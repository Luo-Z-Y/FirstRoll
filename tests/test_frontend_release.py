"""Frontend release preparation, recovery and live checks with bounded fake providers."""

from copy import deepcopy
from datetime import timedelta
import json
from urllib.error import HTTPError

import pytest

from tools.release import frontend as f, protocol as p


SHA = "a" * 40


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setattr(f, "frontend_risk", lambda *_: "medium")
    for name in p.REQUIRED_FILES | {"staticwebapp.config.json"}:
        file = tmp_path / name
        file.parent.mkdir(exist_ok=True)
        file.write_text("fixture:" + name)
    return tmp_path


def receipt_for(site, *, run_id=123, clock=None):
    files = p.inventory(site)
    return p.create_receipt(
        component="frontend",
        commit=SHA,
        run_id=run_id,
        attempt=1,
        payload_digest=p.fingerprint(p.canonical(files)),
        files=files,
        bootstrap=True,
        clock=clock,
    )


def install_github(monkeypatch, receipt, **changes):
    run = {
        "path": f.WORKFLOW,
        "head_sha": receipt["commit_sha"],
        "head_branch": "master",
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
        "head_repository": {"full_name": p.REPOSITORY},
    }
    run.update(changes)
    artefact = {"name": receipt["artifact_name"], "expired": False, "id": 321}

    def api(path):
        return {"artifacts": [artefact]} if "/artifacts?" in path else run

    monkeypatch.setattr(f, "github_json", api)
    return artefact


def test_initial_release_requires_explicit_acknowledgement(monkeypatch, site):
    monkeypatch.setattr(f, "live_receipt", lambda: None)
    with pytest.raises(ValueError, match="allow_initial_release"):
        f.prepare(site, commit=SHA, run_id=123, attempt=1, allow_initial=False)
    receipt = f.prepare(site, commit=SHA, run_id=123, attempt=1, allow_initial=True)
    assert receipt["bootstrap"] and receipt["previous"] is None
    assert f.check_baseline(receipt) is None


def test_receipt_absence_is_only_a_404_not_a_timeout_or_bad_response(monkeypatch):
    def missing(*args, **kwargs):
        raise HTTPError(f.SITE + "/release.json", 404, "missing", {}, None)

    monkeypatch.setattr(f, "fetch", missing)
    assert f.live_receipt() is None

    def timeout(*args, **kwargs):
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(f, "fetch", timeout)
    with pytest.raises(TimeoutError):
        f.live_receipt()
    monkeypatch.setattr(f, "fetch", lambda *args, **kwargs: b"<html>fallback</html>")
    with pytest.raises(ValueError):
        f.live_receipt()


@pytest.mark.parametrize(
    "changes",
    [
        {"head_sha": "b" * 40},
        {"head_branch": "feature"},
        {"path": ".github/workflows/ci.yml"},
        {"conclusion": "failure"},
        {"status": "in_progress"},
        {"event": "pull_request"},
        {"head_repository": {"full_name": "attacker/FirstRoll"}},
    ],
)
def test_untrusted_or_failed_run_is_not_a_rollback_baseline(monkeypatch, site, changes):
    receipt = receipt_for(site)
    install_github(monkeypatch, receipt, **changes)
    with pytest.raises(ValueError, match="trusted release"):
        f.resolve_previous(receipt)


def test_expired_previous_package_blocks_even_if_bootstrap_requested(monkeypatch, site):
    receipt = receipt_for(site)
    artefact = install_github(monkeypatch, receipt)
    artefact["expired"] = True
    monkeypatch.setattr(f, "live_receipt", lambda: receipt)
    with pytest.raises(ValueError, match="missing or expired"):
        f.prepare(site, commit=SHA, run_id=124, attempt=1, allow_initial=True)


def test_after_approval_baseline_cannot_change(monkeypatch, site):
    old = receipt_for(site)
    install_github(monkeypatch, old)
    monkeypatch.setattr(f, "live_receipt", lambda: old)
    candidate = f.prepare(site, commit=SHA, run_id=124, attempt=1, allow_initial=False)
    assert f.check_baseline(candidate)["artifact_id"] == 321
    new = receipt_for(site, run_id=125)
    install_github(monkeypatch, new)
    monkeypatch.setattr(f, "live_receipt", lambda: new)
    with pytest.raises(ValueError, match="Production changed"):
        f.check_baseline(candidate)


