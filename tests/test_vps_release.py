"""Structural and behavioural tests for the single-server (VPS) release path."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from tools.release import protocol, vps


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
WORKFLOW_PATH = WORKFLOWS / "vps-release.yml"
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")
CI = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
STACK = ROOT / "infra" / "vps"
COMPOSE = yaml.safe_load((STACK / "docker-compose.yml").read_text(encoding="utf-8"))
CADDYFILE = (STACK / "Caddyfile").read_text(encoding="utf-8")
ENV_EXAMPLE = (STACK / ".env.example").read_text(encoding="utf-8")
DEPLOY = (STACK / "deploy.sh").read_text(encoding="utf-8")
BOOTSTRAP = (STACK / "bootstrap.sh").read_text(encoding="utf-8")
ACTION_REFERENCE = re.compile(r"^\s*(?:-\s+)?uses:\s+([^@\s]+)@([^\s#]+)", re.MULTILINE)
FULL_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
COMMIT = "a" * 40
IMAGE_DIGEST = "sha256:" + "b" * 64


def load_workflow(text: str) -> dict:
    return yaml.safe_load(text)


def step(workflow: dict, job: str, name: str) -> dict:
    return next(item for item in workflow["jobs"][job]["steps"] if item.get("name") == name)


def env_values(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def build_site(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "assets").mkdir(exist_ok=True)
    for name in protocol.REQUIRED_FILES | {"assets/favicon.svg"}:
        (directory / name).write_text(f"// {name}\n", encoding="utf-8")
    return directory


def sealed(tmp_path: Path, **overrides) -> tuple[dict, Path]:
    site = build_site(tmp_path / "dist")
    arguments = {
        "commit": COMMIT,
        "run_id": 42,
        "attempt": 1,
        "image": vps.expected_image(COMMIT),
        "image_digest": IMAGE_DIGEST,
    }
    arguments.update(overrides)
    receipt = vps.prepare(site, **arguments)
    return receipt, site


class FakeClient:
    """Serves a sealed site and API answers from memory for verification tests."""

    def __init__(self, receipt: dict, site: Path, *, release_sha: str = COMMIT):
        self.receipt = receipt
        self.site = site
        self.release_sha = release_sha
        self.hidden_status = 404
        self.cors_origin = vps.SITE
        self.requests: list[str] = []

    def get(self, url: str) -> bytes:
        self.requests.append(url)
        path = url.split("?", 1)[0]
        if path == f"{vps.API}/api/health":
            return json.dumps({"status": "ok", "release_sha": self.release_sha}).encode()
        if path.startswith(vps.API + "/"):
            return b"{}"
        name = path[len(vps.SITE) + 1 :]
        if name == "release.json":
            return protocol.canonical(self.receipt)
        return (self.site / name).read_bytes()

    def status(self, url: str) -> int:
        self.requests.append(url)
        return self.hidden_status

    def preflight(self, url: str, origin: str) -> str | None:
        self.requests.append(url)
        return self.cors_origin


class TestWorkflowPolicy:
    def test_runs_only_after_successful_master_ci_or_manual_dispatch(self):
        workflow = load_workflow(WORKFLOW)
        trigger = workflow.get("on") or workflow[True]
        assert trigger["workflow_run"]["workflows"] == ["CI"]
        assert trigger["workflow_run"]["branches"] == ["master"]
        assert "workflow_dispatch" in trigger
        assert "\n  pull_request:\n" not in WORKFLOW
        condition = workflow["jobs"]["build"]["if"]
        assert "vars.VPS_RELEASE_ENABLED == 'true'" in condition
        for binding in (
            "workflow_run.conclusion == 'success'",
            "workflow_run.event == 'push'",
            "workflow_run.head_branch == 'master'",
            "workflow_run.head_repository.full_name == github.repository",
        ):
            assert binding in condition
        assert (
            "Manual release requires a successful push CI run for the exact master SHA" in WORKFLOW
        )

    def test_actions_are_github_owned_and_pinned_to_full_commits(self):
        references = ACTION_REFERENCE.findall(WORKFLOW)
        assert references
        assert all(owner.startswith("actions/") for owner, _ in references)
        assert all(FULL_COMMIT_SHA.fullmatch(sha) for _, sha in references)
        assert "persist-credentials: false" in WORKFLOW
        assert "permissions:\n  contents: read" in WORKFLOW

    def test_build_job_has_no_production_credential(self):
        build_job, deploy_job = WORKFLOW.split("\n  deploy:\n", maxsplit=1)
        assert "secrets." not in build_job
        assert "packages: write" in build_job
        assert "docker logout ghcr.io" in build_job
        assert "./tools/build_web.sh" in build_job
        assert "python3 -m tools.release.vps prepare" in build_job
        assert "actions/upload-artifact@" in build_job
        assert "retention-days: 90" in build_job
        assert "needs: build" in deploy_job
        assert "environment:\n      name: production" in deploy_job
        assert "artifact-ids: ${{ needs.build.outputs.artifact-id }}" in deploy_job

    def test_deploy_job_verifies_before_the_ssh_key_exists(self):
        workflow = load_workflow(WORKFLOW)
        steps = workflow["jobs"]["deploy"]["steps"]
        names = [item["name"] for item in steps]
        assert not any("checkout@" in item.get("uses", "") for item in steps)
        assert not any(
            "npm install" in item.get("run", "") or "pip install" in item.get("run", "")
            for item in steps
        )
        key_step = names.index("Prepare the pinned SSH identity")
        for name in (
            "Fetch approved release control modules",
            "Verify the receipt, site archive and approval expiry",
            "Refuse a stale revision after approval",
            "Check required production configuration",
        ):
            assert names.index(name) < key_step
        fetch = step(workflow, "deploy", "Fetch approved release control modules")
        assert "for module in protocol vps" in fetch["run"]
        assert "?ref=$EXPECTED_SHA" in fetch["run"]
        verify = step(workflow, "deploy", "Verify the receipt, site archive and approval expiry")
        assert "--archive vps-release/site.tar.gz" in verify["run"]
        assert "--expected-digest" in verify["run"]
        assert "--image-digest" in verify["run"]
        identity = step(workflow, "deploy", "Prepare the pinned SSH identity")
        for setting in ("StrictHostKeyChecking yes", "IdentitiesOnly yes", "BatchMode yes"):
            assert setting in identity["run"]
        assert "known_hosts" in identity["run"]
        assert "secrets.VPS_SSH_PRIVATE_KEY" in identity["env"]["VPS_SSH_PRIVATE_KEY"]

    def test_approval_refuses_a_moved_master(self):
        freshness = step(load_workflow(WORKFLOW), "deploy", "Refuse a stale revision after approval")
        assert "git/ref/heads/master" in freshness["run"]
        assert '"$current_master_sha" != "$EXPECTED_SHA"' in freshness["run"]
        assert "exit 1" in freshness["run"]
        assert load_workflow(WORKFLOW)["concurrency"]["cancel-in-progress"] is False

    def test_release_is_by_digest_and_failure_rolls_back(self):
        workflow = load_workflow(WORKFLOW)
        rollout = step(workflow, "deploy", "Release on the server")
        assert "deploy.sh release '$COMMIT_SHA' '$IMAGE_DIGEST'" in rollout["run"]
        rollback = step(workflow, "deploy", "Roll back after failed post-deployment verification")
        assert "failure()" in rollback["if"]
        assert "steps.rollout.outcome == 'success'" in rollback["if"]
        assert "deploy.sh rollback" in rollback["run"]
        assert "python3 -m tools.release.vps health" in rollback["run"]
        live = step(workflow, "deploy", "Verify the live site and API identity")
        assert "python3 -m tools.release.vps live" in live["run"]
        assert not any(
            item.get("continue-on-error") for item in workflow["jobs"]["deploy"]["steps"]
        )

    @pytest.mark.parametrize("current,expected_code", [(COMMIT, 0), ("b" * 40, 1)])
    def test_post_approval_script_refuses_moved_master(self, tmp_path, current, expected_code):
        gh = tmp_path / "gh"
        gh.write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_MASTER"\n')
        gh.chmod(0o755)
        env = {
            **os.environ,
            "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
            "EXPECTED_SHA": COMMIT,
            "FAKE_MASTER": current,
            "GITHUB_REPOSITORY": "Luo-Z-Y/FirstRoll",
        }
        script = step(load_workflow(WORKFLOW), "deploy", "Refuse a stale revision after approval")
        result = subprocess.run(["bash", "-c", script["run"]], env=env, capture_output=True)
        assert result.returncode == expected_code


class TestServerStack:
    def test_api_is_private_behind_caddy_and_deployed_by_digest(self):
        api = COMPOSE["services"]["api"]
        assert api["image"].startswith(f"{vps.IMAGE_REPOSITORY}@${{FIRSTROLL_IMAGE_DIGEST")
        assert "ports" not in api
        assert api["expose"] == ["10000"]
        assert api["env_file"] == ".env"
        assert api["restart"] == "unless-stopped"
        assert api["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in api["security_opt"]
        assert api["healthcheck"]["test"][0] == "CMD"
        assert "resources" in api["deploy"]

    def test_caddy_owns_the_public_ports_and_reads_releases_read_only(self):
        caddy = COMPOSE["services"]["caddy"]
        assert re.fullmatch(r"caddy:\d+\.\d+\.\d+", caddy["image"])
        assert set(caddy["ports"]) == {"80:80", "443:443", "443:443/udp"}
        assert "./releases:/srv/releases:ro" in caddy["volumes"]
        assert "./Caddyfile:/etc/caddy/Caddyfile:ro" in caddy["volumes"]
        assert caddy["restart"] == "unless-stopped"
        for service in COMPOSE["services"].values():
            assert service["logging"]["options"]["max-size"] == "10m"
            assert not service.get("privileged")

    def test_caddyfile_serves_the_current_release_with_the_static_cache_policy(self):
        assert "root * /srv/releases/current" in CADDYFILE
        assert 'header /release.json Cache-Control "no-store"' in CADDYFILE
        assert 'header /assets/* Cache-Control "no-cache, must-revalidate"' in CADDYFILE
        assert "reverse_proxy api:10000" in CADDYFILE
        assert "file_server" in CADDYFILE
        for placeholder in (
            "{$FIRSTROLL_SITE_DOMAIN}",
            "{$FIRSTROLL_API_DOMAIN}",
            "{$CADDY_ACME_EMAIL}",
        ):
            assert placeholder in CADDYFILE

    def test_environment_template_keeps_the_public_boundary_and_no_secret_values(self):
        values = env_values(ENV_EXAMPLE)
        assert values["FIRSTROLL_PUBLIC_MODE"] == "true"
        assert values["FIRSTROLL_VIDEO_ANALYSIS_ENABLED"] == "false"
        assert values["FIRSTROLL_DEEP_STUDY_ENABLED"] == "false"
        assert values["FIRSTROLL_CORS_ALLOWED_ORIGINS"] == "https://firstroll.app"
        assert values["FIRSTROLL_SITE_DOMAIN"] == "firstroll.app"
        assert values["FIRSTROLL_API_DOMAIN"] == "api.firstroll.app"
        assert values["SUPABASE_PUBLISHABLE_KEY"].startswith("sb_publishable_")
        for secret in ("DEEPSEEK_API_KEY", "TMDB_BEARER_TOKEN", "YOUTUBE_API_KEY"):
            assert values[secret] == ""
        assert re.fullmatch(r"sha256:0{64}", values["FIRSTROLL_IMAGE_DIGEST"])
        for key in (
            "FIRSTROLL_IMAGE_DIGEST",
            "FIRSTROLL_SITE_DOMAIN",
            "FIRSTROLL_API_DOMAIN",
            "CADDY_ACME_EMAIL",
        ):
            assert f"${{{key}" in (STACK / "docker-compose.yml").read_text(encoding="utf-8")

    def test_ci_validates_the_stack_without_a_server(self):
        assert "shellcheck infra/vps/bootstrap.sh infra/vps/deploy.sh" in CI
        assert "docker compose -f infra/vps/docker-compose.yml config --quiet" in CI
        assert "caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile" in CI
        assert "rm -f infra/vps/.env" in CI

    def test_bootstrap_hardens_the_host_and_refuses_non_root(self):
        for control in (
            "ufw default deny incoming",
            "unattended-upgrades",
            "PasswordAuthentication no",
            "PermitRootLogin prohibit-password",
            "usermod -aG docker",
            "install -m 0600",
        ):
            assert control in BOOTSTRAP
        if os.geteuid() == 0:
            pytest.skip("bootstrap refusal is only observable as a non-root user")
        result = subprocess.run(
            ["bash", str(STACK / "bootstrap.sh")], capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "must run as root" in result.stderr

    @pytest.mark.parametrize(
        ("failure", "expected_calls", "expected_code"),
        [
            ("", ["start", "validate", "reload"], 0),
            ("start", ["start"], 1),
            ("validate", ["start", "validate"], 1),
        ],
    )
    def test_bootstrap_starts_socket_activated_ssh_before_validation(
        self, failure, expected_calls, expected_code
    ):
        # Execute only the SSH service sequence with shell fakes: no system changes,
        # root access or local systemctl/sshd invocation are permitted by this harness.
        start = BOOTSTRAP.index("  systemctl start ssh\n")
        end = BOOTSTRAP.index("  systemctl reload ssh\n", start) + len("  systemctl reload ssh\n")
        harness = r"""
