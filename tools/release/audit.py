"""Durable audit event recording for production deployments.

Every approval, deployment, and rollback action is recorded as a structured
audit event.  The record clearly communicates:

    "Agent submitted approval under explicit authorisation from the named user."

Audit events contain identifiers but never secrets, tokens, private keys,
or authorisation headers.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


logger = logging.getLogger("firstroll.release.audit")


@dataclass
class AuditEvent:
    """Structured audit event for a production deployment action."""

    # Who
    authorizing_user: str
    agent_identity: str = "firstroll-release-agent"
    approval_service_identity: str = "firstroll-release-approver"

    # When
    timestamp: str = ""

    # What (release identity)
    repository: str = ""
    environment: str = ""
    workflow_run_id: int = 0
    commit_sha: str = ""
    image_digest: str = ""
    manifest_digest: str = ""

    # Production state
    current_production_revision: str = ""
    rollback_target: str = ""

    # Assessment
    risk_classification: str = ""

    # Authorisation
    authorization_expiry: str = ""
    authorization_nonce: str = ""

    # Results
    github_approval_result: str = ""  # "approved", "rejected", "error", "pending"
    deployment_result: str = ""  # "success", "failed", "pending", "skipped"
    smoke_test_result: str = ""  # "passed", "failed", "skipped"
    rollback_result: str = ""  # "success", "failed", "not_required"

    # Explanation
    action: str = ""  # "approval_submitted", "deployment_completed", "rollback_initiated"
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


class AuditLog:
    """Append-only audit log backed by a JSON Lines file.

    In production, replace with a durable, tamper-evident log service
    (e.g. Azure Monitor, CloudWatch Logs, or a dedicated audit database).
    """

    def __init__(self, log_path: str | Path | None = None) -> None:
        if log_path is None:
            log_path = os.environ.get(
                "FIRSTROLL_AUDIT_LOG",
                "/var/log/firstroll/release-audit.jsonl",
            )
        self._path = Path(log_path)

    def record(self, event: AuditEvent) -> None:
        """Append an audit event to the log."""
        line = json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a") as f:
                f.write(line + "\n")
            logger.info(
                "Audit event recorded: action=%s user=%s run=%s",
                event.action,
                event.authorizing_user,
                event.workflow_run_id,
            )
        except OSError as exc:
            # Log failure must not block the approval flow, but it must
            # be reported clearly.
            logger.error("Failed to write audit event: %s", exc)

    def read_events(self) -> list[AuditEvent]:
        """Read all audit events from the log (for testing/review)."""
        events: list[AuditEvent] = []
        if not self._path.exists():
            return events
        with self._path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    events.append(AuditEvent(**d))
        return events


def record_approval_event(
    *,
    audit_log: AuditLog,
    authorizing_user: str,
    repository: str,
    environment: str,
    workflow_run_id: int,
    commit_sha: str,
    image_digest: str,
    manifest_digest: str,
    risk_classification: str,
    authorization_nonce: str,
    authorization_expiry: str,
    current_production_revision: str = "",
    rollback_target: str = "",
    github_approval_result: str = "pending",
    detail: str = "",
) -> AuditEvent:
    """Record an approval-submission audit event."""
    event = AuditEvent(
        authorizing_user=authorizing_user,
        action="approval_submitted",
        repository=repository,
        environment=environment,
        workflow_run_id=workflow_run_id,
        commit_sha=commit_sha,
        image_digest=image_digest,
        manifest_digest=manifest_digest,
        risk_classification=risk_classification,
        authorization_nonce=authorization_nonce,
        authorization_expiry=authorization_expiry,
        current_production_revision=current_production_revision,
        rollback_target=rollback_target,
        github_approval_result=github_approval_result,
        detail=detail
        or (f"Agent submitted approval under explicit authorisation from {authorizing_user}."),
    )
    audit_log.record(event)
    return event


def record_deployment_event(
    *,
    audit_log: AuditLog,
    authorizing_user: str,
    repository: str,
    environment: str,
    workflow_run_id: int,
    commit_sha: str,
    image_digest: str,
    deployment_result: str,
    smoke_test_result: str = "skipped",
    rollback_result: str = "not_required",
    detail: str = "",
) -> AuditEvent:
    """Record a deployment-completed audit event."""
    event = AuditEvent(
        authorizing_user=authorizing_user,
        action="deployment_completed",
        repository=repository,
        environment=environment,
        workflow_run_id=workflow_run_id,
        commit_sha=commit_sha,
        image_digest=image_digest,
        deployment_result=deployment_result,
        smoke_test_result=smoke_test_result,
        rollback_result=rollback_result,
        detail=detail,
    )
    audit_log.record(event)
    return event
