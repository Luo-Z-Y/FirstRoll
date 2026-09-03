"""Single-use HMAC-signed authorization capabilities.

An authorization token binds a user's explicit approval decision to:

    repository + environment + workflow run ID + commit SHA +
    image digest + deployment target + expiry + nonce

The token is:
  - single-use (nonce consumed after first verification)
  - short-lived (default 15-minute expiry)
  - HMAC-SHA256 signed
  - rejected after expiry
  - rejected after consumption
  - unusable for a different repository, environment, run, commit, or digest

The signing key is a shared secret between the authorization issuer (the
agent-facing approval interface) and the trusted approval broker.  It must
never be stored in the repository, in CI variables, or in the agent runtime.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


DEFAULT_EXPIRY_SECONDS = 900  # 15 minutes


@dataclass(frozen=True)
class AuthorizationCapability:
    """Narrowly scoped, single-use approval capability."""

    repository: str
    environment: str
    workflow_run_id: int
    commit_sha: str
    image_digest: str
    deployment_target: str
    manifest_digest: str
    authorizing_user: str
    decision: str  # "approve" or "reject"
    nonce: str
    issued_at: str  # ISO-8601
    expires_at: str  # ISO-8601
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "environment": self.environment,
            "workflow_run_id": self.workflow_run_id,
            "commit_sha": self.commit_sha,
            "image_digest": self.image_digest,
            "deployment_target": self.deployment_target,
            "manifest_digest": self.manifest_digest,
            "authorizing_user": self.authorizing_user,
            "decision": self.decision,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }

    def signing_payload(self) -> bytes:
        """Canonical byte string used as the HMAC input."""
        d = self.to_dict()
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()

    def to_token(self) -> str:
        """Serialise to a compact JSON token including the signature."""
        d = self.to_dict()
        d["signature"] = self.signature
        return json.dumps(d, sort_keys=True, separators=(",", ":"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_capability(
    *,
    signing_key: str,
    repository: str,
    environment: str,
    workflow_run_id: int,
    commit_sha: str,
    image_digest: str,
    deployment_target: str,
    manifest_digest: str,
    authorizing_user: str,
    decision: str = "approve",
    expiry_seconds: int = DEFAULT_EXPIRY_SECONDS,
) -> AuthorizationCapability:
    """Mint a new single-use authorization capability.

    Parameters
    ----------
    signing_key:
        Shared HMAC-SHA256 key.  Must be kept secret.
    decision:
        ``"approve"`` or ``"reject"``.
    expiry_seconds:
        Time until the capability expires.  Default: 15 minutes.
    """
    if decision not in ("approve", "reject"):
        raise ValueError(f"decision must be 'approve' or 'reject', got {decision!r}")

    now = _now()
    cap = AuthorizationCapability(
        repository=repository,
        environment=environment,
        workflow_run_id=workflow_run_id,
        commit_sha=commit_sha,
        image_digest=image_digest,
        deployment_target=deployment_target,
        manifest_digest=manifest_digest,
        authorizing_user=authorizing_user,
        decision=decision,
        nonce=secrets.token_urlsafe(32),
        issued_at=now.isoformat(timespec="seconds"),
        expires_at=(now + timedelta(seconds=expiry_seconds)).isoformat(timespec="seconds"),
    )

    sig = hmac.new(
        signing_key.encode(),
        cap.signing_payload(),
        hashlib.sha256,
    ).hexdigest()

    return AuthorizationCapability(
        repository=cap.repository,
        environment=cap.environment,
        workflow_run_id=cap.workflow_run_id,
        commit_sha=cap.commit_sha,
        image_digest=cap.image_digest,
        deployment_target=cap.deployment_target,
        manifest_digest=cap.manifest_digest,
        authorizing_user=cap.authorizing_user,
        decision=cap.decision,
        nonce=cap.nonce,
        issued_at=cap.issued_at,
        expires_at=cap.expires_at,
        signature=sig,
    )


def capability_from_token(token: str) -> AuthorizationCapability:
    """Deserialise a capability from its compact JSON token."""
    d = json.loads(token)
    return AuthorizationCapability(**d)


# ---------------------------------------------------------------------------
# Nonce store — single-use enforcement
# ---------------------------------------------------------------------------


class NonceStore:
    """Thread-safe in-memory nonce store for single-use enforcement.

    In production, replace with a durable store (e.g. Redis, DynamoDB)
    that supports atomic test-and-set with TTL expiry.
    """

    def __init__(self) -> None:
        self._consumed: set[str] = set()
        self._lock = threading.Lock()

    def consume(self, nonce: str) -> bool:
        """Atomically consume a nonce.  Returns True if this was the first use."""
        with self._lock:
            if nonce in self._consumed:
                return False
            self._consumed.add(nonce)
            return True

    def is_consumed(self, nonce: str) -> bool:
        with self._lock:
            return nonce in self._consumed

    def clear(self) -> None:
        """Remove all consumed nonces (for testing only)."""
        with self._lock:
            self._consumed.clear()


@dataclass
class VerificationResult:
    """Result of capability verification."""

    valid: bool
    error: str = ""


def verify_capability(
    capability: AuthorizationCapability,
    *,
    signing_key: str,
    nonce_store: NonceStore,
    expected_repository: str | None = None,
    expected_environment: str | None = None,
    expected_workflow_run_id: int | None = None,
    expected_commit_sha: str | None = None,
    expected_image_digest: str | None = None,
    expected_manifest_digest: str | None = None,
) -> VerificationResult:
    """Verify an authorization capability.

    Checks performed (in order):

    1. Signature is valid (HMAC-SHA256).
    2. Capability has not expired.
    3. Nonce has not been previously consumed.
    4. Decision is ``"approve"``.
    5. All expected binding fields match.

    On success, the nonce is consumed atomically.  On failure, the nonce
    is *not* consumed (so the holder may retry after correcting the issue,
    provided the capability has not expired).
    """
    # 1. Verify signature
    expected_sig = hmac.new(
        signing_key.encode(),
        capability.signing_payload(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(capability.signature, expected_sig):
        return VerificationResult(valid=False, error="Invalid signature.")

    # 2. Check expiry
    try:
        expires = datetime.fromisoformat(capability.expires_at)
    except ValueError:
        return VerificationResult(valid=False, error="Malformed expiry timestamp.")

    if _now() >= expires:
        return VerificationResult(valid=False, error="Authorization has expired.")

    # 3. Check decision
    if capability.decision != "approve":
        return VerificationResult(
            valid=False,
            error=f"Decision is '{capability.decision}', not 'approve'.",
        )

    # 4. Verify bindings
    checks: list[tuple[str, Any, Any]] = []
    if expected_repository is not None:
        checks.append(("repository", capability.repository, expected_repository))
    if expected_environment is not None:
        checks.append(("environment", capability.environment, expected_environment))
    if expected_workflow_run_id is not None:
        checks.append(("workflow_run_id", capability.workflow_run_id, expected_workflow_run_id))
    if expected_commit_sha is not None:
        checks.append(("commit_sha", capability.commit_sha, expected_commit_sha))
    if expected_image_digest is not None:
        checks.append(("image_digest", capability.image_digest, expected_image_digest))
    if expected_manifest_digest is not None:
        checks.append(("manifest_digest", capability.manifest_digest, expected_manifest_digest))

    for field_name, actual, expected in checks:
        if actual != expected:
            return VerificationResult(
                valid=False,
                error=f"Binding mismatch: {field_name} expected {expected!r}, got {actual!r}.",
            )

    # 5. Consume nonce (atomic single-use)
    if not nonce_store.consume(capability.nonce):
        return VerificationResult(valid=False, error="Authorization has already been used.")

    return VerificationResult(valid=True)
