"""Deterministic risk classification for backend releases.

Risk levels are derived from objective, verifiable properties of the release
diff.  An LLM may *explain* the classification, but it must not lower a
deterministic minimum risk level.

Classification rules (evaluated in order; highest applicable level wins):

  BLOCKED
    - Failed or bypassed security check.
    - Approval must not proceed.

  HIGH
    - Destructive database migration detected.
    - Cloud permission or identity change.

  MEDIUM
    - Any database migration present.
    - Authentication or authorisation code changed.
    - Billing or quota logic changed.
    - CORS or network configuration changed.
    - Secret-handling code changed.
    - Public API contract changed.
    - Container base-image changed.
    - Terraform infrastructure changed (beyond image tag).
    - Test or scan exceptions present.

  LOW
    - Backend image change only, no migration, all checks passed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


LEVEL_ORDER = {"blocked": 0, "high": 1, "medium": 2, "low": 3}


@dataclass(frozen=True)
class RiskAssessment:
    """Result of deterministic risk classification."""

    level: str  # "blocked", "high", "medium", "low"
    reasons: list[str] = field(default_factory=list)
    minimum_deterministic_level: str = "low"

    def __post_init__(self) -> None:
        if self.level not in LEVEL_ORDER:
            raise ValueError(f"Unknown risk level: {self.level!r}")

    @property
    def allows_approval(self) -> bool:
        return self.level != "blocked"


# ---------------------------------------------------------------------------
# File-pattern detectors
# ---------------------------------------------------------------------------

_MIGRATION_PATTERNS = (
    re.compile(r"^database/migrations/"),
    re.compile(r"^supabase/migrations/"),
    re.compile(r"^migrations/"),
    re.compile(r"^alembic/"),
)

_AUTH_PATTERNS = (
    re.compile(r"app/backend/auth\.py"),
    re.compile(r"app/backend/.*auth.*\.py"),
)

_QUOTA_PATTERNS = (re.compile(r"app/backend/quota\.py"),)

_CORS_PATTERNS = (
    re.compile(r"FIRSTROLL_CORS_ALLOWED_ORIGINS"),
    re.compile(r"CORSMiddleware"),
)

_SECRET_PATTERNS = (
    re.compile(r"app/backend/settings\.py"),
    re.compile(r"SecretStr"),
    re.compile(r"LocalSettingsStore"),
)

_API_CONTRACT_PATTERNS = (
    re.compile(r"@app\.(get|post|put|delete|patch)\("),
    re.compile(r"app/backend/main\.py"),
)

_TERRAFORM_PATTERNS = (re.compile(r"^infra/terraform/.*\.tf$"),)

_DOCKERFILE_PATTERN = re.compile(r"^Dockerfile$")

_RELEASE_AUTHORITY_PATTERNS = (
    re.compile(r"^\.github/workflows/backend-release\.yml$"),
    re.compile(r"^tools/release/"),
)


def _matches_any(path: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(p.search(path) for p in patterns)


def _is_destructive_migration(path: str, diff_content: str | None = None) -> bool:
    """Heuristic: check for DROP, TRUNCATE, DELETE without WHERE in SQL."""
    if diff_content is None:
        return False
    upper = diff_content.upper()
    return any(kw in upper for kw in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM"))


def classify_risk(
    *,
    changed_files: list[str],
    diff_contents: dict[str, str] | None = None,
    ci_passed: bool = True,
    container_tests_passed: bool = True,
    scan_passed: bool | None = None,
    database_migration: bool = False,
    infrastructure_change: bool = False,
    terraform_only_image_tag: bool = False,
) -> RiskAssessment:
    """Classify the risk level of a release based on changed files and CI results.

    Parameters
    ----------
    changed_files:
        List of file paths changed in the release (relative to repo root).
    diff_contents:
        Optional mapping of file path to the actual diff content, used for
        destructive-migration detection.
    ci_passed:
        Whether the CI pipeline passed.
    container_tests_passed:
        Whether the container startup test passed.
    scan_passed:
        Whether the security scan passed.  ``None`` means no scanner configured.
    database_migration:
        Whether any migration file was detected in the diff.
    infrastructure_change:
        Whether Terraform files changed beyond ``image_tag``.
    terraform_only_image_tag:
        If True, Terraform changes are limited to the image tag variable.
    """
    reasons: list[str] = []
    min_level = "low"
    diffs = diff_contents or {}

    # ── BLOCKED conditions ───────────────────────────────────────────────
    if not ci_passed:
        reasons.append("CI pipeline did not pass.")
        return RiskAssessment(
            level="blocked",
            reasons=reasons,
            minimum_deterministic_level="blocked",
        )

    if not container_tests_passed:
        reasons.append("Container startup test did not pass.")
        return RiskAssessment(
            level="blocked",
            reasons=reasons,
            minimum_deterministic_level="blocked",
        )

    if scan_passed is False:
        reasons.append("Security scan reported blocking vulnerabilities.")
        return RiskAssessment(
            level="blocked",
            reasons=reasons,
            minimum_deterministic_level="blocked",
        )

    # ── HIGH conditions ──────────────────────────────────────────────────
    migration_files = [f for f in changed_files if _matches_any(f, _MIGRATION_PATTERNS)]
    if migration_files:
        database_migration = True
        for mf in migration_files:
            if _is_destructive_migration(mf, diffs.get(mf)):
                reasons.append(f"Destructive migration detected: {mf}")
                min_level = "high"

    # Cloud permission changes in Terraform (non-image-tag changes)
    tf_files = [f for f in changed_files if _matches_any(f, _TERRAFORM_PATTERNS)]
    if tf_files and not terraform_only_image_tag:
        for tf in tf_files:
            content = diffs.get(tf, "")
            if any(
                kw in content
                for kw in ("role_definition_name", "identity", "azurerm_role_assignment")
            ):
                reasons.append(f"Cloud permission or identity change in {tf}.")
                min_level = "high"

    authority_files = [f for f in changed_files if _matches_any(f, _RELEASE_AUTHORITY_PATTERNS)]
    if authority_files:
        reasons.append("Production release authority changed: " + ", ".join(authority_files))
        min_level = "high"

    # ── MEDIUM conditions ────────────────────────────────────────────────
    if database_migration and min_level not in ("high",):
        reasons.append("Database migration present.")
        if LEVEL_ORDER.get(min_level, 3) > LEVEL_ORDER["medium"]:
            min_level = "medium"

    auth_files = [f for f in changed_files if _matches_any(f, _AUTH_PATTERNS)]
    if auth_files:
        reasons.append(f"Authentication or authorisation code changed: {', '.join(auth_files)}")
        if LEVEL_ORDER.get(min_level, 3) > LEVEL_ORDER["medium"]:
            min_level = "medium"

    quota_files = [f for f in changed_files if _matches_any(f, _QUOTA_PATTERNS)]
    if quota_files:
        reasons.append("Billing or quota logic changed.")
        if LEVEL_ORDER.get(min_level, 3) > LEVEL_ORDER["medium"]:
            min_level = "medium"

    # CORS changes
    for f in changed_files:
        content = diffs.get(f, "")
        if _matches_any(content, _CORS_PATTERNS) or _matches_any(f, _CORS_PATTERNS):
            reasons.append("CORS or network configuration changed.")
            if LEVEL_ORDER.get(min_level, 3) > LEVEL_ORDER["medium"]:
                min_level = "medium"
            break

    # Secret handling
    secret_files = [f for f in changed_files if _matches_any(f, _SECRET_PATTERNS)]
    if secret_files:
        reasons.append("Secret-handling code changed.")
        if LEVEL_ORDER.get(min_level, 3) > LEVEL_ORDER["medium"]:
            min_level = "medium"

    # API contract changes (routes added/removed)
    api_files = [f for f in changed_files if _matches_any(f, _API_CONTRACT_PATTERNS)]
    if api_files:
        for af in api_files:
            content = diffs.get(af, "")
            if _matches_any(content, _API_CONTRACT_PATTERNS):
                reasons.append(f"Public API contract may have changed: {af}")
                if LEVEL_ORDER.get(min_level, 3) > LEVEL_ORDER["medium"]:
                    min_level = "medium"
                break

    # Base image changes
    dockerfile_changed = any(_DOCKERFILE_PATTERN.search(f) for f in changed_files)
    if dockerfile_changed:
        content = diffs.get("Dockerfile", "")
        base_image_changed = any(
            re.match(r"^[+-]\s*FROM\b", line)
            and not line.startswith(("+++", "---"))
            for line in content.splitlines()
        )
        if base_image_changed:
            reasons.append("Container base-image changed.")
            if LEVEL_ORDER.get(min_level, 3) > LEVEL_ORDER["medium"]:
                min_level = "medium"

    # Terraform infrastructure changes beyond image tag
    if tf_files and not terraform_only_image_tag and min_level not in ("high",):
        reasons.append(f"Terraform infrastructure changed: {', '.join(tf_files)}")
        if LEVEL_ORDER.get(min_level, 3) > LEVEL_ORDER["medium"]:
            min_level = "medium"

    # ── LOW ───────────────────────────────────────────────────────────────
    if not reasons:
        reasons.append(
            "Backend image change only; no migration, infrastructure, or "
            "security-sensitive changes; all checks passed."
        )

    return RiskAssessment(
        level=min_level,
        reasons=reasons,
        minimum_deterministic_level=min_level,
    )
