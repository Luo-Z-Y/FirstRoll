"""Tests for the release manifest data model and generation.

Covers: serialisation round-trip, digest stability, field validation,
and handling of unavailable data.
"""

from __future__ import annotations

import json

import pytest

from tools.release.manifest import (
    SCHEMA_VERSION,
    Candidate,
    ChangeSummary,
    CurrentProduction,
    PullRequest,
    ReleaseManifest,
    Verification,
    build_manifest,
    manifest_from_json,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_manifest(**overrides):
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
        pr_title="Improve film discovery caching",
        pr_url="#42",
    )
    defaults.update(overrides)
    return build_manifest(**defaults)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestManifestSerialisation:
    def test_round_trip_json(self):
        m = _sample_manifest()
        text = m.to_json()
        restored = manifest_from_json(text)
        assert restored.commit_sha == m.commit_sha
        assert restored.candidate.image_digest == m.candidate.image_digest
        assert restored.verification.ci_passed is True
        assert restored.pull_request is not None
        assert restored.pull_request.number == 42

    def test_schema_version(self):
        m = _sample_manifest()
        assert m.schema_version == SCHEMA_VERSION

    def test_to_dict_contains_all_fields(self):
        m = _sample_manifest()
        d = m.to_dict()
        assert "schema_version" in d
        assert "repository" in d
        assert "candidate" in d
        assert "verification" in d
        assert "change_summary" in d

    def test_manifest_without_pr(self):
        m = _sample_manifest(pr_number=None, pr_title=None)
        assert m.pull_request is None
        text = m.to_json()
        restored = manifest_from_json(text)
        assert restored.pull_request is None


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------


class TestManifestDigest:
    def test_digest_is_deterministic(self):
        m1 = _sample_manifest()
        m2 = _sample_manifest()
        assert m1.digest() == m2.digest()

    def test_digest_changes_with_commit_sha(self):
        m1 = _sample_manifest(commit_sha="a" * 40)
        m2 = _sample_manifest(commit_sha="c" * 40)
        assert m1.digest() != m2.digest()

    def test_digest_changes_with_image_digest(self):
        m1 = _sample_manifest(image_digest="sha256:" + "b" * 64)
        m2 = _sample_manifest(image_digest="sha256:" + "d" * 64)
        assert m1.digest() != m2.digest()

    def test_digest_changes_with_workflow_run_id(self):
        m1 = _sample_manifest(workflow_run_id=1)
        m2 = _sample_manifest(workflow_run_id=2)
        assert m1.digest() != m2.digest()

    def test_artifact_digest_is_set(self):
        m = _sample_manifest()
        assert m.candidate.artifact_digest.startswith("sha256:")
        assert len(m.candidate.artifact_digest) == 71  # sha256: + 64 hex chars


# ---------------------------------------------------------------------------
# Unavailable data
# ---------------------------------------------------------------------------


class TestUnavailableData:
    def test_current_production_can_be_empty(self):
        m = _sample_manifest()
        assert m.current_production.image_digest is None
        assert m.current_production.revision is None

    def test_scan_can_be_none(self):
        m = _sample_manifest()
        assert m.verification.scan_passed is None

    def test_sbom_can_be_none(self):
        m = _sample_manifest()
        assert m.verification.sbom_generated is None


# ---------------------------------------------------------------------------
# Change summary
# ---------------------------------------------------------------------------


class TestChangeSummary:
    def test_default_infrastructure_change(self):
        m = _sample_manifest()
        assert m.change_summary.infrastructure_change == "backend image only"

    def test_migration_detected(self):
        m = _sample_manifest(database_migration=True)
        assert m.change_summary.database_migration is True

    def test_risk_level_default(self):
        m = _sample_manifest()
        assert m.change_summary.risk_level == "low"

    def test_rollback_summary_present(self):
        m = _sample_manifest()
        assert "revision" in m.change_summary.rollback_summary.lower()


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_manifest_is_frozen(self):
        m = _sample_manifest()
        with pytest.raises(AttributeError):
            m.commit_sha = "x" * 40  # type: ignore[misc]

    def test_candidate_is_frozen(self):
        m = _sample_manifest()
        with pytest.raises(AttributeError):
            m.candidate.image_digest = "sha256:new"  # type: ignore[misc]

    def test_verification_is_frozen(self):
        m = _sample_manifest()
        with pytest.raises(AttributeError):
            m.verification.ci_passed = False  # type: ignore[misc]
