"""Executable release-boundary tests; no GitHub, Azure or model calls."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import subprocess

import pytest

from tools.release import protocol as p


SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)


@pytest.fixture
def site(tmp_path):
    directory = tmp_path / "site"
    directory.mkdir()
    for name in p.REQUIRED_FILES:
        file = directory / name
        file.parent.mkdir(exist_ok=True)
        file.write_text("fixture:" + name)
    return directory


def frontend_receipt(site, **kwargs):
    files = p.inventory(site)
    return p.create_receipt(
        component="frontend",
        commit=SHA,
        run_id=123,
        attempt=1,
        payload_digest=p.fingerprint(p.canonical(files)),
        files=files,
        bootstrap=True,
        clock=NOW,
        **kwargs,
    )


def backend_receipt():
    return p.create_receipt(
        component="backend",
        commit=SHA,
        run_id=123,
        attempt=1,
        payload_digest=DIGEST,
        evidence_digest=DIGEST,
        clock=NOW,
    )


@pytest.mark.parametrize("component", ["frontend", "backend"])
def test_receipt_roundtrip_and_independent_binding(component, site):
    receipt = frontend_receipt(site) if component == "frontend" else backend_receipt()
    p.validate_receipt(
        json.loads(json.dumps(receipt)),
        component=component,
        commit=SHA,
        run_id=123,
        attempt=1,
        expected_digest=receipt["receipt_digest"],
        clock=NOW,
    )


@pytest.mark.parametrize(
    "binding,value",
    [
        ("commit", "c" * 40),
        ("run_id", 124),
        ("attempt", 2),
        ("component", "frontend"),
        ("expected_digest", DIGEST),
    ],
)
def test_wrong_approval_binding_is_refused(binding, value):
    with pytest.raises(ValueError, match="approved candidate"):
        p.validate_receipt(backend_receipt(), clock=NOW, **{binding: value})


def test_self_rehashed_receipt_does_not_override_build_job_fingerprint():
    original = backend_receipt()
    altered = deepcopy(original)
    altered["payload_digest"] = "sha256:" + "c" * 64
    altered["receipt_digest"] = p.receipt_digest(altered)
    with pytest.raises(ValueError, match="approved candidate"):
        p.validate_receipt(altered, expected_digest=original["receipt_digest"], clock=NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("checks", {"ci": "true", "build": True}),
        ("checks", {"ci": True, "build": False}),
        ("workflow_run_id", True),
        ("risk", "blocked"),
        ("branch", "feature"),
        ("environment", "staging"),
        ("repository", "attacker/FirstRoll"),
        ("schema_version", 999),
        ("payload_digest", "latest"),
    ],
)
def test_unsafe_receipts_fail_even_with_consistent_self_hash(field, value):
    receipt = backend_receipt()
    receipt[field] = value
    receipt["receipt_digest"] = p.receipt_digest(receipt)
    with pytest.raises(ValueError):
        p.validate_receipt(receipt, clock=NOW)


def test_seven_day_approval_window_is_independent_of_rollback_retention():
    receipt = backend_receipt()
    with pytest.raises(ValueError, match="expired"):
        p.validate_receipt(receipt, clock=NOW + timedelta(days=7))
    p.validate_receipt(receipt, clock=NOW + timedelta(days=30), fresh=False)


def test_future_timestamp_is_rejected():
    with pytest.raises(ValueError, match="validity window"):
        p.validate_receipt(backend_receipt(), clock=NOW - timedelta(hours=1))


@pytest.mark.parametrize(
    "body",
    [
        "",
        "<html>unavailable</html>",
        "{}",
        '{"status":"ok"}',
        '{"status":"error","release_sha":"' + SHA + '"}',
        '{"status":"ok","release_sha":"latest"}',
    ],
)
def test_unavailable_or_unversioned_api_does_not_block_recovery_selection(tmp_path, body):
    path = tmp_path / "health.json"
    path.write_text(body)
    assert p.health_commit(path) is None


def test_healthy_production_sha_is_used(tmp_path):
    path = tmp_path / "health.json"
    path.write_text(json.dumps({"status": "ok", "release_sha": SHA}))
    assert p.health_commit(path) == SHA


def test_inventory_is_stable_and_detects_modified_added_or_missing_files(site):
    receipt = frontend_receipt(site)
    p.write_json(site / "release.json", receipt)
    p.verify_directory(receipt, site)
    extra = site / "injected.js"
    extra.write_text("injected")
    with pytest.raises(ValueError, match="differ"):
        p.verify_directory(receipt, site)
    extra.unlink()
    (site / "assets/app.js").write_text("changed")
    with pytest.raises(ValueError, match="differ"):
        p.verify_directory(receipt, site)
    (site / "index.html").unlink()
    with pytest.raises(ValueError, match="missing"):
        p.verify_directory(receipt, site)


def test_inventory_rejects_symlinks_hidden_files_and_budgets(site, tmp_path, monkeypatch):
    (site / "link").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="Unsafe"):
        p.inventory(site)
    (site / "link").unlink()
    (site / ".env").write_text("not allowed")
    with pytest.raises(ValueError, match="Unsafe"):
        p.inventory(site)
    (site / ".env").unlink()
    monkeypatch.setattr(p, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="budget"):
        p.inventory(site)


@pytest.mark.parametrize(
    "name",
    [
        "../secret",
        "/secret",
        "assets/../../secret",
        "a\\b",
        "a\nb",
        "a?token=1",
        ".env",
        "a//b",
        "a/./b",
    ],
)
def test_untrusted_inventory_cannot_choose_unsafe_paths(site, name):
    receipt = frontend_receipt(site)
    receipt["files"][name] = DIGEST
    receipt["payload_digest"] = p.fingerprint(p.canonical(receipt["files"]))
    receipt["receipt_digest"] = p.receipt_digest(receipt)
    with pytest.raises(ValueError, match="Unsafe"):
        p.validate_receipt(receipt, clock=NOW)


def test_cli_rejects_modified_backend_evidence(tmp_path):
    evidence = tmp_path / "manifest.json"
    evidence.write_text(
        json.dumps({"candidate": {"image_digest": DIGEST}, "change_summary": {"risk_level": "low"}})
    )
    receipt = tmp_path / "release.json"
    command = ["python3", "-m", "tools.release.protocol"]
    args = [
        "--receipt",
        str(receipt),
        "--evidence",
        str(evidence),
        "--commit",
        SHA,
        "--run-id",
        "123",
        "--attempt",
        "1",
    ]
    subprocess.run(command + ["seal-backend"] + args, check=True, capture_output=True)
    digest = p.read_json(receipt)["receipt_digest"]
    subprocess.run(
        command + ["verify"] + args + ["--expected-digest", digest], check=True, capture_output=True
    )
    evidence.write_text("altered")
    failed = subprocess.run(
        command + ["verify"] + args + ["--expected-digest", digest], capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "evidence differs" in failed.stderr


def test_changed_scope_includes_accumulated_undeployed_commits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Release test")
    (tmp_path / "base").write_text("base")
    git("add", ".")
    git("commit", "-m", "deployed")
    deployed = git("rev-parse", "HEAD")
    (tmp_path / "backend.py").write_text("pending backend")
    git("add", ".")
    git("commit", "-m", "pending backend")
    (tmp_path / "notes.md").write_text("later docs")
    git("add", ".")
    git("commit", "-m", "later docs")
    candidate = git("rev-parse", "HEAD")
    assert "backend.py" in git("diff", "--name-only", p.change_base(candidate, deployed), candidate)
    assert "base" in git("diff", "--name-only", p.change_base(candidate, None), candidate)
