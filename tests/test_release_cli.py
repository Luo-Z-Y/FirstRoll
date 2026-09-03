"""Integration tests for deterministic release evidence creation."""

from __future__ import annotations

import argparse
import json

import pytest

from tools.release import cli
from tools.release.manifest import build_manifest, manifest_from_json, validate_manifest


SHA = "a" * 40
IMAGE_DIGEST = "sha256:" + "b" * 64


def _arguments(tmp_path):
    return argparse.Namespace(
        repository="Luo-Z-Y/FirstRoll",
        environment="production",
        workflow_run_id=123,
        commit_sha=SHA,
        base_ref=f"{SHA}^",
        image_repository="firstroll-api",
        image_digest=IMAGE_DIGEST,
        current_image_digest="sha256:" + "c" * 64,
        current_revision="firstroll-api--0000002",
        output_directory=str(tmp_path),
    )


def test_create_uses_real_risk_result_and_json_escapes_title(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "_changed_files",
        lambda *_: [".github/workflows/backend-release.yml", "app/backend/main.py"],
    )
    monkeypatch.setattr(cli, "_diff_contents", lambda *_: {})
    monkeypatch.setattr(
        cli,
        "_pull_request_details",
        lambda *_: (39, 'Secure "quoted" release', "https://github.com/example/pull/39"),
    )

    assert cli.create_manifest(_arguments(tmp_path)) == 0
    raw = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    manifest = manifest_from_json(raw)
    assert json.loads(raw)["pull_request"]["title"] == 'Secure "quoted" release'
    assert manifest.change_summary.risk_level == "high"
    assert any(
        "release authority" in reason.lower() for reason in manifest.change_summary.risk_reasons
    )
    assert (tmp_path / "approval-summary.md").exists()


def test_validation_rejects_tampered_manifest():
    manifest = build_manifest(
        repository="Luo-Z-Y/FirstRoll",
        environment="production",
        workflow_run_id=123,
        commit_sha=SHA,
        branch="master",
        image_repository="firstroll-api",
        image_tag=SHA,
        image_digest=IMAGE_DIGEST,
        ci_passed=True,
        container_tests_passed=True,
    )
    data = manifest.to_dict()
    data["change_summary"]["release_title"] = "Tampered after sealing"
    tampered = manifest_from_json(json.dumps(data))
    with pytest.raises(ValueError, match="manifest digest"):
        validate_manifest(tampered)


def test_validation_rejects_wrong_release_binding():
    manifest = build_manifest(
        repository="Luo-Z-Y/FirstRoll",
        environment="production",
        workflow_run_id=123,
        commit_sha=SHA,
        branch="master",
        image_repository="firstroll-api",
        image_tag=SHA,
        image_digest=IMAGE_DIGEST,
        ci_passed=True,
        container_tests_passed=True,
    )
    with pytest.raises(ValueError, match="workflow_run_id"):
        validate_manifest(manifest, expected_workflow_run_id=999)


def test_validation_rejects_blocked_risk():
    manifest = build_manifest(
        repository="Luo-Z-Y/FirstRoll",
        environment="production",
        workflow_run_id=123,
        commit_sha=SHA,
        branch="master",
        image_repository="firstroll-api",
        image_tag=SHA,
        image_digest=IMAGE_DIGEST,
        ci_passed=True,
        container_tests_passed=True,
        risk_level="blocked",
    )
    with pytest.raises(ValueError, match="blocks deployment"):
        validate_manifest(manifest)
