"""Structural safety tests for the passwordless backend release workflow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "backend-release.yml"
TERRAFORM_MAIN = ROOT / "infra" / "terraform" / "main.tf"
DOCKERFILE = ROOT / "Dockerfile"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


class TestReleaseSelection:
    def test_runs_after_successful_master_ci_or_manual_dispatch(self, workflow):
        on_block = workflow.get("on") or workflow.get(True)
        assert on_block["workflow_run"]["workflows"] == ["CI"]
        assert on_block["workflow_run"]["branches"] == ["master"]
        assert "workflow_dispatch" in on_block
        condition = workflow["jobs"]["scope"]["if"]
        for binding in ("conclusion == 'success'", "event == 'push'", "github.repository"):
            assert binding in condition

    def test_release_is_disabled_until_owner_setup_is_complete(self, workflow):
        assert "BACKEND_RELEASE_ENABLED == 'true'" in workflow["jobs"]["scope"]["if"]

    def test_stale_master_is_refused_before_build_and_after_approval(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert text.count("master moved") == 2
        assert "git ls-remote origin refs/heads/master" in text
        assert 'gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/master"' in text

    def test_manual_dispatch_requires_successful_ci_for_exact_sha(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "Manual release requires a successful push CI run" in text
        assert '.head_sha == $sha and .event == "push"' in text

    def test_backend_path_filter_exists(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        for path in ("app/backend/*", "tools/release/*", "infra/terraform/*", "Dockerfile"):
            assert path in text


class TestCredentialBoundaries:
    def test_build_and_deploy_use_oidc(self, workflow):
        for job_name in ("build", "deploy"):
            assert workflow["jobs"][job_name]["permissions"]["id-token"] == "write"
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "client-id:" in text
        assert "tenant-id:" in text
        assert "subscription-id:" in text

    def test_static_azure_and_registry_passwords_are_absent(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        for forbidden in ("AZURE_CREDENTIALS", "ACR_USERNAME", "ACR_PASSWORD", "creds:"):
            assert forbidden not in text

    def test_distinct_build_and_deploy_identities_are_used(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "AZURE_BUILD_CLIENT_ID" in text
        assert "AZURE_DEPLOY_CLIENT_ID" in text

    def test_deploy_job_is_human_gated_and_checks_out_no_source(self, workflow):
        deploy = workflow["jobs"]["deploy"]
        assert deploy["environment"]["name"] == "production"
        assert all("checkout" not in step.get("uses", "") for step in deploy["steps"])

    def test_deploy_credential_is_requested_after_manifest_checks(self, workflow):
        names = [step["name"] for step in workflow["jobs"]["deploy"]["steps"]]
        assert names.index(
            "Verify the release binding before credentials are issued"
        ) < names.index("Sign in to Azure with the approval-bound deploy identity")


class TestReleaseEvidence:
    def test_workflow_invokes_the_real_manifest_and_risk_code(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "python3 -m tools.release.cli create" in text
        assert "Generate deterministic release evidence" in text
        assert "approval-summary.md" in text

    def test_manifest_is_bound_to_run_commit_and_digest(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        for field in (
            'manifest.get("workflow_run_id")',
            'manifest.get("commit_sha")',
            'candidate.get("image_digest")',
            'candidate.get("artifact_digest", "")',
        ):
            assert field in text

    def test_release_identity_mismatch_fails(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert '"release_sha": sys.argv[1]' in text
        assert 'expected_image="$ACR_LOGIN_SERVER/firstroll-api@$EXPECTED_DIGEST"' in text
        assert 'test "$deployed_image" = "$expected_image"' in text
        assert "::warning::Release SHA mismatch" not in text

    def test_commit_identity_is_baked_into_the_candidate(self):
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        dockerfile_text = DOCKERFILE.read_text(encoding="utf-8")
        assert '--build-arg "FIRSTROLL_RELEASE_SHA=$COMMIT_SHA"' in workflow_text
        assert 'ARG FIRSTROLL_RELEASE_SHA=""' in dockerfile_text
        assert "FIRSTROLL_RELEASE_SHA=$FIRSTROLL_RELEASE_SHA" in dockerfile_text


class TestDeploymentSafety:
    def test_candidate_is_deployed_by_digest(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "firstroll-api@$IMAGE_DIGEST" in text
        assert ":latest" not in text

    def test_exact_revision_health_is_checked(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "az containerapp revision show" in text
        assert '"Healthy"' in text
        assert '"Running"' in text

    def test_post_deploy_failure_requests_rollback(self, workflow):
        rollback = next(
            step
            for step in workflow["jobs"]["deploy"]["steps"]
            if step["name"].startswith("Roll back")
        )
        assert "failure()" in rollback["if"]
        assert "steps.rollout.outputs.attempted == 'true'" in rollback["if"]
        assert "PREVIOUS_IMAGE" in rollback["run"]

    def test_pending_release_is_not_cancelled_by_a_new_run(self, workflow):
        assert workflow["concurrency"]["cancel-in-progress"] is False

    def test_all_external_actions_are_pinned(self, workflow):
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if uses:
                    assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", uses), (job_name, uses)


class TestTerraformLeastPrivilege:
    def test_two_oidc_identities_have_distinct_subjects(self):
        text = TERRAFORM_MAIN.read_text(encoding="utf-8")
        assert 'subject   = "repo:${var.github_repository}:ref:refs/heads/master"' in text
        assert (
            'subject   = "repo:${var.github_repository}:environment:production"' in text
        )
        assert 'issuer    = "https://token.actions.githubusercontent.com"' in text

    def test_build_and_deploy_roles_are_narrowly_scoped(self):
        text = TERRAFORM_MAIN.read_text(encoding="utf-8")
        assert 'role_definition_name             = "AcrPush"' in text
        assert 'role_definition_name             = "Reader"' in text
        assert 'role_definition_name             = "Contributor"' in text
        assert "scope                            = azurerm_container_app.api[0].id" in text
        assert "ignore_changes = [template[0].container[0].image]" in text


class TestHealthEndpointReleaseIdentity:
    def test_health_can_report_exact_release_identity(self):
        content = (ROOT / "app" / "backend" / "main.py").read_text(encoding="utf-8")
        assert "FIRSTROLL_RELEASE_SHA" in content
        assert "FIRSTROLL_RELEASE_DIGEST" in content
        assert 'result["release_sha"]' in content
        assert 'result["release_digest"]' in content