def test_initial_release_cannot_overwrite_a_new_baseline(monkeypatch, site):
    candidate = receipt_for(site)
    monkeypatch.setattr(f, "live_receipt", lambda: receipt_for(site, run_id=125))
    with pytest.raises(ValueError, match="Production changed"):
        f.check_baseline(candidate)


def test_old_verified_backup_can_be_restored_but_tampering_fails(monkeypatch, site):
    old = receipt_for(site, clock=p.now() - timedelta(days=30))
    p.write_json(site / "release.json", old)
    install_github(monkeypatch, old)
    candidate = {"previous": f.resolve_previous(old)}
    assert f.verify_rollback(candidate, site) == old
    (site / "assets/app.js").write_text("modified")
    with pytest.raises(ValueError, match="differ"):
        f.verify_rollback(candidate, site)


def fake_live(
    monkeypatch, site, receipt, *, changed_file=None, wrong_receipt=False, api_down=False
):
    requested = []

    def fetch(url, **kwargs):
        requested.append(url)
        if url.startswith(f.API):
            if api_down:
                raise OSError("API unavailable")
            return b'{"status":"ok"}'
        name = url.removeprefix(f.SITE + "/").split("?")[0]
        if name == "release.json":
            live = deepcopy(receipt)
            if wrong_receipt:
                live["commit_sha"] = "f" * 40
            return json.dumps(live).encode()
        if name == changed_file:
            return b"stale file"
        return (site / name).read_bytes()

    monkeypatch.setattr(f, "fetch", fetch)
    return requested


def test_live_verification_checks_all_public_files_and_api_but_not_azure_control_file(
    monkeypatch, site
):
    receipt = receipt_for(site)
    requested = fake_live(monkeypatch, site, receipt)
    f.verify_live(receipt, deadline_seconds=1)
    assert f.API + "/api/health" in requested
    assert f.API + "/api/contract" in requested
    assert not any("staticwebapp.config.json" in url for url in requested)
    for path in p.REQUIRED_FILES:
        assert any(url.startswith(f.SITE + "/" + path + "?") for url in requested)


@pytest.mark.parametrize(
    "error", [{"changed_file": "assets/app.js"}, {"wrong_receipt": True}, {"api_down": True}]
)
def test_live_mismatch_fails_and_propagates_to_workflow_rollback(monkeypatch, site, error):
    receipt = receipt_for(site)
    fake_live(monkeypatch, site, receipt, **error)
    # Progress the fake clock past its deadline after one real verification attempt.
    ticks = iter([0, *([0] * 30), 1000])
    monkeypatch.setattr(f.time, "monotonic", lambda: next(ticks, 1000))
    monkeypatch.setattr(f.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="verification failed"):
        f.verify_live(receipt, deadline_seconds=1)


def test_rollback_checks_static_identity_even_during_an_independent_api_outage(monkeypatch, site):
    receipt = receipt_for(site)
    requested = fake_live(monkeypatch, site, receipt, api_down=True)
    f.verify_live(receipt, include_api=False, deadline_seconds=1)
    assert not any(url.startswith(f.API) for url in requested)


@pytest.mark.parametrize(
    "path,risk",
    [
        (b"tools/release/protocol.py", "high"),
        (b".github/workflows/ci.yml", "high"),
        (b"app/web/app.js", "medium"),
    ],
)
def test_frontend_release_control_changes_raise_risk(monkeypatch, path, risk):
    from types import SimpleNamespace

    monkeypatch.setattr(f, "change_base", lambda *_: "base")
    monkeypatch.setattr(
        f.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=path + b"\0")
    )
    assert f.frontend_risk(SHA, SHA) == risk


def test_verifier_refuses_arbitrary_origins_and_redirects():
    with pytest.raises(ValueError, match="origin"):
        f.fetch("https://attacker.invalid/payload")
    with pytest.raises(ValueError, match="origin"):
        f.fetch(f.SITE + "/payload", github=True)
    assert (
        f.NoRedirects().redirect_request(None, None, 302, "redirect", {}, "https://evil.invalid")
        is None
    )
