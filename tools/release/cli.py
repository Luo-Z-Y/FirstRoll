"""Deterministic command-line integration for the backend release workflow."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from tools.release.manifest import build_manifest, manifest_from_json, validate_manifest
from tools.release.risk import classify_risk
from tools.release.summary import generate_full_approval_view


MIGRATION_PREFIXES = (
    "database/migrations/",
    "supabase/migrations/",
    "migrations/",
    "alembic/",
)


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _changed_files(base_ref: str, commit_sha: str) -> list[str]:
    raw = subprocess.run(
        ["git", "diff", "--name-only", "-z", base_ref, commit_sha, "--"],
        check=True,
        capture_output=True,
    ).stdout
    return sorted(path.decode("utf-8") for path in raw.split(b"\0") if path)


def _diff_contents(base_ref: str, commit_sha: str, changed_files: list[str]) -> dict[str, str]:
    return {
        path: _git(
            "diff",
            "--no-ext-diff",
            "--unified=0",
            base_ref,
            commit_sha,
            "--",
            path,
        )
        for path in changed_files
    }


def _release_description(changed_files: list[str]) -> list[str]:
    areas: list[str] = []
    rules = (
        ("app/backend/", "Backend application behaviour changed."),
        ("supabase/migrations/", "Database schema or policy changed."),
        ("infra/terraform/", "Azure infrastructure definition changed."),
        ("Dockerfile", "Production container definition changed."),
        ("tools/release/", "Release verification logic changed."),
        (".github/workflows/backend-release.yml", "Backend delivery workflow changed."),
    )
    for prefix, description in rules:
        if any(path == prefix or path.startswith(prefix) for path in changed_files):
            areas.append(description)
    return areas


def _pull_request_details(commit_sha: str) -> tuple[int | None, str | None, str | None]:
    subject = _git("log", "-1", "--format=%s", commit_sha).strip()
    import re

    match = re.search(r"#(\d+)", subject)
    if not match:
        return None, None, None
    number = int(match.group(1))
    title = re.sub(r"^Merge pull request #\d+ from \S+\s*", "", subject).strip()
    return number, title or subject, f"https://github.com/Luo-Z-Y/FirstRoll/pull/{number}"


def create_manifest(arguments: argparse.Namespace) -> int:
    changed_files = _changed_files(arguments.base_ref, arguments.commit_sha)
    diffs = _diff_contents(arguments.base_ref, arguments.commit_sha, changed_files)
    migration_files = [path for path in changed_files if path.startswith(MIGRATION_PREFIXES)]
    terraform_files = [
        path
        for path in changed_files
        if path.startswith("infra/terraform/") and path.endswith(".tf")
    ]
    risk = classify_risk(
        changed_files=changed_files,
        diff_contents=diffs,
        ci_passed=True,
        container_tests_passed=True,
        database_migration=bool(migration_files),
        infrastructure_change=bool(terraform_files),
    )

    pr_number, pr_title, pr_url = _pull_request_details(arguments.commit_sha)
    release_title = pr_title or f"Release {arguments.commit_sha[:7]}"
    manifest = build_manifest(
        repository=arguments.repository,
        environment=arguments.environment,
        workflow_run_id=arguments.workflow_run_id,
        commit_sha=arguments.commit_sha,
        branch="master",
        pr_number=pr_number,
        pr_title=pr_title,
        pr_url=pr_url,
        image_repository=arguments.image_repository,
        image_tag=arguments.commit_sha,
        image_digest=arguments.image_digest,
        ci_passed=True,
        container_tests_passed=True,
        scan_passed=None,
        sbom_generated=None,
        terraform_plan_available=False if terraform_files else None,
        release_title=release_title,
        user_visible_changes=_release_description(changed_files),
        database_migration=bool(migration_files),
        migration_files=migration_files,
        infrastructure_change=(
            "the backend image and Terraform-managed Azure infrastructure"
            if terraform_files
            else "the backend image only"
        ),
        terraform_changed_files=terraform_files,
        risk_level=risk.level,
        risk_reasons=risk.reasons,
        current_image_digest=arguments.current_image_digest or None,
        current_revision=arguments.current_revision or None,
    )
    validate_manifest(
        manifest,
        expected_repository=arguments.repository,
        expected_environment=arguments.environment,
        expected_workflow_run_id=arguments.workflow_run_id,
        expected_commit_sha=arguments.commit_sha,
        expected_image_repository=arguments.image_repository,
        expected_image_digest=arguments.image_digest,
    )

    output_directory = Path(arguments.output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "manifest.json").write_text(manifest.to_json() + "\n", encoding="utf-8")
    (output_directory / "approval-summary.md").write_text(
        generate_full_approval_view(manifest), encoding="utf-8"
    )
    if not risk.allows_approval:
        raise RuntimeError("Release risk is blocked; no deployable manifest was produced")
    return 0


def validate_file(arguments: argparse.Namespace) -> int:
    manifest = manifest_from_json(Path(arguments.manifest).read_text(encoding="utf-8"))
    validate_manifest(
        manifest,
        expected_repository=arguments.repository,
        expected_environment=arguments.environment,
        expected_workflow_run_id=arguments.workflow_run_id,
        expected_commit_sha=arguments.commit_sha,
        expected_image_repository=arguments.image_repository,
        expected_image_digest=arguments.image_digest,
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create release evidence from Git and CI facts")
    create.add_argument("--repository", required=True)
    create.add_argument("--environment", default="production")
    create.add_argument("--workflow-run-id", required=True, type=int)
    create.add_argument("--commit-sha", required=True)
    create.add_argument("--base-ref", required=True)
    create.add_argument("--image-repository", default="firstroll-api")
    create.add_argument("--image-digest", required=True)
    create.add_argument("--current-image-digest", default="")
    create.add_argument("--current-revision", default="")
    create.add_argument("--output-directory", default="release-manifest")
    create.set_defaults(handler=create_manifest)

    validate = commands.add_parser("validate", help="Validate an existing manifest")
    validate.add_argument("manifest")
    validate.add_argument("--repository", required=True)
    validate.add_argument("--environment", default="production")
    validate.add_argument("--workflow-run-id", required=True, type=int)
    validate.add_argument("--commit-sha", required=True)
    validate.add_argument("--image-repository", default="firstroll-api")
    validate.add_argument("--image-digest", required=True)
    validate.set_defaults(handler=validate_file)
    return root


def main() -> int:
    arguments = parser().parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
