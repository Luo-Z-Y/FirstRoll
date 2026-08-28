from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.backend.study_service import GroundedStudy
from tools import evaluate_agent_repair as evaluator


ROOT = Path(__file__).resolve().parents[1]
PROGRAMME = ROOT / "evals" / "autonomous_agent_programme.json"


def programme() -> dict[str, Any]:
    return json.loads(PROGRAMME.read_text(encoding="utf-8"))


def approved_programme() -> dict[str, Any]:
    value = programme()
    experiment = evaluator.repair_experiment(value)
    proposed = experiment["proposed_budget"]
    value["status"] = "a02_structural_repair_ablation_approved"
    value["owner_mandate"]["paid_model_or_provider_calls_authorised"] = True
    experiment["status"] = "approved_one_run"
    experiment["paid_budget_confirmation"] = {
        "confirmed": True,
        "authorisation_consumed": False,
        "approved_fault_scenarios": proposed["fault_scenarios"],
        "approved_repetitions_per_lane_per_scenario": proposed["repetitions_per_lane_per_scenario"],
        "approved_expected_model_calls": proposed["expected_model_calls"],
        "approved_maximum_model_calls": proposed["maximum_model_calls"],
    }
    return value


def test_current_programme_authorises_one_exact_repair_ablation() -> None:
    assert evaluator.comparison_authorised(programme()) is True


def test_repair_authorisation_requires_every_exact_budget() -> None:
    approved = approved_programme()
    mismatched = approved_programme()
    evaluator.repair_experiment(mismatched)["paid_budget_confirmation"][
        "approved_maximum_model_calls"
    ] += 1
    consumed = approved_programme()
    evaluator.repair_experiment(consumed)["paid_budget_confirmation"]["authorisation_consumed"] = (
        True
    )

    assert evaluator.comparison_authorised(approved) is True
    assert evaluator.comparison_authorised(mismatched) is False
    assert evaluator.comparison_authorised(consumed) is False


def test_repair_run_inputs_must_match_approved_paths(tmp_path: Path) -> None:
    value = programme()
    experiment = evaluator.repair_experiment(value)
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


def test_synthetic_faults_are_bounded_to_the_declared_paths() -> None:
    valid = evaluator.valid_candidate()

    for scenario in evaluator.SCENARIOS:
        candidate, paths = evaluator.fault_candidate(scenario)
        assert 1 <= len(paths) <= 2
        assert candidate != valid
        assert all(path.startswith("sections.") for path in paths)

    assert len(evaluator.synthetic_packet().theory_sources) == 2
    assert len(evaluator.synthetic_packet().attributed_sources) == 2


def test_accepted_field_comparison_ignores_only_requested_paths() -> None:
    candidate, paths = evaluator.fault_candidate("one_invalid_citation")
    repaired = evaluator.valid_candidate()
    changed_elsewhere = evaluator.valid_candidate()
    changed_elsewhere["central_argument"] = (
        "This unrelated accepted field was changed and must make the preservation check fail even "
        "when the requested citation path itself has been corrected by the repair lane."
    )

    assert evaluator.accepted_fields_preserved(candidate, repaired, paths) is True
    assert evaluator.accepted_fields_preserved(candidate, changed_elsewhere, paths) is False
    GroundedStudy.model_validate(repaired)


def sample(
    lane: str,
    *,
    duration: float,
    tokens: int,
    quality: float = 100.0,
    preserved: bool | None = None,
) -> dict[str, Any]:
    return {
        "scenario": "one_invalid_citation",
        "repetition": 1,
        "lane": lane,
        "status": "passed",
        "duration_seconds": duration,
        "model_calls": 1,
        "total_tokens": tokens,
        "quality_score": quality,
        "citation_and_schema_valid": True,
        "accepted_fields_preserved": preserved,
        "repair_attempts": 1 if lane == "targeted_field_patch" else 0,
    }


def test_repair_targets_require_material_saving_and_preservation() -> None:
    samples = []
    for _ in range(9):
        samples.append(
            sample(
                "targeted_field_patch",
                duration=10.0,
                tokens=300,
                preserved=True,
            )
        )
        samples.append(
            sample(
                "complete_regeneration",
                duration=20.0,
                tokens=1000,
            )
        )
    patch = evaluator.lane_summary(samples, "targeted_field_patch")
    regeneration = evaluator.lane_summary(samples, "complete_regeneration")

    targets = evaluator.evaluate_targets(samples, patch, regeneration, 36)

    assert all(item["status"] == "passed" for item in targets)
    assert evaluator.ratio(patch["total_tokens"], regeneration["total_tokens"]) == 0.3


def test_repair_target_fails_when_an_accepted_field_changes() -> None:
    samples = [
        sample(
            "targeted_field_patch",
            duration=10.0,
            tokens=300,
            preserved=False,
        ),
        sample("complete_regeneration", duration=20.0, tokens=1000),
    ]
    patch = evaluator.lane_summary(samples, "targeted_field_patch")
    regeneration = evaluator.lane_summary(samples, "complete_regeneration")

    targets = {
        item["target_id"]: item["status"]
        for item in evaluator.evaluate_targets(samples, patch, regeneration, 36)
    }

    assert targets["accepted_field_preservation"] == "failed"


def test_repair_target_fails_when_transport_telemetry_omits_a_call() -> None:
    samples = []
    for _ in range(9):
        samples.extend(
            [
                sample(
                    "targeted_field_patch",
                    duration=10.0,
                    tokens=300,
                    preserved=True,
                ),
                sample("complete_regeneration", duration=20.0, tokens=1000),
            ]
        )
    patch = evaluator.lane_summary(samples, "targeted_field_patch")
    regeneration = evaluator.lane_summary(samples, "complete_regeneration")

    targets = {
        item["target_id"]: item["status"]
        for item in evaluator.evaluate_targets(
            samples,
            patch,
            regeneration,
            36,
            transport_calls=17,
        )
    }

    assert targets["transport_call_telemetry_complete"] == "failed"
