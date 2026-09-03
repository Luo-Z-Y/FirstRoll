"""Tests for workflow protections and the approval broker.

Covers: workflow trigger conditions, branch enforcement, environment
declaration, no-checkout in deploy, immutable digest deployment,
no 'latest' tag usage, pinned external actions, and broker behaviour.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from tools.release.authorization import NonceStore, issue_capability
from tools.release.audit import AuditLog
from tools.release.broker import ApprovalBroker, ApprovalRequest


SIGNING_KEY = "test-signing-key-do-not-use-in-production"
WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "backend-release.yml"
)


# ---------------------------------------------------------------------------
# Workflow YAML verification
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow():
    if not WORKFLOW_PATH.exists():
        pytest.skip("backend-release.yml not found")
    with WORKFLOW_PATH.open() as f:
        return yaml.safe_load(f)


class TestWorkflowTrigger:
    def test_triggers_on_workflow_run(self, workflow):
        on_block = workflow.get("on") or workflow.get(True)
        assert "workflow_run" in on_block

    def test_listens_for_ci_completion(self, workflow):
        on_block = workflow.get("on") or workflow.get(True)
        wr = on_block["workflow_run"]
        assert "CI" in wr["workflows"]
        assert "completed" in wr["types"]

    def test_branch_is_master(self, workflow):
        on_block = workflow.get("on") or workflow.get(True)
        wr = on_block["workflow_run"]
        assert "master" in wr["branches"]


class TestBuildJobConditions:
    def test_event_must_be_push(self, workflow):
        build_if = workflow["jobs"]["build"]["if"]
        assert "event == 'push'" in build_if or "event == \\'push\\'" in build_if

    def test_branch_must_be_master(self, workflow):
        build_if = workflow["jobs"]["build"]["if"]
        assert "master" in build_if

    def test_repository_must_match(self, workflow):
        build_if = workflow["jobs"]["build"]["if"]
        assert "github.repository" in build_if

    def test_ci_must_succeed(self, workflow):
        build_if = workflow["jobs"]["build"]["if"]
        assert "success" in build_if


class TestDeployJob:
    def test_declares_production_environment(self, workflow):
        deploy = workflow["jobs"]["deploy"]
        assert deploy["environment"]["name"] == "production"

    def test_depends_on_build(self, workflow):
        deploy = workflow["jobs"]["deploy"]
        assert "build" in deploy["needs"]

    def test_no_checkout_step(self, workflow):
        """The deploy job must not check out repository source code."""
        deploy = workflow["jobs"]["deploy"]
        for step in deploy["steps"]:
            uses = step.get("uses", "")
            assert "checkout" not in uses.lower(), (
                f"Deploy job must not check out code, but found: {uses}"
            )

    def test_deploy_step_uses_digest(self, workflow):
        """Verify that the deployment step references the image by digest."""
        deploy = workflow["jobs"]["deploy"]
        deploy_step = None
        for step in deploy["steps"]:
            if "deploy" in step.get("name", "").lower() and "image" in step.get("name", "").lower():
                deploy_step = step
                break
            # Also check the run content
            run_content = step.get("run", "")
            if "containerapp update" in run_content.lower():
                deploy_step = step
                break
        assert deploy_step is not None, "No deployment step found"
        run = deploy_step.get("run", "")
        assert "IMAGE_DIGEST" in run or "image_digest" in run.lower(), (
            "Deployment must use the immutable image digest"
        )


class TestNoLatestTag:
    def test_workflow_does_not_use_latest_tag(self, workflow):
        """No step should reference or produce a 'latest' tag."""
        raw = WORKFLOW_PATH.read_text()
        # The word "latest" should only appear in comments or documentation,
        # not in actual image tagging commands
        lines = raw.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("echo"):
                continue
            if ":latest" in stripped and "tag" in stripped.lower():
                pytest.fail(f"Line {i} uses ':latest' tag: {stripped}")


class TestPinnedActions:
    def test_all_external_actions_pinned(self, workflow):
        """All uses: references must be pinned to full commit SHAs."""
        for job_name, job in workflow.get("jobs", {}).items():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                if uses and "/" in uses:
                    # Must contain @ followed by a 40-char hex SHA
                    assert "@" in uses, f"Action {uses} in {job_name} is not pinned"
                    sha = uses.split("@")[1].split()[0]  # strip comments
                    assert len(sha) >= 40, (
                        f"Action {uses} in {job_name} is not pinned to a full SHA"
                    )


class TestPermissions:
    def test_contents_read(self, workflow):
        perms = workflow.get("permissions", {})
        assert perms.get("contents") == "read"

    def test_no_write_permissions_at_workflow_level(self, workflow):
        perms = workflow.get("permissions", {})
        for perm, value in perms.items():
            assert value != "write" or perm in ("actions",), (
                f"Unexpected write permission: {perm}: {value}"
            )


# ---------------------------------------------------------------------------
# Broker tests
# ---------------------------------------------------------------------------


def _issue_cap(**overrides):
    defaults = dict(
        signing_key=SIGNING_KEY,
        repository="Luo-Z-Y/FirstRoll",
        environment="production",
        workflow_run_id=123456789,
        commit_sha="a" * 40,
        image_digest="sha256:" + "b" * 64,
        deployment_target="api.firstroll.app",
        manifest_digest="sha256:" + "c" * 64,
        authorizing_user="luo-z-y",
        decision="approve",
    )
    defaults.update(overrides)
    return issue_capability(**defaults)


class TestBrokerApproval:
    def test_valid_approval_accepted(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name
        try:
            broker = ApprovalBroker(
                signing_key=SIGNING_KEY,
                nonce_store=NonceStore(),
                audit_log=AuditLog(log_path),
            )
            cap = _issue_cap()
            request = ApprovalRequest(
                release_id="test-release",
                decision="approve",
                authorization_token=cap.to_token(),
            )
            response = broker.process_approval(request)
            assert response.accepted is True
            assert "123456789" in response.message
        finally:
            os.unlink(log_path)

    def test_replay_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name
        try:
            nonce_store = NonceStore()
            broker = ApprovalBroker(
                signing_key=SIGNING_KEY,
                nonce_store=nonce_store,
                audit_log=AuditLog(log_path),
            )
            cap = _issue_cap()
            request = ApprovalRequest(
                release_id="test-release",
                decision="approve",
                authorization_token=cap.to_token(),
            )
            broker.process_approval(request)
            # Replay
            response = broker.process_approval(request)
            assert response.accepted is False
            assert "already been used" in response.message
        finally:
            os.unlink(log_path)

    def test_wrong_repo_rejected(self):
        broker = ApprovalBroker(
            signing_key=SIGNING_KEY,
            nonce_store=NonceStore(),
            audit_log=AuditLog("/dev/null"),
        )
        cap = _issue_cap(repository="Evil/Repo")
        request = ApprovalRequest(
            release_id="test-release",
            decision="approve",
            authorization_token=cap.to_token(),
        )
        response = broker.process_approval(request)
        assert response.accepted is False
        assert "repository" in response.message.lower()

    def test_malformed_token_rejected(self):
        broker = ApprovalBroker(
            signing_key=SIGNING_KEY,
            nonce_store=NonceStore(),
            audit_log=AuditLog("/dev/null"),
        )
        request = ApprovalRequest(
            release_id="test-release",
            decision="approve",
            authorization_token="not-json",
        )
        response = broker.process_approval(request)
        assert response.accepted is False
        assert "malformed" in response.message.lower()


class TestBrokerAudit:
    def test_audit_event_recorded(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name
        try:
            audit = AuditLog(log_path)
            broker = ApprovalBroker(
                signing_key=SIGNING_KEY,
                nonce_store=NonceStore(),
                audit_log=audit,
            )
            cap = _issue_cap()
            request = ApprovalRequest(
                release_id="test-release",
                decision="approve",
                authorization_token=cap.to_token(),
            )
            broker.process_approval(request)
            events = audit.read_events()
            assert len(events) == 1
            assert events[0].action == "approval_submitted"
            assert events[0].authorizing_user == "luo-z-y"
            assert "explicit authorisation" in events[0].detail.lower()
        finally:
            os.unlink(log_path)

    def test_audit_event_contains_no_secrets(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name
        try:
            audit = AuditLog(log_path)
            broker = ApprovalBroker(
                signing_key=SIGNING_KEY,
                nonce_store=NonceStore(),
                audit_log=audit,
            )
            cap = _issue_cap()
            request = ApprovalRequest(
                release_id="test-release",
                decision="approve",
                authorization_token=cap.to_token(),
            )
            broker.process_approval(request)

            raw = Path(log_path).read_text()
            assert SIGNING_KEY not in raw
            assert "Bearer" not in raw
            assert "private_key" not in raw.lower()
        finally:
            os.unlink(log_path)


# ---------------------------------------------------------------------------
# Health endpoint release identity
# ---------------------------------------------------------------------------


class TestHealthEndpointReleaseIdentity:
    """Verify the health endpoint reports release identity when env vars are set."""

    def test_health_includes_release_sha(self):
        """Verify the health endpoint code includes release_sha logic."""
        main_path = Path(__file__).resolve().parent.parent / "app" / "backend" / "main.py"
        if not main_path.exists():
            pytest.skip("main.py not found")
        content = main_path.read_text()
        assert "FIRSTROLL_RELEASE_SHA" in content
        assert "release_sha" in content

    def test_health_includes_release_digest(self):
        main_path = Path(__file__).resolve().parent.parent / "app" / "backend" / "main.py"
        if not main_path.exists():
            pytest.skip("main.py not found")
        content = main_path.read_text()
        assert "FIRSTROLL_RELEASE_DIGEST" in content
