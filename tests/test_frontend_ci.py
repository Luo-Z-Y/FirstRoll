import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
DEPLOYMENT = (WORKFLOWS / "vps-release.yml").read_text(encoding="utf-8")
BUILD = (ROOT / "tools" / "frontend" / "build.sh").read_text(encoding="utf-8")
DEPENDABOT = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
AGENT_POLICY = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
PULL_REQUEST_TEMPLATE = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
ACTION_REFERENCE = re.compile(r"^\s*(?:-\s+)?uses:\s+[^@\s]+@([^\s#]+)", re.MULTILINE)
FULL_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


def assert_uses_immutable_actions(workflow: str) -> None:
    references = ACTION_REFERENCE.findall(workflow)

    assert references
    assert all(FULL_COMMIT_SHA.fullmatch(reference) for reference in references)


def test_pull_request_ci_has_a_bounded_read_only_token() -> None:
    assert "\n  pull_request:\n" in CI
    assert "permissions:\n  contents: read" in CI
    assert "persist-credentials: false" in CI
    assert "secrets." not in CI
    assert "cancel-in-progress: true" in CI
    assert "timeout-minutes:" in CI
    assert_uses_immutable_actions(CI)


def test_ci_runs_the_complete_hosted_safe_test_suite() -> None:
    assert "run: python -m pytest -q tests" in CI


def test_frontend_dependencies_are_locked_audited_and_script_safe() -> None:
    assert "npm audit --audit-level=high" in CI
    assert "npm audit --audit-level=high" in DEPLOYMENT
    assert "npm ci --include=dev --ignore-scripts" in BUILD
    assert '"lockfileVersion":' in (ROOT / "package-lock.json").read_text(encoding="utf-8")
    assert "package-ecosystem: github-actions" in DEPENDABOT
    assert "package-ecosystem: npm" in DEPENDABOT


def test_agent_workflow_requires_protected_prs_and_human_deployment_approval() -> None:
    agent_policy = " ".join(AGENT_POLICY.split())
    pull_request_template = " ".join(PULL_REQUEST_TEMPLATE.split())

    assert "Never commit or push directly to `master`" in agent_policy
    assert "short-lived branch" in agent_policy
    assert "permanent `local`, `develop`" in agent_policy
    assert "opening a pull request into protected `master`" in agent_policy
    assert "must not approve it, bypass it or weaken the gate" in agent_policy
    assert "directly to `origin/master`" not in agent_policy
    assert "does **not** approve production" in pull_request_template
    assert "separate human approval" in pull_request_template
