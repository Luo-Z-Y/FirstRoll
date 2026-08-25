from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import evaluate_text_agent as evaluator


def programme() -> dict[str, Any]:
    return json.loads((ROOT / "evals" / "text_agent_programme.json").read_text(encoding="utf-8"))


def sample(case_id: str, lane: str, repetition: int, *, score: float = 98.0) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "lane": lane,
        "repetition": repetition,
        "status": "passed",
        "terminal_status": "complete",
        "identity_match": True,
        "quality": {
            "score": score,
            "quality_gate_status": "passed",
            "valid_citations": True,
        },
        "latency_seconds": 10.0,
        "model_calls": [{"usage": {"total_tokens": 100}}],
        "study_attempts": [],
    }


def test_text_programme_freezes_retry_comparison_and_no_clip_boundaries() -> None:
    contract = programme()

    assert contract["retry_contract"] == {
        "owner": "research_graph",
        "initial_generation_attempts": 1,
        "maximum_repair_attempts": 2,
        "maximum_generation_model_calls_per_run": 3,
        "service_internal_repairs": 0,
        "fixed_production_internal_repairs": 1,
    }
    assert contract["comparison_protocol"]["generation_repetitions_per_lane_per_case"] == 3
    assert contract["comparison_protocol"]["quality_denominator"] == (
        "all_scheduled_samples_with_failures_scored_zero"
    )
    assert [stage["id"] for stage in contract["stages"]] == [
        "T01",
        "T02",
        "T03",
        "T04",
        "T05",
    ]
    assert contract["boundaries"]["clip_analysis"] == ("blocked_until_text_programme_complete")
    assert contract["boundaries"]["hosted_route"] is False
    assert contract["boundaries"]["production_cutover"] is False
    assert (
        contract["human_targets_after_machine_pass"]["changed_packet_source_diversity"]["threshold"]
        == 3
    )
    assert (
        contract["human_targets_after_machine_pass"]["changed_packet_filmmaker_actionability"][
            "threshold"
        ]
        == 4
    )


def test_consumed_budget_confirmation_cannot_authorise_a_rerun() -> None:
    completed = programme()
    approved = json.loads(json.dumps(completed))
    approved["status"] = "approved_revised_local_comparison"
    approved["run_budget"]["paid_run_requires_separate_budget_confirmation"] = False
    approved["owner_budget_confirmation"]["authorisation_consumed"] = False
    mismatched = json.loads(json.dumps(approved))
    mismatched["owner_budget_confirmation"]["approved_maximum_synthesis_calls"] = 91

    assert evaluator.comparison_authorised(completed) is False
    assert evaluator.comparison_authorised(approved) is True
    assert evaluator.comparison_authorised(mismatched) is False
    assert completed["owner_budget_confirmation"] == {
        "confirmed": True,
        "recorded_at": "2026-08-25T05:07:00Z",
        "decided_by": "repository_owner",
        "approved_minimum_synthesis_calls": 30,
        "approved_maximum_synthesis_calls": 90,
        "approved_maximum_planner_calls": 10,
        "approved_maximum_external_provider_calls": 10,
        "authorisation_consumed": True,
    }


def test_versioned_repeated_result_matches_the_frozen_contract() -> None:
    contract = programme()
    result = json.loads(
        (ROOT / "evals" / "results" / "text-agent-repeated-2026-08-25.json").read_text(
            encoding="utf-8"
        )
    )
    failed = {target["target_id"] for target in result["targets"] if target["status"] == "failed"}
    target_case = next(
        case
        for case in result["acquisition_cases"]
        if case["case_id"] == "the-thing-ambiguous-identity"
    )

    assert result["source_revision"] == contract["comparison_result"]["source_revision"]
    assert result["summary"]["fixed"]["completed_samples"] == 15
    assert result["summary"]["agent"]["completed_samples"] == 15
    assert result["summary"]["fixed"]["mean_quality_all_scheduled"] == 97.17
    assert result["summary"]["agent"]["mean_quality_all_scheduled"] == 97.8
    assert result["summary"]["comparison"]["agent_minus_fixed_mean_quality"] == 0.63
    assert failed == {"repeated_p50_latency_ratio", "repeated_p95_latency_ratio"}
    assert target_case["initial_packet_status"] == "limited"
    assert target_case["final_packet_status"] == "passed"
    assert target_case["acquired_reviews"] == 3
    assert result["summary"]["human_packet_review_ready"] is False
    assert contract["comparison_result"]["private_packet_snapshot_written"] is False
    evaluator.assert_safe_report(result)


