"""Release manifest data model and generation.

The manifest captures every machine-verifiable fact about a release candidate.
An LLM may turn these facts into clearer prose, but it must not invent or alter
any field in this structure.  The approval decision binds to the manifest, not
to the natural-language summary.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PullRequest:
    """Merged pull request associated with the release."""

    number: int
    title: str
    url: str


@dataclass(frozen=True)
class Candidate:
    """Immutable container image produced by the build."""

    image_repository: str
    image_tag: str
    image_digest: str  # sha256:...
    artifact_digest: str  # sha256 of the manifest JSON itself (set after serialisation)
    created_at: str  # ISO-8601


@dataclass(frozen=True)
class CurrentProduction:
    """State of the currently deployed production revision."""

    image_digest: str | None = None
    revision: str | None = None
    deployed_at: str | None = None


@dataclass(frozen=True)
class Verification:
    """Deterministic verification results from CI and build."""

    ci_passed: bool
    container_tests_passed: bool
    scan_passed: bool | None = None  # None = scanner not configured
    sbom_generated: bool | None = None
    terraform_plan_available: bool | None = None


@dataclass(frozen=True)
class ChangeSummary:
    """Human-interpretable description of the release changes.

    Fields populated from deterministic sources (diff analysis, migration
    detection, Terraform plan) are authoritative.  LLM-generated fields
    (``user_visible_changes``, ``risk_reasons``) are clearly separated.
    """

    release_title: str
    user_visible_changes: list[str] = field(default_factory=list)
    expected_impact: list[str] = field(default_factory=list)
    database_migration: bool = False
    migration_files: list[str] = field(default_factory=list)
    infrastructure_change: str = "backend image only"
    terraform_changed_files: list[str] = field(default_factory=list)
    expected_downtime: str = "none"
    risk_level: str = "low"
    risk_reasons: list[str] = field(default_factory=list)
    rollback_summary: str = "Restore the previously active Container Apps revision."


@dataclass(frozen=True)
class ReleaseManifest:
    """Complete, machine-produced release manifest.

    Every field is populated from a deterministic, verifiable source.
    Fields that cannot be verified are explicitly ``None`` or empty.
    """

    schema_version: int
    repository: str
    environment: str
    workflow_run_id: int
    commit_sha: str  # full 40-character SHA
    branch: str
    pull_request: PullRequest | None
    candidate: Candidate
    current_production: CurrentProduction
    verification: Verification
    change_summary: ChangeSummary

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary suitable for JSON encoding."""
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        """Serialise to canonical JSON with sorted keys."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def digest(self) -> str:
        """Compute a SHA-256 digest of the canonical JSON representation.

        The ``artifact_digest`` field in the candidate is excluded from the
        hash input to avoid circularity — the manifest digest *is* the
        artifact digest.
        """
        d = self.to_dict()
        d["candidate"]["artifact_digest"] = ""
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def manifest_from_dict(data: dict[str, Any]) -> ReleaseManifest:
    """Reconstruct a ``ReleaseManifest`` from a plain dictionary."""
    pr_data = data.get("pull_request")
    pr = PullRequest(**pr_data) if pr_data else None
    return ReleaseManifest(
        schema_version=data["schema_version"],
        repository=data["repository"],
        environment=data["environment"],
        workflow_run_id=data["workflow_run_id"],
        commit_sha=data["commit_sha"],
        branch=data["branch"],
        pull_request=pr,
        candidate=Candidate(**data["candidate"]),
        current_production=CurrentProduction(**data.get("current_production", {})),
        verification=Verification(**data["verification"]),
        change_summary=ChangeSummary(**data["change_summary"]),
    )


def manifest_from_json(text: str) -> ReleaseManifest:
    """Parse a manifest from its JSON representation."""
    return manifest_from_dict(json.loads(text))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_manifest(
    *,
    repository: str,
    environment: str,
    workflow_run_id: int,
    commit_sha: str,
    branch: str,
    pr_number: int | None = None,
    pr_title: str | None = None,
    pr_url: str | None = None,
    image_repository: str,
    image_tag: str,
    image_digest: str,
    ci_passed: bool,
    container_tests_passed: bool,
    scan_passed: bool | None = None,
    sbom_generated: bool | None = None,
    terraform_plan_available: bool | None = None,
    release_title: str = "",
    user_visible_changes: list[str] | None = None,
    expected_impact: list[str] | None = None,
    database_migration: bool = False,
    migration_files: list[str] | None = None,
    infrastructure_change: str = "backend image only",
    terraform_changed_files: list[str] | None = None,
    expected_downtime: str = "none",
    risk_level: str = "low",
    risk_reasons: list[str] | None = None,
    rollback_summary: str = "Restore the previously active Container Apps revision.",
    current_image_digest: str | None = None,
    current_revision: str | None = None,
    current_deployed_at: str | None = None,
) -> ReleaseManifest:
    """Build a ``ReleaseManifest`` from verified release facts.

    Call this from the CI manifest-generation step with values sourced from
    deterministic workflow metadata, registry queries, and diff analysis.
    """
    pr = None
    if pr_number is not None and pr_title is not None:
        pr = PullRequest(
            number=pr_number,
            title=pr_title,
            url=pr_url or f"#{pr_number}",
        )

    title = release_title or (pr_title if pr_title else f"Release {commit_sha[:7]}")

    candidate = Candidate(
        image_repository=image_repository,
        image_tag=image_tag,
        image_digest=image_digest,
        artifact_digest="",  # set after digest computation
        created_at=_now_iso(),
    )

    manifest = ReleaseManifest(
        schema_version=SCHEMA_VERSION,
        repository=repository,
        environment=environment,
        workflow_run_id=workflow_run_id,
        commit_sha=commit_sha,
        branch=branch,
        pull_request=pr,
        candidate=candidate,
        current_production=CurrentProduction(
            image_digest=current_image_digest,
            revision=current_revision,
            deployed_at=current_deployed_at,
        ),
        verification=Verification(
            ci_passed=ci_passed,
            container_tests_passed=container_tests_passed,
            scan_passed=scan_passed,
            sbom_generated=sbom_generated,
            terraform_plan_available=terraform_plan_available,
        ),
        change_summary=ChangeSummary(
            release_title=title,
            user_visible_changes=user_visible_changes or [],
            expected_impact=expected_impact or [],
            database_migration=database_migration,
            migration_files=migration_files or [],
            infrastructure_change=infrastructure_change,
            terraform_changed_files=terraform_changed_files or [],
            expected_downtime=expected_downtime,
            risk_level=risk_level,
            risk_reasons=risk_reasons or [],
            rollback_summary=rollback_summary,
        ),
    )

    # Rewrite the candidate with the computed artifact digest.
    artifact_digest = manifest.digest()
    final_candidate = Candidate(
        image_repository=candidate.image_repository,
        image_tag=candidate.image_tag,
        image_digest=candidate.image_digest,
        artifact_digest=artifact_digest,
        created_at=candidate.created_at,
    )

    return ReleaseManifest(
        schema_version=manifest.schema_version,
        repository=manifest.repository,
        environment=manifest.environment,
        workflow_run_id=manifest.workflow_run_id,
        commit_sha=manifest.commit_sha,
        branch=manifest.branch,
        pull_request=manifest.pull_request,
        candidate=final_candidate,
        current_production=manifest.current_production,
        verification=manifest.verification,
        change_summary=manifest.change_summary,
    )
