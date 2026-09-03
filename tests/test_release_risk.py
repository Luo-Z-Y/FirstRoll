"""Tests for deterministic risk classification.

Covers: CI failure blocks approval, migration detection, destructive
migration, auth changes, Terraform changes, cloud permission changes,
CORS changes, secret handling, API contract, Dockerfile base-image,
and the default low-risk backend-only case.
"""

from __future__ import annotations

import pytest

from tools.release.risk import RiskAssessment, classify_risk


class TestBlockedConditions:
    def test_ci_failure_blocks_approval(self):
        result = classify_risk(changed_files=[], ci_passed=False)
        assert result.level == "blocked"
        assert not result.allows_approval

    def test_container_test_failure_blocks(self):
        result = classify_risk(
            changed_files=[],
            ci_passed=True,
            container_tests_passed=False,
        )
        assert result.level == "blocked"
        assert not result.allows_approval

    def test_scan_failure_blocks(self):
        result = classify_risk(
            changed_files=[],
            ci_passed=True,
            scan_passed=False,
        )
        assert result.level == "blocked"


class TestHighRisk:
    def test_destructive_migration_is_high(self):
        result = classify_risk(
            changed_files=["database/migrations/001_drop_table.sql"],
            diff_contents={
                "database/migrations/001_drop_table.sql": ("+DROP TABLE users;"),
            },
        )
        assert result.level == "high"
        assert "destructive" in result.reasons[0].lower()

    def test_cloud_permission_change_is_high(self):
        result = classify_risk(
            changed_files=["infra/terraform/main.tf"],
            diff_contents={
                "infra/terraform/main.tf": ('+  role_definition_name = "Contributor"'),
            },
        )
        assert result.level == "high"
        assert any("permission" in r.lower() or "identity" in r.lower() for r in result.reasons)


class TestMediumRisk:
    def test_migration_present_is_medium(self):
        result = classify_risk(
            changed_files=["database/migrations/001_add_index.sql"],
        )
        assert result.level == "medium"
        assert any("migration" in r.lower() for r in result.reasons)

    def test_supabase_migration_detected(self):
        result = classify_risk(
            changed_files=["supabase/migrations/001_add_column.sql"],
        )
        assert result.level == "medium"

    def test_auth_change_is_medium(self):
        result = classify_risk(
            changed_files=["app/backend/auth.py"],
        )
        assert result.level == "medium"
        assert any("auth" in r.lower() for r in result.reasons)

    def test_quota_change_is_medium(self):
        result = classify_risk(
            changed_files=["app/backend/quota.py"],
        )
        assert result.level == "medium"

    def test_cors_change_is_medium(self):
        result = classify_risk(
            changed_files=["app/backend/main.py"],
            diff_contents={
                "app/backend/main.py": "CORSMiddleware\nFIRSTROLL_CORS_ALLOWED_ORIGINS",
            },
        )
        assert result.level == "medium"

    def test_secret_handling_change_is_medium(self):
        result = classify_risk(
            changed_files=["app/backend/settings.py"],
        )
        assert result.level == "medium"

    def test_terraform_infrastructure_change_is_medium(self):
        result = classify_risk(
            changed_files=["infra/terraform/main.tf"],
            diff_contents={"infra/terraform/main.tf": "+ some_resource"},
        )
        # At least medium (could be high if permission changes detected)
        assert result.level in ("medium", "high")

    def test_dockerfile_base_image_change_is_medium(self):
        result = classify_risk(
            changed_files=["Dockerfile"],
            diff_contents={"Dockerfile": "+FROM python:3.12-slim"},
        )
        assert result.level == "medium"
        assert any("base-image" in r.lower() for r in result.reasons)


class TestLowRisk:
    def test_backend_code_only_all_checks_passed(self):
        result = classify_risk(
            changed_files=["app/backend/discovery.py"],
            ci_passed=True,
            container_tests_passed=True,
        )
        assert result.level == "low"
        assert result.allows_approval

    def test_no_changes_is_low(self):
        result = classify_risk(changed_files=[])
        assert result.level == "low"

    def test_scan_none_does_not_block(self):
        """Scanner not configured is not a blocker (None != False)."""
        result = classify_risk(
            changed_files=["app/backend/discovery.py"],
            scan_passed=None,
        )
        assert result.level == "low"


class TestRiskAssessmentProperties:
    def test_allows_approval_for_low(self):
        assert RiskAssessment(level="low").allows_approval is True

    def test_allows_approval_for_medium(self):
        assert RiskAssessment(level="medium").allows_approval is True

    def test_allows_approval_for_high(self):
        assert RiskAssessment(level="high").allows_approval is True

    def test_does_not_allow_approval_for_blocked(self):
        assert RiskAssessment(level="blocked").allows_approval is False

    def test_unknown_level_raises(self):
        with pytest.raises(ValueError):
            RiskAssessment(level="unknown")


class TestRiskCannotBeLowered:
    def test_deterministic_minimum_is_preserved(self):
        """The LLM cannot lower a deterministic minimum risk level."""
        result = classify_risk(
            changed_files=["database/migrations/001_schema.sql"],
        )
        assert result.minimum_deterministic_level == "medium"
        # Even if someone tried to override the level, the minimum is recorded
        assert result.level == result.minimum_deterministic_level or result.level in (
            "high",
            "blocked",
        )