def test_repeated_lane_order_alternates_to_limit_time_order_bias() -> None:
    assert evaluator.repetition_lane_order(1) == ("fixed", "agent")
    assert evaluator.repetition_lane_order(2) == ("agent", "fixed")
    assert evaluator.repetition_lane_order(3) == ("fixed", "agent")
    with pytest.raises(ValueError, match="start at one"):
        evaluator.repetition_lane_order(0)


def test_lane_summary_keeps_failed_samples_as_zero_quality() -> None:
    samples = [
        sample("case-1", "agent", 1, score=100),
        sample("case-1", "agent", 2, score=80),
        {
            **sample("case-1", "agent", 3, score=99),
            "status": "failed",
            "quality": {"score": 99, "valid_citations": False},
        },
    ]

    summary = evaluator.summarise_lane(samples, scheduled=3)

    assert summary["completed_samples"] == 2
    assert summary["completion_ratio"] == pytest.approx(2 / 3, abs=1e-6)
    assert summary["mean_quality_all_scheduled"] == 60.0
    assert summary["quality_gate_pass_ratio"] == pytest.approx(2 / 3, abs=1e-6)
    assert summary["valid_citation_ratio"] == pytest.approx(2 / 3, abs=1e-6)


def test_lane_summary_fails_closed_when_provider_token_usage_is_missing() -> None:
    samples = [sample("case-1", "fixed", repetition) for repetition in range(1, 4)]
    samples[1]["model_calls"] = [{"usage": {}}]

    summary = evaluator.summarise_lane(samples, scheduled=3)

    assert summary["token_usage_complete_ratio"] == pytest.approx(2 / 3, abs=1e-6)


def test_comparison_includes_one_off_acquisition_planner_tokens() -> None:
    fixed = {
        "mean_quality_all_scheduled": 98.0,
        "p50_latency_seconds": 10.0,
        "p95_latency_seconds": 12.0,
        "total_tokens": 1000,
    }
    agent = {
        "mean_quality_all_scheduled": 97.0,
        "p50_latency_seconds": 10.5,
        "p95_latency_seconds": 13.0,
        "total_tokens": 1100,
    }

    compared = evaluator.compare_lanes(
        fixed,
        agent,
        acquisition_planner_tokens=50,
        acquisition_planner_calls=1,
    )

    assert compared["agent_minus_fixed_mean_quality"] == -1.0
    assert compared["agent_acquisition_planner_calls"] == 1
    assert compared["agent_total_model_calls_including_acquisition"] == 1
    assert compared["agent_total_tokens_including_acquisition"] == 1150
    assert compared["total_token_ratio"] == 1.15


def test_safe_report_represents_all_three_samples_in_both_lanes() -> None:
    cases = []
    samples = []
    for index in range(5):
        case_id = "the-thing-ambiguous-identity" if index == 4 else f"case-{index}"
        cases.append(
            {
                "case_id": case_id,
                "status": "passed",
                "terminal_status": "evidence_ready",
                "initial_packet_status": "limited" if index == 4 else "passed",
                "final_packet_status": "passed",
                "initial_packet_fingerprint": f"initial-{index}",
                "packet_fingerprint": f"packet-{index}",
                "planning_calls": 1 if index == 4 else 0,
                "planner_total_tokens": 10 if index == 4 else 0,
                "external_tool_calls": 1 if index == 4 else 0,
                "attempted_tools": ["fetch_letterboxd_reviews"] if index == 4 else [],
                "tool_attempts": [],
                "acquired_reviews": 3 if index == 4 else 0,
                "acquired_videos": 0,
                "instruction_containment": True,
                "packet_changed": index == 4,
            }
        )
        for repetition in range(1, 4):
            samples.append(sample(case_id, "fixed", repetition))
            samples.append(sample(case_id, "agent", repetition))

    report = evaluator.build_report(
        programme=programme(),
        suite_id="firstroll-agent-comparison-v1",
        suite_fingerprint="safe-fingerprint",
        acquisition_cases=cases,
        samples=samples,
    )

    assert report["summary"]["fixed"]["scheduled_samples"] == 15
    assert report["summary"]["agent"]["scheduled_samples"] == 15
    assert report["summary"]["local_machine_targets_passed"] is True
    assert report["summary"]["production_cutover_ready"] is False
    evaluator.assert_safe_report(report)
