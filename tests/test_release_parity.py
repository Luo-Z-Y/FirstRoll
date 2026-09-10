"""Common release-policy tests across both service-specific workflows."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
FILES = ["backend-release.yml", "azure-static-web-apps-salmon-field-03695a010.yml"]


def load(name):
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text())


@pytest.fixture(params=FILES)
def workflow(request):
    return load(request.param)


def step(workflow, name):
    return next(item for item in workflow["jobs"]["deploy"]["steps"] if item["name"] == name)


def test_both_keep_approval_gate_and_active_deployments(workflow):
    assert workflow["jobs"]["deploy"]["environment"]["name"] == "production"
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert "workflow_dispatch" in (workflow.get("on") or workflow[True])
    upload = next(
        s for s in workflow["jobs"]["build"]["steps"] if "upload-artifact@" in s.get("uses", "")
    )
    assert upload["with"]["retention-days"] == 90


def test_shared_policy_is_used_before_any_cloud_credentials(workflow):
    steps = workflow["jobs"]["deploy"]["steps"]
    names = [s["name"] for s in steps]
    fetch = step(workflow, "Fetch approved release control modules")
    verify = step(workflow, "Verify the shared receipt and approval expiry")
    assert "?ref=$EXPECTED_SHA" in fetch["run"]
    assert "for module in protocol frontend" in fetch["run"]
    assert "needs.build.outputs.commit-sha" in fetch["env"]["EXPECTED_SHA"]
    assert "python3 -m tools.release.protocol verify" in verify["run"]
    assert "--expected-digest" in verify["run"]
    assert "needs.build.outputs.run-attempt" in verify["env"]["BUILD_ATTEMPT"]
    first_cloud = min(
        i
        for i, s in enumerate(steps)
        if any(
            provider in s.get("uses", "")
            for provider in ("azure/login@", "Azure/static-web-apps-deploy@")
        )
    )
    for name in (fetch["name"], verify["name"], "Refuse a stale revision after approval"):
        assert names.index(name) < first_cloud
    assert not any("checkout@" in s.get("uses", "") for s in steps)
    assert not any(
        "npm install" in s.get("run", "") or "pip install" in s.get("run", "") for s in steps
    )


def test_common_control_fetch_and_freshness_checks_do_not_diverge():
    backend, frontend = map(load, FILES)
    for name in (
        "Fetch approved release control modules",
        "Refuse a stale revision after approval",
    ):
        assert step(backend, name)["run"] == step(frontend, name)["run"]


@pytest.mark.parametrize("current,expected_code", [("a" * 40, 0), ("b" * 40, 1)])
def test_actual_post_approval_script_refuses_moved_master(
    workflow, tmp_path, current, expected_code
):
    gh = tmp_path / "gh"
    gh.write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_MASTER"\n')
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "EXPECTED_SHA": "a" * 40,
        "FAKE_MASTER": current,
        "GITHUB_REPOSITORY": "Luo-Z-Y/FirstRoll",
    }
    result = subprocess.run(
        ["bash", "-c", step(workflow, "Refuse a stale revision after approval")["run"]],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected_code


def test_frontend_validates_recovery_before_upload_and_preserves_failed_status():
    workflow = load(FILES[1])
    steps = workflow["jobs"]["deploy"]["steps"]
    names = [s["name"] for s in steps]
    assert names.index("Verify the retained rollback package") < names.index(
        "Upload the pre-built frontend"
    )
    recovery = step(workflow, "Restore the verified previous frontend")
    assert "failure()" in recovery["if"]
    assert "steps.rollout.outcome == 'failure'" in recovery["if"]
    assert "steps.rollback-ready.outcome == 'success'" in recovery["if"]
    assert not any(s.get("continue-on-error") for s in steps)
    assert (
        "failure() && steps.rollback.outcome == 'success'"
        in step(workflow, "Verify restored frontend identity and files")["if"]
    )


def test_initial_release_is_an_explicit_manual_choice():
    workflow = load(FILES[1])
    trigger = workflow.get("on") or workflow[True]
    assert trigger["workflow_dispatch"]["inputs"]["allow_initial_release"]["default"] is False
    receipt = next(s for s in workflow["jobs"]["build"]["steps"] if s.get("id") == "receipt")
    assert (
        "github.event_name == 'workflow_dispatch' && inputs.allow_initial_release"
        in receipt["env"]["ALLOW_INITIAL"]
    )


def test_live_release_metadata_is_not_cached():
    import json

    config = json.loads((ROOT / "app/web/staticwebapp.config.json").read_text())
    route = next(r for r in config["routes"] if r["route"] == "/release.json")
    assert route["headers"]["Cache-Control"] == "no-store"
