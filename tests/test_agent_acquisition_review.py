from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.backend.criticism import ReviewSource
from app.backend.evidence import EvidencePacket
from tools import review_agent_acquisition_packets as reviewer


def packet() -> EvidencePacket:
    review = ReviewSource(
        source_id="R1",
        provider="Guardian",
        review_id="review-1",
        title="Attributed review",
        summary=(
            "The critic reports a recurring framing pattern that can be checked during close "
            "viewing of the selected film."
        ),
        author="A Critic",
        url="https://theguardian.com/film/review-1",
        language="en",
    )
    return EvidencePacket.from_retrieval(
        {
            "title": "Example Film",
            "year": 2024,
            "credits": {"directors": ["Example Director"]},
        },
        {
            "passages": [
                {
                    "title": "Framing Theory",
                    "page": 2,
                    "language": "en",
                    "excerpt": (
                        "Framing creates repeatable spatial relations that a filmmaker can log and "
                        "compare without treating a hypothesis as observation."
                    ),
                }
            ]
        },
        "How does framing organise uncertainty?",
        reviews=[review],
    )


def private_packets(*, model_calls: int = 2, deterministic_calls: int = 2) -> dict:
    value = packet().model_dump()
    return {
        "schema_version": 1,
        "programme_id": reviewer.PROGRAMME_ID,
        "experiment_id": "A01",
        "source_revision": "abc123",
        "suite_fingerprint": "suite123",
        "case_id": "case-1",
        "packets": [
            {"blind_id": "A", "packet": value},
            {"blind_id": "B", "packet": value},
            {"blind_id": "C", "packet": value},
        ],
        "blind_mapping": {
            "A": "deterministic_gap_router",
            "B": "fixed_no_acquisition",
            "C": "model_gap_planner",
        },
        "lane_metrics": {
            "fixed_no_acquisition": {
                "external_tool_calls": 0,
                "model_planner_calls": 0,
                "planner_total_tokens": 0,
            },
            "deterministic_gap_router": {
                "external_tool_calls": deterministic_calls,
                "model_planner_calls": 0,
                "planner_total_tokens": 0,
            },
            "model_gap_planner": {
                "external_tool_calls": model_calls,
                "model_planner_calls": model_calls,
                "planner_total_tokens": 100,
            },
        },
    }


def review(*, model_scores: dict[str, int], deterministic_scores: dict[str, int]) -> dict:
    fixed_scores = {
        "focus_relevance": 4,
        "traceability": 4,
        "source_diversity": 2,
        "epistemic_calibration": 4,
        "filmmaker_actionability": 3,
    }
    return {
        "recorded_at": "2026-08-28T00:00:00Z",
        "reviewer_attested": True,
        "packets": [
            {"blind_id": "A", "scores": deterministic_scores},
            {"blind_id": "B", "scores": fixed_scores},
            {"blind_id": "C", "scores": model_scores},
        ],
    }


PASSING = {
    "focus_relevance": 4,
    "traceability": 4,
    "source_diversity": 4,
    "epistemic_calibration": 4,
    "filmmaker_actionability": 4,
}


def test_private_acquisition_snapshot_requires_complete_blind_mapping(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(reviewer, "ROOT", tmp_path)
    path = tmp_path / ".firstroll" / "evaluations" / "packets.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(private_packets()), encoding="utf-8")
    os.chmod(path, 0o600)

    loaded = reviewer.load_private_packets(path)

    assert set(loaded["blind_mapping"].values()) == reviewer.EXPECTED_LANES
    assert all("lane" not in item for item in loaded["packets"])


def test_acquisition_review_rejects_private_symlink_outside_project(
    tmp_path: Path, monkeypatch
) -> None:
    worktree = tmp_path / "worktree"
    outside = tmp_path / "outside"
    worktree.mkdir()
    outside.mkdir()
    (worktree / ".firstroll").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(reviewer, "ROOT", worktree)

    with pytest.raises(ValueError, match="under .firstroll"):
        reviewer.require_private_path(worktree / ".firstroll" / "packets.json")


def test_model_planner_advances_only_when_blinded_value_beats_baseline() -> None:
    model_scores = {**PASSING, "source_diversity": 5}

    result = reviewer.aggregate_review(
        review(model_scores=model_scores, deterministic_scores=PASSING),
        private_packets(),
    )

    assert result["summary"]["model_planner_value_demonstrated"] is True
    assert result["summary"]["advancement"] == "advance_A02"
    assert "private_note" not in str(result)


def test_model_value_requires_owner_attestation() -> None:
    private_review = review(
        model_scores={**PASSING, "source_diversity": 5}, deterministic_scores=PASSING
    )
    private_review["reviewer_attested"] = False

    result = reviewer.aggregate_review(private_review, private_packets())

    assert result["reviewer_attested"] is False
    assert result["summary"]["model_planner_value_demonstrated"] is False


def test_equal_packet_and_equal_calls_prefer_deterministic_router() -> None:
    result = reviewer.aggregate_review(
        review(model_scores=PASSING, deterministic_scores=PASSING),
        private_packets(),
    )

    assert result["summary"]["model_planner_value_demonstrated"] is False
    assert result["summary"]["advancement"] == "prefer_deterministic"


def test_equal_packet_can_advance_only_with_fewer_external_calls() -> None:
    result = reviewer.aggregate_review(
        review(model_scores=PASSING, deterministic_scores=PASSING),
        private_packets(model_calls=1, deterministic_calls=2),
    )

    assert result["summary"]["model_planner_value_demonstrated"] is True
    assert result["summary"]["advancement"] == "advance_A02"
