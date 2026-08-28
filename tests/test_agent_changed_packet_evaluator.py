from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.backend.criticism import ReviewSource
from app.backend.evidence import EvidencePacket
from tools import evaluate_agent_changed_packet as evaluator
from tools.evaluate_agent_repair import valid_candidate
from tools.evaluate_local_agent import packet_fingerprint


ROOT = Path(__file__).resolve().parents[1]
PROGRAMME = ROOT / "evals" / "autonomous_agent_programme.json"


def programme() -> dict[str, Any]:
    return json.loads(PROGRAMME.read_text(encoding="utf-8"))


def source(provider: str, domain: str, index: int, summary: str) -> ReviewSource:
    return ReviewSource(
        source_id=f"R{index}",
        provider=provider,
        review_id=f"review-{index}",
        title=f"Attributed source {index}",
        summary=summary,
        author=f"Author {index}",
        url=f"https://{domain}/work/{index}",
        language="en",
    )


def packet(*reviews: ReviewSource) -> EvidencePacket:
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
                    "page": 1,
                    "language": "en",
                    "excerpt": (
                        "Framing can organise uncertainty through spatial relationships that a "
                        "filmmaker can log and compare without assuming unseen facts."
                    ),
                }
            ],
            "method": "synthetic",
        },
        "How does framing organise uncertainty?",
        reviews=list(reviews),
    )


FIRST = source(
    "Guardian",
    "theguardian.com",
    1,
    "The critic reports that framing withholds spatial information during recurring transitions.",
)
SECOND = source(
    "Crossref scholarship",
    "doi.org",
    2,
    "The abstract compares editing rhythm and spatial uncertainty as analytical relationships.",
)


def a01_artifacts(selected_lane: str = "model_gap_planner") -> tuple[dict, dict, dict]:
    fixed = packet(FIRST)
    candidate = packet(FIRST, SECOND)
    deterministic = candidate
    packets = {
        "schema_version": 1,
        "programme_id": "firstroll-autonomous-research-agent-v1",
        "experiment_id": "A01",
        "source_revision": "a01-source",
        "suite_fingerprint": "a01-suite",
        "case_id": "the-thing-ambiguous-identity",
        "packets": [
            {"blind_id": "A", "packet": fixed.model_dump()},
            {"blind_id": "B", "packet": deterministic.model_dump()},
            {"blind_id": "C", "packet": candidate.model_dump()},
        ],
        "blind_mapping": {
            "A": "fixed_no_acquisition",
            "B": "deterministic_gap_router",
            "C": "model_gap_planner",
        },
        "lane_metrics": {
            lane: {
                "external_tool_calls": 0 if lane == "fixed_no_acquisition" else 2,
                "model_planner_calls": 2 if lane == "model_gap_planner" else 0,
                "planner_total_tokens": 80 if lane == "model_gap_planner" else 0,
                "acquisition_latency_seconds": 5.0 if lane != "fixed_no_acquisition" else 0.0,
            }
            for lane in (
                "fixed_no_acquisition",
                "deterministic_gap_router",
                "model_gap_planner",
            )
        },
    }
    machine = {
        "programme_id": packets["programme_id"],
        "experiment_id": "A01",
        "source_revision": "a01-source",
        "suite_fingerprint": "a01-suite",
        "case_id": "the-thing-ambiguous-identity",
        "lanes": [
            {
                "lane": "fixed_no_acquisition",
                "final_packet_fingerprint": packet_fingerprint(fixed),
                "planner_total_tokens": 0,
                "model_planner_calls": 0,
                "acquisition_latency_seconds": 0.0,
            },
            {
                "lane": "deterministic_gap_router",
                "final_packet_fingerprint": packet_fingerprint(deterministic),
                "planner_total_tokens": 0,
                "model_planner_calls": 0,
                "acquisition_latency_seconds": 5.0,
            },
            {
                "lane": "model_gap_planner",
                "final_packet_fingerprint": packet_fingerprint(candidate),
                "planner_total_tokens": 80,
                "model_planner_calls": 2,
                "acquisition_latency_seconds": 5.0,
            },
        ],
        "summary": {"machine_targets_passed": True},
    }
    human = {
        "programme_id": packets["programme_id"],
        "experiment_id": "A01",
        "source_revision": "a01-source",
        "suite_fingerprint": "a01-suite",
        "reviewer_attested": True,
        "lanes": {
            lane: {"passed_packet_rubric": lane != "fixed_no_acquisition"}
            for lane in (
                "fixed_no_acquisition",
                "deterministic_gap_router",
                "model_gap_planner",
            )
        },
        "summary": {
            "advancement": (
                "advance_A02" if selected_lane == "model_gap_planner" else "prefer_deterministic"
            )
        },
    }
    return machine, packets, human


def accepted_programme(selected_lane: str = "model_gap_planner") -> dict[str, Any]:
    value = programme()
    value["a01_result"] = {
        "source_revision": "a01-source",
        "suite_fingerprint": "a01-suite",
        "machine_targets_passed": True,
        "owner_review_attested": True,
        "selected_lane": selected_lane,
    }
    return value