set -e
ssh_runtime_ready=0
systemctl() {
  case "$*" in
    "start ssh")
      printf 'start\n'
      test "$SIMULATED_SSH_FAILURE" != start
      ssh_runtime_ready=1
      ;;
    "reload ssh") printf 'reload\n' ;;
    *) return 99 ;;
  esac
}
sshd() {
  test "$*" = '-t'
  printf 'validate\n'
  test "$ssh_runtime_ready" = 1
  test "$SIMULATED_SSH_FAILURE" != validate
}
"""
        result = subprocess.run(
            ["bash", "-c", harness + BOOTSTRAP[start:end]],
            env={**os.environ, "SIMULATED_SSH_FAILURE": failure},
            capture_output=True,
            text=True,
        )
        assert result.returncode == expected_code, result.stderr
        assert result.stdout.splitlines() == expected_calls


class TestDeployScript:
    def run(self, tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess:
        # An empty PATH entry ahead of the real one guarantees docker is never invoked here.
        env = {**os.environ, "FIRSTROLL_INSTALL_ROOT": str(tmp_path), "PATH": os.environ["PATH"]}
        return subprocess.run(
            ["bash", str(STACK / "deploy.sh"), *arguments],
            env=env,
            capture_output=True,
            text=True,
        )

    def test_usage_without_a_command(self, tmp_path):
        result = self.run(tmp_path)
        assert result.returncode == 2
        assert "deploy.sh release <commit-sha> <image-digest> <site.tar.gz>" in result.stderr

    def test_release_refuses_malformed_identity_before_touching_docker(self, tmp_path):
        archive = tmp_path / "site.tar.gz"
        archive.write_bytes(b"")
        result = self.run(tmp_path, "release", "not-a-sha", IMAGE_DIGEST, str(archive))
        assert result.returncode == 1
        assert "40-character commit SHA" in result.stderr
        result = self.run(tmp_path, "release", COMMIT, "latest", str(archive))
        assert result.returncode == 1
        assert "image digest" in result.stderr
        result = self.run(
            tmp_path, "release", COMMIT, IMAGE_DIGEST, str(tmp_path / "missing.tar.gz")
        )
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_release_requires_the_server_environment_file(self, tmp_path):
        archive = tmp_path / "site.tar.gz"
        archive.write_bytes(b"")
        result = self.run(tmp_path, "release", COMMIT, IMAGE_DIGEST, str(archive))
        assert result.returncode == 1
        assert ".env is missing" in result.stderr

    def test_rollback_refuses_without_a_recorded_previous_release(self, tmp_path):
        (tmp_path / "state").mkdir()
        result = self.run(tmp_path, "rollback")
        assert result.returncode == 1
        assert "no previous release is recorded" in result.stderr

    def test_script_switches_site_only_after_the_api_reports_the_release(self):
        activate = DEPLOY.split("activate() {", 1)[1].split("\n}\n", 1)[0]
        assert activate.index("wait_for_api") < activate.index("point_site")
        assert 'body.get("release_sha") == sys.argv[1]' in DEPLOY
        assert "mv -Tf" in DEPLOY
        assert "--no-same-owner" in DEPLOY


class TestDeploymentFailures:
    """Execute the real shell control flow with Docker replaced by harmless stubs."""

    def run_shell(self, tmp_path, body, **variables):
        definitions = DEPLOY.split("\ncase ${1:-} in", 1)[0]
        return subprocess.run(
            ["bash", "-c", definitions + "\n" + body],
            env={**os.environ, "FIRSTROLL_INSTALL_ROOT": str(tmp_path), **variables},
            capture_output=True,
            text=True,
            timeout=10,
        )

    @pytest.mark.parametrize(
        "failure",
        ["set_digest", "start_api", "wait_for_api", "point_site", "reload_caddy", "write_current"],
    )
    def test_activation_stops_at_each_failed_step(self, tmp_path, failure):
        operations = [
            "set_digest",
            "start_api",
            "wait_for_api",
            "point_site",
            "reload_caddy",
            "write_current",
        ]
        stubs = "\n".join(
            f'{name}() {{ echo {name}; test "$FAIL_AT" != {name}; }}' for name in operations
        )
        result = self.run_shell(
            tmp_path,
            stubs + "\nif activate a b c; then echo false-success; exit 0; else exit 7; fi",
            FAIL_AT=failure,
        )
        assert result.returncode == 7
        assert result.stdout.splitlines() == operations[: operations.index(failure) + 1]

    def test_failed_image_pull_does_not_start_services(self, tmp_path):
        result = self.run_shell(
            tmp_path,
            'docker() { echo "$*"; return 1; }\nif start_api; then exit 0; else exit 7; fi',
        )
        assert result.returncode == 7
        assert "pull --quiet api" in result.stdout
        assert "up -d" not in result.stdout

    def test_failed_symlink_creation_does_not_move_it(self, tmp_path):
        (tmp_path / "releases" / "site-test").mkdir(parents=True)
        result = self.run_shell(
            tmp_path,
            "ln() { return 1; }\nmv() { echo wrong-move; }\n"
            "if point_site site-test; then exit 0; else exit 7; fi",
        )
        assert result.returncode == 7
        assert "wrong-move" not in result.stdout

    def test_failed_environment_rewrite_preserves_the_original(self, tmp_path):
        original = "FIRSTROLL_IMAGE_DIGEST=old\nPRIVATE_SETTING=preserve-me\n"
        (tmp_path / ".env").write_text(original)
        result = self.run_shell(
            tmp_path,
            "awk() { return 1; }\nif set_digest new; then exit 0; else exit 7; fi",
        )
        assert result.returncode == 7
        assert (tmp_path / ".env").read_text() == original
        assert list(tmp_path.glob(".env.*")) == []

    def transaction(
        self, tmp_path, *, previous=False, failure="", recovery_failure=False, same_sha=False
    ):
        releases = tmp_path / "releases"
        state = tmp_path / "state"
        releases.mkdir()
        state.mkdir()
        old_site = f"site-{COMMIT}" if same_sha else "site-old" if previous else "site-bootstrap"
        (releases / old_site).mkdir()
        (releases / old_site / "index.html").write_text("previous site")
        (releases / "current").symlink_to(old_site)
        old_digest = "sha256:" + ("c" if previous else "0") * 64
        (tmp_path / ".env").write_text(f"FIRSTROLL_IMAGE_DIGEST={old_digest}\n")
        if previous:
            (state / "current-release").write_text(
                f"{COMMIT if same_sha else 'd' * 40} {old_digest} {old_site}\n"
            )
            (state / "previous-release").write_text("older recorded release\n")
        site = tmp_path / "payload"
        site.mkdir()
        (site / "index.html").write_text("candidate site")
        (site / "release.json").write_text("{}")
        archive = tmp_path / "site.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for path in site.iterdir():
                tar.add(path, arcname=path.name)
        stubs = r"""
