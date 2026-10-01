"""Shared release-primitive tests; no GitHub, server or model calls."""

import pytest

from tools.release import protocol as p


@pytest.fixture
def site(tmp_path):
    directory = tmp_path / "site"
    directory.mkdir()
    for name in p.REQUIRED_FILES:
        file = directory / name
        file.parent.mkdir(exist_ok=True)
        file.write_text("fixture:" + name)
    return directory


def test_inventory_is_stable_and_detects_modified_added_or_missing_files(site):
    original = p.inventory(site)
    p.write_json(site / "release.json", {"files": original})
    assert p.inventory(site) == original
    extra = site / "injected.js"
    extra.write_text("injected")
    assert p.inventory(site) != original
    extra.unlink()
    (site / "assets/app.js").write_text("changed")
    assert p.inventory(site) != original
    (site / "index.html").unlink()
    with pytest.raises(ValueError, match="missing"):
        p.inventory(site)


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
        "",
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
def test_unsafe_paths_are_refused(name):
    assert not p.safe_path(name)


def test_receipt_digest_excludes_itself_and_detects_changes():
    receipt = {"commit_sha": "a" * 40, "files": {"index.html": "sha256:" + "b" * 64}}
    digest = p.receipt_digest(receipt)
    assert p.receipt_digest({**receipt, "receipt_digest": "anything"}) == digest
    assert p.receipt_digest({**receipt, "commit_sha": "c" * 40}) != digest
    assert p.DIGEST.fullmatch(digest)


def test_timestamps_require_a_timezone():
    assert p.timestamp("2026-10-01T00:00:00Z").utcoffset() is not None
    with pytest.raises(ValueError, match="timezone"):
        p.timestamp("2026-10-01T00:00:00")


def test_read_json_refuses_symlinks_and_non_objects(tmp_path):
    target = tmp_path / "receipt.json"
    target.write_text("[]")
    with pytest.raises(ValueError, match="object"):
        p.read_json(target)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="Invalid receipt file"):
        p.read_json(link)


def test_github_output_refuses_multiline_values(tmp_path, monkeypatch):
    destination = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(destination))
    p.output("digest", "sha256:" + "a" * 64)
    assert destination.read_text() == "digest=sha256:" + "a" * 64 + "\n"
    with pytest.raises(ValueError, match="Unsafe"):
        p.output("digest", "value\ninjected=1")
