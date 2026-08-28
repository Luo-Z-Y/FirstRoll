from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.evidence import EvidencePacket
from tools import review_text_agent_packets as reviewer


def packet() -> EvidencePacket:
    return EvidencePacket.from_retrieval(
        {
            "title": "Example Film",
            "year": 2024,
            "directors": ["Example Director"],
        },
        {
            "method": "hybrid_rrf",
            "passages": [
                {
                    "title": "Film Form",
                    "page": 12,
                    "language": "en",
                    "excerpt": (
                        "Framing and editing can organise spatial relations that a viewer can "
                        "log and compare during close analysis."
                    ),
                }
            ],
        },
        "How does framing organise uncertainty?",
    )


def write_snapshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "programme_id": "firstroll-text-agent-v1",
                "source_revision": "test-revision",
                "suite_fingerprint": "test-suite-fingerprint",
                "cases": [
                    {
                        "case_id": "the-thing-ambiguous-identity",
                        "packet": packet().model_dump(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_packet_review_requires_private_path_and_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(reviewer, "ROOT", tmp_path)
    private_path = tmp_path / ".firstroll" / "evaluations" / "packets.json"
    write_snapshot(private_path)
    os.chmod(private_path, 0o644)

    with pytest.raises(PermissionError, match="0600"):
        reviewer.load_private_packets(private_path)
    with pytest.raises(ValueError, match="under .firstroll"):
        reviewer.load_private_packets(tmp_path / "public.json")

    os.chmod(private_path, 0o600)
    loaded = reviewer.load_private_packets(private_path)
    assert loaded["cases"][0]["case_id"] == "the-thing-ambiguous-identity"


def test_packet_review_rejects_private_symlink_outside_project(tmp_path, monkeypatch) -> None:
    worktree = tmp_path / "worktree"
    outside = tmp_path / "outside"
    worktree.mkdir()
    outside.mkdir()
    (worktree / ".firstroll").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(reviewer, "ROOT", worktree)

    with pytest.raises(ValueError, match="under .firstroll"):
        reviewer.require_private_path(worktree / ".firstroll" / "packets.json")


def test_packet_review_rejects_empty_or_duplicate_changed_cases(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(reviewer, "ROOT", tmp_path)
    private_path = tmp_path / ".firstroll" / "evaluations" / "packets.json"
    write_snapshot(private_path)
    payload = json.loads(private_path.read_text(encoding="utf-8"))
    payload["cases"].append(dict(payload["cases"][0]))
    private_path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(private_path, 0o600)

    with pytest.raises(ValueError, match="invalid or duplicate"):
        reviewer.load_private_packets(private_path)


def test_redacted_human_aggregate_excludes_packet_text_and_private_notes() -> None:
    aggregate = reviewer.aggregate_review(
        {
            "recorded_at": "2026-08-25T00:00:00Z",
            "source_revision": "abc123",
            "reviewer_attested": True,
            "cases": [
                {
                    "case_id": "the-thing-ambiguous-identity",
                    "scores": {
                        "focus_relevance": 4,
                        "traceability": 5,
                        "source_diversity": 3,
                        "epistemic_calibration": 5,
                        "filmmaker_actionability": 4,
                    },
                    "private_note": "PRIVATE_REVIEW_NOTE",
                    "packet": {"content": "PRIVATE_EVIDENCE_TEXT"},
                }
            ],
        }
    )

    assert aggregate["summary"]["passed_cases"] == 1
    serialised = json.dumps(aggregate)
    assert "PRIVATE_REVIEW_NOTE" not in serialised
    assert "PRIVATE_EVIDENCE_TEXT" not in serialised
    assert "packet" not in aggregate["cases"][0]
