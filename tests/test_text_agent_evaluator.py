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
    assert contract["owner_continuation"]["paid_model_or_provider_calls_authorised"] is False
    assert contract["latency_revision_run_budget"] == {
        "expected_minimum_synthesis_calls": 30,
        "maximum_synthesis_calls": 90,
        "maximum_acquisition_planner_calls": 10,
        "maximum_external_provider_calls": 10,
        "paid_run_requires_separate_budget_confirmation": True,
    }
    assert contract["latency_revision_budget_confirmation"]["confirmed"] is False
    assert contract["latency_revision"] == {
        "status": "implementation_complete_without_provider_calls",
        "diagnosis": (
            "Invalid parseable generations were discarded, so graph repair repeated the complete "
            "6926-token prompt and full study."
        ),
        "agent_initial_temperature": 0,
        "fixed_production_initial_temperature": 0.2,
        "safe_failure_categories": True,
        "parseable_candidate_retention": "process_memory_only",
        "maximum_structural_repair_paths": 4,
        "maximum_structural_repair_completion_tokens": 800,
        "accepted_fields_preserved": True,
        "complete_merged_study_revalidated": True,
        "malformed_or_unpatchable_fallback": "one_graph_budgeted_full_regeneration",
        "future_report_schema_version": 3,
        "per_strategy_latency_reported": True,
        "committed_source_required": True,
        "fresh_output_paths_required": True,
        "previous_result_immutable": True,
        "previous_latency_targets_unchanged": True,
        "paid_validation_authorised": False,
        "meaningful_agent_claim": (
            "not_yet_supported_without_provider_latency_and_quality_evidence"
        ),
    }
    assert contract["stages"][0]["status"] == (
        "structural_repair_revision_implemented_awaiting_paid_validation"
    )
    assert all(
        stage["status"] == "blocked_by_revised_t01_validation" for stage in contract["stages"][1:]
    )
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


def test_latency_revision_needs_a_new_exact_budget_confirmation() -> None:
    completed = programme()
    approved = json.loads(json.dumps(completed))
    approved["status"] = "approved_t01_structural_repair_comparison"
    approved["latency_revision"]["paid_validation_authorised"] = True
    approved["latency_revision_run_budget"]["paid_run_requires_separate_budget_confirmation"] = (
        False
    )
    approved["latency_revision_budget_confirmation"] = {
        "confirmed": True,
        "recorded_at": "2026-08-25T12:00:00Z",
        "decided_by": "repository_owner",
        "approved_minimum_synthesis_calls": 30,
        "approved_maximum_synthesis_calls": 90,
        "approved_maximum_planner_calls": 10,
        "approved_maximum_external_provider_calls": 10,
        "authorisation_consumed": False,
    }
    mismatched = json.loads(json.dumps(approved))
    mismatched["latency_revision_budget_confirmation"]["approved_maximum_synthesis_calls"] = 91
    reused_historical = json.loads(json.dumps(completed))
    reused_historical["status"] = "approved_revised_local_comparison"
    reused_historical["owner_budget_confirmation"]["authorisation_consumed"] = False

    assert evaluator.comparison_authorised(completed) is False
    assert evaluator.comparison_authorised(approved) is True
    assert evaluator.comparison_authorised(mismatched) is False
    assert evaluator.comparison_authorised(reused_historical) is False
    assert completed["owner_budget_confirmation"]["authorisation_consumed"] is True
    assert completed["latency_revision_budget_confirmation"]["confirmed"] is False


def test_repeated_comparison_requires_a_committed_source(monkeypatch: pytest.MonkeyPatch) -> None:
    class DirtyResult:
        returncode = 1

    monkeypatch.setattr(evaluator.subprocess, "run", lambda *args, **kwargs: DirtyResult())

    with pytest.raises(SystemExit, match="Commit all tracked"):
        evaluator.require_committed_source()


def test_repeated_comparison_refuses_to_overwrite_evidence(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    packets = tmp_path / "packets.json"

    evaluator.require_fresh_output_paths(report, packets)
    report.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="report"):
        evaluator.require_fresh_output_paths(report, packets)
    report.unlink()
    packets.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="packet snapshot"):
        evaluator.require_fresh_output_paths(report, packets)


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


def test_lane_summary_reports_safe_repair_strategy_diagnostics() -> None:
    samples = [sample("case-1", "agent", repetition) for repetition in range(1, 4)]
    samples[0]["study_attempts"] = [
        {
            "kind": "initial",
            "strategy": "initial_generation",
            "status": "failed",
            "quality_status": "invalid",
            "failure_category": "citation_validation",
            "duration_seconds": 40.0,
        },
        {
            "kind": "repair",
            "strategy": "targeted_structural_repair",
            "status": "completed",
            "quality_status": "passed",
            "duration_seconds": 8.0,
        },
    ]
    samples[1]["study_attempts"] = [
        {
            "kind": "initial",
            "strategy": "initial_generation",
            "status": "completed",
            "quality_status": "insufficient_evidence",
            "duration_seconds": 42.0,
        },
        {
            "kind": "repair",
            "strategy": "targeted_quality_repair",
            "status": "completed",
            "quality_status": "passed",
            "duration_seconds": 14.0,
        },
    ]
    samples[2]["study_attempts"] = [
        {
            "kind": "repair",
            "strategy": "full_regeneration",
            "status": "completed",
            "quality_status": "passed",
            "duration_seconds": 45.0,
        }
    ]

    summary = evaluator.summarise_lane(samples, scheduled=3)

    assert summary["initial_generation_failure_samples"] == 1
    assert summary["targeted_structural_repair_samples"] == 1
    assert summary["targeted_quality_repair_samples"] == 1
    assert summary["full_regeneration_samples"] == 1
    assert summary["failure_categories"] == {"citation_validation": 1}
    assert summary["strategy_latency_seconds"] == {
        "initial_generation": {"attempts": 2, "p50": 41.0, "p95": 41.9},
        "targeted_structural_repair": {"attempts": 1, "p50": 8.0, "p95": 8.0},
        "targeted_quality_repair": {"attempts": 1, "p50": 14.0, "p95": 14.0},
        "full_regeneration": {"attempts": 1, "p50": 45.0, "p95": 45.0},
    }
    assert "PRIVATE" not in json.dumps(summary)


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

    assert report["schema_version"] == 3
    assert report["protocol"]["agent_initial_generation_temperature"] == 0
    assert report["protocol"]["maximum_structural_repair_paths"] == 4
    assert report["protocol"]["maximum_structural_repair_completion_tokens"] == 800
    assert report["summary"]["fixed"]["scheduled_samples"] == 15
    assert report["summary"]["agent"]["scheduled_samples"] == 15
    assert report["summary"]["local_machine_targets_passed"] is True
    assert report["summary"]["production_cutover_ready"] is False
    evaluator.assert_safe_report(report)
