"""Tests for the human-readable approval summary generator.

Covers: release title, change description, user impact, migration status,
infrastructure status, downtime, risk/reasons, rollback language, technical
identifiers hidden behind details, and handling of unavailable facts.
"""

from __future__ import annotations


from tools.release.manifest import build_manifest
from tools.release.summary import (
    generate_approval_summary,
    generate_full_approval_view,
    generate_technical_details,
)


def _manifest(**overrides):
    defaults = dict(
        repository="Luo-Z-Y/FirstRoll",
        environment="production",
        workflow_run_id=123456789,
        commit_sha="a" * 40,
        branch="master",
        image_repository="firstroll-api",
        image_tag="a" * 40,
        image_digest="sha256:" + "b" * 64,
        ci_passed=True,
        container_tests_passed=True,
        pr_number=42,
        pr_title="Improve film discovery caching and provider timeouts",
        pr_url="#42",
    )
    defaults.update(overrides)
    return build_manifest(**defaults)


class TestPrimarySummary:
    def test_displays_release_title(self):
        summary = generate_approval_summary(_manifest())
        assert "FirstRoll backend release is ready" in summary

    def test_displays_pr_info(self):
        summary = generate_approval_summary(_manifest())
        assert "PR #42" in summary
        assert "Improve film discovery caching" in summary

    def test_displays_change_description(self):
        m = _manifest(user_visible_changes=["Faster film searches."])
        summary = generate_approval_summary(m)
        assert "Faster film searches." in summary

    def test_displays_expected_user_impact(self):
        summary = generate_approval_summary(_manifest())
        assert "No planned downtime" in summary

    def test_displays_migration_status_none(self):
        summary = generate_approval_summary(_manifest())
        assert "No database migration" in summary

    def test_displays_migration_status_present(self):
        m = _manifest(
            database_migration=True,
            migration_files=["database/migrations/001_add_index.sql"],
        )
        summary = generate_approval_summary(m)
        assert "Database migration included" in summary

    def test_displays_infrastructure_status(self):
        summary = generate_approval_summary(_manifest())
        assert "backend image only" in summary

    def test_displays_no_downtime(self):
        summary = generate_approval_summary(_manifest())
        assert "No planned downtime" in summary

    def test_displays_risk_level(self):
        summary = generate_approval_summary(_manifest())
        assert "Low" in summary

    def test_displays_risk_reasons(self):
        m = _manifest(risk_reasons=["Provider timeout logic changed."])
        summary = generate_approval_summary(m)
        assert "Provider timeout logic changed." in summary

    def test_displays_rollback(self):
        summary = generate_approval_summary(_manifest())
        assert "revision" in summary.lower()

    def test_displays_after_approval_steps(self):
        summary = generate_approval_summary(_manifest())
        assert "Deploy the prepared backend image" in summary
        assert "health endpoint" in summary.lower()

    def test_frontend_unchanged_note(self):
        summary = generate_approval_summary(_manifest())
        assert "frontend is unchanged" in summary.lower()


class TestTechnicalDetails:
    def test_contains_commit_sha(self):
        details = generate_technical_details(_manifest())
        assert "a" * 40 in details

    def test_contains_image_digest(self):
        details = generate_technical_details(_manifest())
        assert "sha256:" + "b" * 64 in details

    def test_contains_workflow_run_id(self):
        details = generate_technical_details(_manifest())
        assert "123456789" in details

    def test_contains_environment(self):
        details = generate_technical_details(_manifest())
        assert "production" in details

    def test_contains_repository(self):
        details = generate_technical_details(_manifest())
        assert "Luo-Z-Y/FirstRoll" in details


class TestFullApprovalView:
    def test_primary_and_details_present(self):
        view = generate_full_approval_view(_manifest())
        assert "FirstRoll backend release is ready" in view
        assert "Technical details" in view

    def test_technical_details_in_expandable(self):
        view = generate_full_approval_view(_manifest())
        assert "<details>" in view
        assert "<summary>" in view


class TestRawIdentifiersHidden:
    def test_primary_summary_does_not_expose_raw_sha(self):
        """The 40-character SHA should not appear in the primary summary."""
        summary = generate_approval_summary(_manifest())
        assert "a" * 40 not in summary

    def test_primary_summary_does_not_expose_raw_digest(self):
        summary = generate_approval_summary(_manifest())
        assert "sha256:" + "b" * 64 not in summary

    def test_primary_summary_does_not_expose_run_id(self):
        summary = generate_approval_summary(_manifest())
        assert "123456789" not in summary


class TestUnavailableFacts:
    def test_scan_not_configured_shows_warning(self):
        summary = generate_approval_summary(_manifest())
        assert "not configured" in summary.lower() or "⚠️" in summary

    def test_never_fabricates_unavailable_facts(self):
        """When scan_passed is None, the summary must not claim it passed."""
        m = _manifest()
        summary = generate_approval_summary(m)
        assert m.verification.scan_passed is None
        # Should NOT say "No blocking vulnerabilities found"
        # Should say something like "not configured"
        assert "not configured" in summary.lower() or "⚠️" in summary

    def test_current_production_unavailable(self):
        details = generate_technical_details(_manifest())
        assert "unavailable" in details.lower()
