from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import evaluate_agent_patch_reliability as evaluator
from tools.evaluate_agent_repair import fault_candidate, valid_candidate


ROOT = Path(__file__).resolve().parents[1]
PROGRAMME = ROOT / "evals" / "autonomous_agent_programme.json"


def programme() -> dict[str, Any]:
    return json.loads(PROGRAMME.read_text(encoding="utf-8"))


def approved_programme() -> dict[str, Any]:
    value = programme()
    experiment = evaluator.reliability_experiment(value)
    budget = experiment["proposed_budget"]
    value["status"] = "a02r_patch_reliability_approved"
    value["owner_mandate"]["paid_model_or_provider_calls_authorised"] = True
    experiment["status"] = "approved_one_run"
    experiment["paid_budget_confirmation"] = {
        "confirmed": True,
        "authorisation_consumed": False,
        "approved_fault_scenarios": budget["fault_scenarios"],
        "approved_repetitions_per_scenario": budget["repetitions_per_scenario"],
        "approved_expected_model_calls": budget["expected_model_calls"],
        "approved_maximum_model_calls": budget["maximum_model_calls"],
        "approved_planner_calls": budget["planner_calls"],
        "approved_provider_calls": budget["provider_calls"],
        "approved_report_path": "evals/results/patch-reliability-approved.json",
        "approved_run_lock_path": ".firstroll/evaluations/patch-reliability-approved.lock",
    }
    return value


def samples() -> list[dict[str, Any]]:
    return [
        {
            "scenario": scenario,
            "repetition": repetition,
            "lane": "targeted_field_patch",
            "status": "passed",
            "duration_seconds": 2.0,
            "model_calls": 1,
            "total_tokens": 1000,
            "quality_score": 100.0,
            "citation_and_schema_valid": True,
            "accepted_fields_preserved": True,
            "repair_attempts": 1,
        }
        for repetition in range(1, evaluator.REPETITIONS + 1)
        for scenario in evaluator.SCENARIOS
    ]


def test_current_programme_refuses_unfunded_patch_reliability() -> None:
    assert evaluator.comparison_authorised(programme()) is False


def test_patch_reliability_authorisation_requires_every_exact_limit() -> None:
    approved = approved_programme()
    mismatched = approved_programme()
    evaluator.reliability_experiment(mismatched)["paid_budget_confirmation"][
        "approved_maximum_model_calls"
    ] += 1
    consumed = approved_programme()
    evaluator.reliability_experiment(consumed)["paid_budget_confirmation"][
        "authorisation_consumed"
    ] = True

    assert evaluator.comparison_authorised(approved) is True
    assert evaluator.comparison_authorised(mismatched) is False
    assert evaluator.comparison_authorised(consumed) is False


def test_patch_reliability_inputs_must_match_approved_paths(tmp_path: Path) -> None:
    value = approved_programme()
    experiment = evaluator.reliability_experiment(value)
    confirmation = experiment["paid_budget_confirmation"]
    args = evaluator.argparse.Namespace(
        programme=evaluator.DEFAULT_PROGRAMME,
        output=evaluator.ROOT / confirmation["approved_report_path"],
        run_lock=evaluator.ROOT / confirmation["approved_run_lock_path"],
    )

    evaluator.require_authorised_run_inputs(args, experiment)
    args.output = tmp_path / "unapproved.json"
    with pytest.raises(SystemExit, match="output path is not authorised"):
        evaluator.require_authorised_run_inputs(args, experiment)


def test_mixed_schema_and_citation_fault_changes_only_declared_paths() -> None:
    candidate, paths = fault_candidate("one_schema_and_one_citation")

    assert candidate != valid_candidate()
    assert paths == ("sections.1.mechanism", "sections.3.source_ids")


def test_patch_reliability_targets_require_twenty_four_complete_preserved_samples() -> None:
    scheduled = samples()
    summary = evaluator.summarise(scheduled)
    targets = evaluator.evaluate_targets(
        scheduled,
        summary,
        evaluator.reliability_experiment(programme()),
        transport_calls=24,
    )

    assert summary["completed_samples"] == 24
    assert summary["p95_latency_seconds"] == 2.0
    assert summary["total_tokens"] == 24000
    assert all(item["status"] == "passed" for item in targets)


def test_patch_reliability_retains_failure_in_every_gate() -> None:
    scheduled = samples()
    scheduled[0] = {
        **scheduled[0],
        "status": "failed",
        "quality_score": 0.0,
        "citation_and_schema_valid": False,
        "accepted_fields_preserved": False,
    }
    summary = evaluator.summarise(scheduled)
    targets = {
        item["target_id"]: item["status"]
        for item in evaluator.evaluate_targets(
            scheduled,
            summary,
            evaluator.reliability_experiment(programme()),
            transport_calls=24,
        )
    }

    assert targets["completion_ratio"] == "failed"
    assert targets["per_scenario_completion"] == "failed"
    assert targets["citation_and_schema_validity"] == "failed"
    assert targets["accepted_field_preservation"] == "failed"
