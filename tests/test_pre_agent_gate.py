from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_pre_agent_gate import build_report, evaluate
from tools.review_evidence_packets import (
    RUBRIC_DIMENSIONS,
    aggregate_review,
    case_passes,
    configure_input_encoding,
)


def complete_scores(value: int = 4) -> dict[str, int]:
    return {dimension: value for dimension in RUBRIC_DIMENSIONS}


def test_machine_gate_has_only_the_human_packet_review_pending(tmp_path) -> None:
    scorecard = json.loads(
        (ROOT / "evals" / "pre_agent_scorecard.json").read_text(encoding="utf-8")
    )

    results = evaluate(scorecard, tmp_path / "missing-human-review.json")

    assert len(results) == len(scorecard["agent_entry_gate"]["required_target_ids"])
    assert sum(item["status"] == "passed" for item in results) == 16
    assert [
        item["target_id"]
        for item in results
        if item["status"] == "pending_human_review"
    ] == ["human_packet_pass_ratio"]
    assert not [item for item in results if item["status"] == "failed"]


def test_redacted_attested_human_review_can_complete_the_gate(tmp_path) -> None:
    scorecard = json.loads(
        (ROOT / "evals" / "pre_agent_scorecard.json").read_text(encoding="utf-8")
    )
    private_review = {
        "recorded_at": "2026-08-21T00:00:00+00:00",
        "source_revision": "test-revision",
        "reviewer_attested": True,
        "cases": [
            {
                "case_id": f"case-{index}",
                "scores": complete_scores(4 if index < 5 else 3),
                "private_note": "PRIVATE_REVIEW_NOTE",
            }
            for index in range(1, 6)
        ],
    }
    redacted = aggregate_review(private_review)
    path = tmp_path / "human-review-redacted.json"
    path.write_text(json.dumps(redacted), encoding="utf-8")

    results = evaluate(scorecard, path)
    human = next(item for item in results if item["target_id"] == "human_packet_pass_ratio")

    assert redacted["summary"]["pass_ratio"] == 0.8
    assert redacted["summary"]["passed_cases"] == 4
    assert "PRIVATE_REVIEW_NOTE" not in json.dumps(redacted)
    assert human["status"] == "passed"
    assert human["observed"] == 0.8
    report = build_report(scorecard, results, revision="reviewed-revision")
    assert report["summary"]["completed_required_steps"] == 11
    assert report["summary"]["agent_entry_ready"] is True
    assert report["blocking_reasons"] == []


def test_incomplete_required_step_blocks_agent_entry(tmp_path) -> None:
    scorecard = json.loads(
        (ROOT / "evals" / "pre_agent_scorecard.json").read_text(encoding="utf-8")
    )
    for step in scorecard["steps"]:
        if step["id"] == "S11":
            step["status"] = "next"
    review = {
        "recorded_at": "2026-08-21T00:00:00+00:00",
        "source_revision": "test-revision",
        "reviewer_attested": True,
        "cases": [
            {"case_id": f"case-{index}", "scores": complete_scores()}
            for index in range(1, 6)
        ],
    }
    path = tmp_path / "human-review-redacted.json"
    path.write_text(json.dumps(aggregate_review(review)), encoding="utf-8")

    report = build_report(scorecard, evaluate(scorecard, path), revision="test")

    assert report["summary"]["passed_targets"] == 17
    assert report["summary"]["agent_entry_ready"] is False
    assert report["blocking_reasons"] == ["incomplete:S11"]


def test_review_input_replaces_invalid_utf8_instead_of_crashing() -> None:
    class RecordingInput:
        configured: dict[str, str] | None = None

        def reconfigure(self, **values: str) -> None:
            self.configured = values

    stream = RecordingInput()
    configure_input_encoding(stream)

    assert stream.configured == {"encoding": "utf-8", "errors": "replace"}


def test_human_case_gate_requires_core_dimensions_and_no_low_score() -> None:
    assert case_passes(complete_scores(4)) is True

    weak_relevance = complete_scores(4)
    weak_relevance["focus_relevance"] = 3
    assert case_passes(weak_relevance) is False

    low_diversity = complete_scores(4)
    low_diversity["source_diversity"] = 2
    assert case_passes(low_diversity) is False
