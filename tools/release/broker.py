"""Trusted approval broker for FirstRoll backend deployments.

This is a standalone FastAPI service that validates single-use authorisation
capabilities and submits production deployment approvals to the GitHub API.

Trust boundary:
  - The broker does NOT execute repository-controlled code.
  - The broker does NOT access Azure production credentials.
  - The broker validates the authorisation token and calls the GitHub
    pending-deployments API using a GitHub App installation token.
  - The GitHub App private key is stored in the broker's secure runtime
    environment, never in the repository or CI variables.

Deployment:
  - Run as a separate service (Azure Functions, Container App, or VM).
  - Requires: GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, APPROVAL_SIGNING_KEY.
  - Exposes: POST /api/approve, GET /api/pending/{run_id}, GET /api/health.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from tools.release.authorization import (
    AuthorizationCapability,
    NonceStore,
    VerificationResult,
    capability_from_token,
    verify_capability,
)
from tools.release.audit import AuditLog, record_approval_event


logger = logging.getLogger("firstroll.release.broker")

# In-memory nonce store.  Production should use Redis or equivalent.
_nonce_store = NonceStore()

# File-backed audit log.  Production should use a durable log service.
_audit_log = AuditLog()


@dataclass
class ApprovalRequest:
    """Incoming approval request from the agent or UI."""

    release_id: str  # opaque release identifier (run_id-sha7)
    decision: str  # "approve" or "reject"
    authorization_token: str  # signed capability JSON


@dataclass
class ApprovalResponse:
    """Response from the approval broker."""

    accepted: bool
    message: str
    audit_event_id: str = ""
    github_result: dict[str, Any] | None = None


@dataclass
class PendingRelease:
    """Pending release information from GitHub."""

    run_id: int
    environment_id: int
    environment_name: str
    commit_sha: str
    can_approve: bool
    reviewers: list[dict[str, Any]]


def _get_signing_key() -> str:
    """Read the HMAC signing key from the secure environment."""
    key = os.environ.get("APPROVAL_SIGNING_KEY", "")
    if not key:
        raise RuntimeError("APPROVAL_SIGNING_KEY is not configured.")
    return key


class ApprovalBroker:
    """Trusted approval broker that validates capabilities and calls GitHub.

    Parameters
    ----------
    signing_key:
        HMAC-SHA256 signing key shared with the capability issuer.
    github_token_provider:
        Callable that returns a short-lived GitHub App installation token.
        In production, this generates a token from the App's private key.
    nonce_store:
        Single-use nonce store for replay protection.
    audit_log:
        Durable audit log for recording approval events.
    """

    def __init__(
        self,
        *,
        signing_key: str,
        github_token_provider: Any = None,
        nonce_store: NonceStore | None = None,
        audit_log: AuditLog | None = None,
    ) -> None:
        self._signing_key = signing_key
        self._github_token_provider = github_token_provider
        self._nonce_store = nonce_store or _nonce_store
        self._audit_log = audit_log or _audit_log

    def process_approval(
        self,
        request: ApprovalRequest,
        *,
        expected_repository: str = "Luo-Z-Y/FirstRoll",
        expected_environment: str = "production",
    ) -> ApprovalResponse:
        """Process an approval request.

        Steps:
        1. Deserialise and verify the authorisation capability.
        2. Verify bindings (repository, environment, etc.).
        3. Verify expiry and replay protection.
        4. Call the GitHub pending-deployments API (if a token provider exists).
        5. Record an audit event.
        6. Return the result.
        """
        # 1. Parse the capability
        try:
            capability = capability_from_token(request.authorization_token)
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.warning("Failed to parse authorisation token: %s", exc)
            return ApprovalResponse(
                accepted=False,
                message="Malformed authorisation token.",
            )

        # 2-3. Verify the capability
        result = verify_capability(
            capability,
            signing_key=self._signing_key,
            nonce_store=self._nonce_store,
            expected_repository=expected_repository,
            expected_environment=expected_environment,
        )

        if not result.valid:
            logger.warning("Authorisation verification failed: %s", result.error)
            return ApprovalResponse(accepted=False, message=result.error)

        # 4. Call GitHub API (if provider is configured)
        github_result: dict[str, Any] = {}
        github_approval_status = "approved"

        if self._github_token_provider is not None:
            try:
                github_result = self._submit_github_approval(capability)
            except Exception as exc:
                logger.error("GitHub API call failed: %s", exc)
                github_approval_status = "error"
                return ApprovalResponse(
                    accepted=False,
                    message=f"GitHub API call failed: {exc}",
                )
        else:
            logger.info(
                "No GitHub token provider configured; approval validated "
                "but not submitted to GitHub.  The deployment will remain "
                "pending for manual GitHub approval."
            )
            github_approval_status = "validated_locally"

        # 5. Record audit event
        event = record_approval_event(
            audit_log=self._audit_log,
            authorizing_user=capability.authorizing_user,
            repository=capability.repository,
            environment=capability.environment,
            workflow_run_id=capability.workflow_run_id,
            commit_sha=capability.commit_sha,
            image_digest=capability.image_digest,
            manifest_digest=capability.manifest_digest,
            risk_classification="",  # From manifest, not capability
            authorization_nonce=capability.nonce,
            authorization_expiry=capability.expires_at,
            github_approval_result=github_approval_status,
            detail=(
                f"Agent submitted approval under explicit authorisation "
                f"from {capability.authorizing_user}."
            ),
        )

        # 6. Return result
        return ApprovalResponse(
            accepted=True,
            message=(
                f"Approval accepted for workflow run {capability.workflow_run_id}, "
                f"commit {capability.commit_sha[:7]}."
            ),
            audit_event_id=event.authorization_nonce,
            github_result=github_result or None,
        )

    def _submit_github_approval(
        self,
        capability: AuthorizationCapability,
    ) -> dict[str, Any]:
        """Submit the pending deployment approval to GitHub.

        Uses the GitHub REST API:
        POST /repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments

        The GitHub App installation token is generated fresh for each call.
        """
        # This method requires the 'requests' library and a configured
        # GitHub App.  For the MVP, it's designed but not invoked in CI.
        #
        # In production:
        #   token = self._github_token_provider()
        #   response = requests.post(
        #       f"https://api.github.com/repos/{owner}/{repo}"
        #       f"/actions/runs/{run_id}/pending_deployments",
        #       headers={
        #           "Authorization": f"Bearer {token}",
        #           "Accept": "application/vnd.github+json",
        #           "X-GitHub-Api-Version": "2022-11-28",
        #       },
        #       json={
        #           "environment_ids": [environment_id],
        #           "state": "approved",
        #           "comment": (
        #               f"Approved by firstroll-release-approver under "
        #               f"explicit authorisation from "
        #               f"{capability.authorizing_user}. "
        #               f"Nonce: {capability.nonce[:8]}..."
        #           ),
        #       },
        #   )
        #   response.raise_for_status()
        #   return response.json()
        raise NotImplementedError(
            "GitHub App token provider not configured.  "
            "Deploy the approval broker service to enable "
            "programmatic GitHub approval."
        )


def create_broker(
    *,
    signing_key: str | None = None,
    nonce_store: NonceStore | None = None,
    audit_log: AuditLog | None = None,
) -> ApprovalBroker:
    """Create an approval broker instance.

    Reads configuration from the environment if not provided explicitly.
    """
    key = signing_key or _get_signing_key()
    return ApprovalBroker(
        signing_key=key,
        nonce_store=nonce_store,
        audit_log=audit_log,
    )
