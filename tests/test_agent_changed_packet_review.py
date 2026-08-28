from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools import review_agent_changed_packet_studies as reviewer
from tools.evaluate_agent_changed_packet import blind_private_pairs
from tools.evaluate_agent_repair import synthetic_packet, valid_candidate


def private_studies() -> dict:
    studies = {
        (lane, repetition): valid_candidate()
        for lane in ("fixed", "candidate")
        for repetition in (1, 5, 10)
    }
    packet = synthetic_packet()
    return {
        "schema_version": 1,
        "programme_id": reviewer.PROGRAMME_ID,
        "experiment_id": "A03",
        "source_revision": "abc123",
        "a01_source_revision": "a01-source",
        "suite_fingerprint": "suite123",
        "case_id": "case-1",
        "selected_acquisition_lane": "model_gap_planner",
        "pairs": blind_private_pairs(
            studies,
            {"fixed": packet, "candidate": packet},
            repetitions=(1, 5, 10),
            revision="abc123",
        ),
    }


def private_review(studies: dict, *, attested: bool = True) -> dict:
    pairs = []
    for pair in studies["pairs"]:
        candidate_id = next(
            blind_id for blind_id, lane in pair["blind_mapping"].items() if lane == "candidate"
        )
        pairs.append(
            {
                "repetition": pair["repetition"],
                "usefulness_preference": candidate_id,
                "evidence_responsibility_preference": "TIE",
                "severe_grounding_concern": {"A": False, "B": False},
                "private_note": "PRIVATE_REVIEW_NOTE",
            }
        )
    return {
        "recorded_at": "2026-08-28T00:00:00Z",
        "reviewer_attested": attested,
        "pairs": pairs,
    }


def test_private_changed_studies_require_mode_and_complete_blind_pairs(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(reviewer, "ROOT", tmp_path)
    path = tmp_path / ".firstroll" / "evaluations" / "studies.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(private_studies()), encoding="utf-8")
    os.chmod(path, 0o600)

    loaded = reviewer.load_private_studies(path)

    assert {pair["repetition"] for pair in loaded["pairs"]} == {1, 5, 10}
    assert all(
        set(pair["blind_mapping"].values()) == {"fixed", "candidate"} for pair in loaded["pairs"]
    )


def test_changed_study_review_rejects_private_symlink_outside_project(
    tmp_path: Path, monkeypatch
) -> None:
    worktree = tmp_path / "worktree"
    outside = tmp_path / "outside"
    worktree.mkdir()
    outside.mkdir()
    (worktree / ".firstroll").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(reviewer, "ROOT", worktree)

    with pytest.raises(ValueError, match="under .firstroll"):
        reviewer.require_private_path(worktree / ".firstroll" / "studies.json")


def test_changed_study_human_gate_passes_three_blinded_candidate_preferences() -> None:
    studies = private_studies()

    result = reviewer.aggregate_review(private_review(studies), studies)

    assert result["summary"] == {
        "candidate_usefulness_preferred_pairs": 3,
        "candidate_evidence_responsibility_losses": 0,
        "candidate_severe_grounding_concerns": 0,
        "human_gate_passed": True,
    }
    assert "PRIVATE_REVIEW_NOTE" not in str(result)


def test_changed_study_human_gate_requires_attestation_and_no_grounding_concern() -> None:
    studies = private_studies()
    unverified = reviewer.aggregate_review(private_review(studies, attested=False), studies)
    concerned_review = private_review(studies)
    first = concerned_review["pairs"][0]
    pair = next(item for item in studies["pairs"] if item["repetition"] == first["repetition"])
    candidate_id = next(
        blind_id for blind_id, lane in pair["blind_mapping"].items() if lane == "candidate"
    )
    first["severe_grounding_concern"][candidate_id] = True
    concerned = reviewer.aggregate_review(concerned_review, studies)

    assert unverified["summary"]["human_gate_passed"] is False
    assert concerned["summary"]["candidate_severe_grounding_concerns"] == 1
    assert concerned["summary"]["human_gate_passed"] is False


def test_changed_study_human_gate_rejects_fixed_evidence_preference() -> None:
    studies = private_studies()
    review = private_review(studies)
    first = review["pairs"][0]
    pair = next(item for item in studies["pairs"] if item["repetition"] == first["repetition"])
    fixed_id = next(blind_id for blind_id, lane in pair["blind_mapping"].items() if lane == "fixed")
    first["evidence_responsibility_preference"] = fixed_id

    result = reviewer.aggregate_review(review, studies)

    assert result["summary"]["candidate_evidence_responsibility_losses"] == 1
    assert result["summary"]["human_gate_passed"] is False