def approved_programme() -> dict[str, Any]:
    value = accepted_programme()
    experiment = evaluator.changed_packet_experiment(value)
    proposed = experiment["proposed_budget"]
    value["status"] = "a03_changed_packet_synthesis_approved"
    value["owner_mandate"]["paid_model_or_provider_calls_authorised"] = True
    experiment["status"] = "approved_one_run"
    experiment["paid_budget_confirmation"] = {
        "confirmed": True,
        "authorisation_consumed": False,
        "approved_generation_repetitions_per_lane": proposed["generation_repetitions_per_lane"],
        "approved_minimum_synthesis_calls": proposed["expected_minimum_synthesis_calls"],
        "approved_maximum_synthesis_calls": proposed["maximum_synthesis_calls"],
        "approved_planner_calls": 0,
        "approved_provider_calls": 0,
    }
    return value


def test_current_programme_refuses_changed_packet_spend() -> None:
    assert evaluator.comparison_authorised(programme()) is False


def test_changed_packet_authorisation_requires_A01_and_exact_zero_reacquisition_budget() -> None:
    approved = approved_programme()
    mismatch = approved_programme()
    evaluator.changed_packet_experiment(mismatch)["paid_budget_confirmation"][
        "approved_provider_calls"
    ] = 1

    assert evaluator.comparison_authorised(approved) is True
    assert evaluator.comparison_authorised(mismatch) is False


def test_A03_rejects_private_review_symlink_outside_project(tmp_path: Path, monkeypatch) -> None:
    worktree = tmp_path / "worktree"
    outside = tmp_path / "outside"
    worktree.mkdir()
    outside.mkdir()
    review_path = outside / "review.json"
    review_path.write_text("{}", encoding="utf-8")
    os.chmod(review_path, 0o600)
    (worktree / ".firstroll").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(evaluator, "ROOT", worktree)

    with pytest.raises(ValueError, match="under .firstroll"):
        evaluator.load_private_json(worktree / ".firstroll" / "review.json")


def test_A03_selects_exact_A01_packet_and_human_winning_policy() -> None:
    machine, private, human = a01_artifacts()

    selected, fixed, candidate, lane = evaluator.select_a01_packets(
        accepted_programme(), machine, private, human
    )

    assert selected == "model_gap_planner"
    assert packet_fingerprint(fixed) == machine["lanes"][0]["final_packet_fingerprint"]
    assert packet_fingerprint(candidate) == machine["lanes"][2]["final_packet_fingerprint"]
    assert lane["acquisition_latency_seconds"] == 5.0

    human["summary"]["advancement"] = "prefer_deterministic"
    with pytest.raises(ValueError, match="contradicts"):
        evaluator.select_a01_packets(accepted_programme(), machine, private, human)


def test_candidate_only_signature_ignores_reassigned_evidence_ID() -> None:
    fixed = packet(FIRST)
    candidate = packet(SECOND, FIRST)

    candidate_ids = evaluator.candidate_only_source_ids(fixed, candidate)

    assert len(candidate_ids) == 1
    second_item = next(
        item for item in candidate.attributed_sources if "doi.org" in item.source_url
    )
    assert candidate_ids == {second_item.evidence_id}


def test_candidate_only_source_use_is_measured_without_reporting_IDs() -> None:
    fixed = packet(FIRST)
    candidate = packet(FIRST, SECOND)
    candidate_ids = evaluator.candidate_only_source_ids(fixed, candidate)
    used_id = next(iter(candidate_ids))
    study = valid_candidate()
    study["sections"][0]["attributed_source_ids"] = [used_id]

    assert evaluator.cited_candidate_only_sources(study, candidate_ids) == {used_id}


def test_changed_packet_machine_gate_requires_quality_value_use_and_lifecycle_latency() -> None:
    experiment = evaluator.changed_packet_experiment(programme())
    fixed = {
        "completion_ratio": 1.0,
        "mean_quality_all_scheduled": 98.0,
        "p50_latency_seconds": 50.0,
        "p95_latency_seconds": 60.0,
        "total_tokens": 100_000,
        "model_calls": 10,
        "quality_gate_pass_ratio": 1.0,
        "valid_citation_ratio": 1.0,
        "token_usage_complete_ratio": 1.0,
    }
    candidate = {
        **fixed,
        "mean_quality_all_scheduled": 98.5,
        "p50_latency_seconds": 52.0,
        "p95_latency_seconds": 62.0,
        "total_tokens": 110_000,
    }
    comparison = {
        "agent_minus_fixed_mean_quality": 0.5,
        "p50_latency_ratio": 1.04,
        "p95_latency_ratio": 1.033333,
        "total_token_ratio": 1.1,
    }

    targets = evaluator.evaluate_targets(
        experiment,
        fixed,
        candidate,
        comparison,
        source_usage_ratio=0.8,
        candidate_only_count=2,
        acquisition_latency_seconds=5.0,
    )

    assert all(item["status"] == "passed" for item in targets)


def test_changed_packet_blind_pairs_use_predeclared_repetitions() -> None:
    studies = {
        (lane, repetition): valid_candidate()
        for lane in ("fixed", "candidate")
        for repetition in (1, 5, 10)
    }
    packets = {"fixed": packet(FIRST), "candidate": packet(FIRST, SECOND)}

    pairs = evaluator.blind_private_pairs(
        studies,
        packets,
        repetitions=(1, 5, 10),
        revision="abc123",
    )

    assert {pair["repetition"] for pair in pairs} == {1, 5, 10}
    assert all(set(pair["blind_mapping"].values()) == {"fixed", "candidate"} for pair in pairs)
    assert all("lane" not in study for pair in pairs for study in pair["studies"])