# No real Docker calls, waits, pruning or platform-specific symlink moves occur.
docker() { printf '%s\n' "$*" >> "$root/docker-calls"; test "$FAIL_AT" != image_prune; }
prune_sites() { test "$FAIL_AT" != prune_sites; }
write_previous() {
  test "$FAIL_AT" != write_previous || return 1
  write_record "$previous_file" "$@"
}
start_api() {
  printf 'start:%s\n' "$(current_digest)" >> "$root/events"
  if [ "$(current_digest)" = "$OLD_DIGEST" ] && [ "$RECOVERY_FAILURE" = 1 ]; then return 1; fi
  test "$FAIL_AT" != start_api
}
wait_for_api() { test "$FAIL_AT" != wait_for_api || test "$1" != "$NEW_SHA"; }
point_site() { ln -sfn "$1" "$releases/current"; }
reload_caddy() {
  if [ "$FAIL_AT" = reload_caddy ] && [ "$(current_digest)" != "$OLD_DIGEST" ]; then return 1; fi
}
release "$NEW_SHA" "$NEW_DIGEST" "$ARCHIVE"
"""
        result = self.run_shell(
            tmp_path,
            stubs,
            NEW_SHA=COMMIT,
            NEW_DIGEST=IMAGE_DIGEST,
            OLD_DIGEST=old_digest,
            ARCHIVE=str(archive),
            FAIL_AT=failure,
            RECOVERY_FAILURE=str(int(recovery_failure)),
        )
        return result, old_site, old_digest

    @pytest.mark.parametrize("failure", ["start_api", "wait_for_api", "reload_caddy"])
    def test_first_activation_failure_restores_bootstrap_without_pulling_zero_digest(
        self, tmp_path, failure
    ):
        result, old_site, old_digest = self.transaction(tmp_path, failure=failure)
        assert result.returncode != 0
        assert (tmp_path / "releases" / "current").readlink() == Path(old_site)
        assert old_digest in (tmp_path / ".env").read_text()
        assert not (tmp_path / "state" / "current-release").exists()
        assert not (tmp_path / "state" / "previous-release").exists()
        assert "stop api" in (tmp_path / "docker-calls").read_text()
        assert old_digest not in (tmp_path / "events").read_text()
        assert list((tmp_path / "releases").glob(f"site-{COMMIT}.*")) == []

    @pytest.mark.parametrize("failure", ["wait_for_api", "reload_caddy", "write_previous"])
    def test_later_failure_restores_exact_previous_release(self, tmp_path, failure):
        result, old_site, old_digest = self.transaction(tmp_path, previous=True, failure=failure)
        assert result.returncode != 0
        assert (tmp_path / "releases" / "current").readlink() == Path(old_site)
        assert (
            tmp_path / "state" / "current-release"
        ).read_text() == f"{'d' * 40} {old_digest} {old_site}\n"
        assert (tmp_path / "state" / "previous-release").read_text() == "older recorded release\n"
        assert (tmp_path / "events").read_text().splitlines()[-1] == f"start:{old_digest}"

    def test_failed_recovery_retains_candidate_and_reports_manual_action(self, tmp_path):
        result, old_site, _ = self.transaction(
            tmp_path, previous=True, failure="reload_caddy", recovery_failure=True
        )
        assert result.returncode != 0
        assert "Recovery also failed" in result.stderr
        assert (tmp_path / "releases" / "current").readlink() == Path(old_site)
        assert len(list((tmp_path / "releases").glob(f"site-{COMMIT}.*"))) == 1

    def test_success_records_new_release_and_keeps_old_site(self, tmp_path):
        result, old_site, old_digest = self.transaction(tmp_path, previous=True)
        assert result.returncode == 0, result.stderr
        active = (tmp_path / "releases" / "current").readlink()
        assert str(active).startswith(f"site-{COMMIT}.")
        assert (
            tmp_path / "state" / "current-release"
        ).read_text() == f"{COMMIT} {IMAGE_DIGEST} {active}\n"
        assert (
            tmp_path / "state" / "previous-release"
        ).read_text() == f"{'d' * 40} {old_digest} {old_site}\n"
        assert (tmp_path / "releases" / old_site / "index.html").read_text() == "previous site"

    def test_workflow_does_not_roll_back_an_already_recovered_rollout(self):
        rollback = step(
            load_workflow(WORKFLOW), "deploy", "Roll back after failed post-deployment verification"
        )
        assert "steps.rollout.outcome == 'success'" in rollback["if"]
        assert "attempted" not in rollback["if"]

    def test_same_commit_retry_never_deletes_the_active_site(self, tmp_path):
        result, old_site, _ = self.transaction(tmp_path, previous=True, same_sha=True)
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "releases" / old_site / "index.html").read_text() == "previous site"
        assert str((tmp_path / "releases" / "current").readlink()) != old_site

    @pytest.mark.parametrize("failure", ["prune_sites", "image_prune"])
    def test_housekeeping_failure_still_allows_live_verification(self, tmp_path, failure):
        result, _, _ = self.transaction(tmp_path, previous=True, failure=failure)
        assert result.returncode == 0, result.stderr
        assert "Warning:" in result.stderr
        assert "Released " in result.stdout
        assert (tmp_path / "state" / "current-release").read_text().startswith(COMMIT)


class TestReleaseTooling:
    def test_prepare_seals_site_inventory_and_image_identity(self, tmp_path, capsys):
        receipt, site = sealed(tmp_path)
        written = protocol.read_json(site / "release.json")
        assert written == receipt
        assert receipt["component"] == "vps"
        assert receipt["image"] == f"{vps.IMAGE_REPOSITORY}:{COMMIT}"
        assert receipt["image_digest"] == IMAGE_DIGEST
        assert protocol.REQUIRED_FILES.issubset(receipt["files"])
        assert "release.json" not in receipt["files"]
        assert receipt["receipt_digest"] == protocol.receipt_digest(receipt)
        assert protocol.timestamp(receipt["expires_at"]) - protocol.timestamp(
            receipt["created_at"]
        ) == timedelta(days=7)
        vps.validate(receipt, commit=COMMIT, run_id=42, attempt=1, image_digest=IMAGE_DIGEST)
        assert "single-server release is ready" in capsys.readouterr().out

    @pytest.mark.parametrize(
        "overrides",
        [
            {"commit": "abc"},
            {"image_digest": "sha256:short"},
            {"image": "ghcr.io/someone-else/firstroll-api:" + COMMIT},
            {"run_id": 0},
        ],
    )
    def test_prepare_rejects_invalid_bindings(self, tmp_path, overrides):
        with pytest.raises(ValueError):
            sealed(tmp_path, **overrides)

    def test_validate_rejects_tampering_and_mismatched_bindings(self, tmp_path):
        receipt, _ = sealed(tmp_path)
        with pytest.raises(ValueError):
            vps.validate(receipt, commit="b" * 40)
        with pytest.raises(ValueError):
            vps.validate(receipt, image_digest="sha256:" + "c" * 64)
        with pytest.raises(ValueError):
            vps.validate(receipt, expected_digest="sha256:" + "d" * 64)
        edited = dict(receipt, image="ghcr.io/other/firstroll-api:" + COMMIT)
        edited["receipt_digest"] = protocol.receipt_digest(edited)
        with pytest.raises(ValueError):
            vps.validate(edited)
        forged = dict(receipt, files={**receipt["files"], "assets/app.js": "sha256:" + "e" * 64})
        forged["receipt_digest"] = protocol.receipt_digest(forged)
        with pytest.raises(ValueError):
            vps.validate(forged)

    def test_validate_enforces_the_seven_day_approval_window(self, tmp_path):
        created = datetime(2026, 9, 28, tzinfo=timezone.utc)
        receipt, _ = sealed(tmp_path, clock=created)
        vps.validate(receipt, clock=created + timedelta(days=6))
        with pytest.raises(ValueError):
            vps.validate(receipt, clock=created + timedelta(days=8))
        vps.validate(receipt, clock=created + timedelta(days=8), fresh=False)

    def test_verify_archive_requires_the_exact_sealed_site(self, tmp_path):
        receipt, site = sealed(tmp_path)
        archive = tmp_path / "site.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(site, arcname=".")
        vps.verify_archive(receipt, archive)
        (site / "assets" / "app.js").write_text("// changed\n", encoding="utf-8")
        tampered = tmp_path / "tampered.tar.gz"
        with tarfile.open(tampered, "w:gz") as tar:
            tar.add(site, arcname=".")
        with pytest.raises(ValueError):
            vps.verify_archive(receipt, tampered)

    def test_verify_live_accepts_the_served_release(self, tmp_path):
        receipt, site = sealed(tmp_path)
        client = FakeClient(receipt, site)
        vps.verify_live(
            receipt, commit=COMMIT, client=client, clock=lambda: 0.0, sleep=lambda _: None
        )
        assert any(url.endswith("/api/contract") for url in client.requests)
        assert any(url.endswith("/openapi.json") for url in client.requests)

    def test_verify_live_fails_closed_on_identity_docs_or_cors(self, tmp_path):
        receipt, site = sealed(tmp_path)
        ticks = iter(range(0, 10_000, 100))

        def run(client: FakeClient) -> None:
            vps.verify_live(
                receipt,
                commit=COMMIT,
                client=client,
                deadline_seconds=1,
                clock=lambda: next(ticks),
                sleep=lambda _: None,
            )

        stale = FakeClient(receipt, site, release_sha="b" * 40)
        with pytest.raises(RuntimeError):
            run(stale)
        exposed = FakeClient(receipt, site)
        exposed.hidden_status = 200
        with pytest.raises(RuntimeError):
            run(exposed)
        permissive = FakeClient(receipt, site)
        permissive.cors_origin = "*"
        with pytest.raises(RuntimeError):
            run(permissive)
        other_site = FakeClient(dict(receipt, release_id="vps-other"), site)
        with pytest.raises(RuntimeError):
            run(other_site)

    def test_live_client_refuses_unapproved_origins(self):
        client = vps.LiveClient()
        with pytest.raises(ValueError):
            client.get("https://example.com/release.json")
        with pytest.raises(ValueError):
            client.status("https://firstroll.app.evil.example/api/health")
