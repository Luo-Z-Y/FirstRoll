from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend import main
from app.backend.study_service import DeepSeekStudyService
from tools.evaluate_agent_repair import percentile, run_patch_sample, synthetic_packet
from tools.evaluate_local_agent import (
    SafeRecordingTransport,
    assert_safe_report,
    source_revision,
    validate_private_packet_output_path,
    write_private_packets,
)
from tools.evaluate_text_agent import require_committed_source


EXPERIMENT_ID = "A02R"
SCENARIOS = (
    "one_invalid_citation",
    "one_schema_invalid_field",
    "two_invalid_fields",
    "one_schema_and_one_citation",
)
REPETITIONS = 6
DEFAULT_PROGRAMME = ROOT / "evals" / "autonomous_agent_programme.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "autonomous-agent-patch-reliability-current.json"
DEFAULT_RUN_LOCK = ROOT / ".firstroll" / "evaluations" / "autonomous-agent-patch-reliability.lock"


def reliability_experiment(programme: dict[str, Any]) -> dict[str, Any]:
    return next(item for item in programme["experiments"] if item["id"] == EXPERIMENT_ID)


def comparison_authorised(programme: dict[str, Any]) -> bool:
    experiment = reliability_experiment(programme)
    proposed = experiment.get("proposed_budget", {})
    confirmation = experiment.get("paid_budget_confirmation")
    return bool(
        programme.get("status") == "a02r_patch_reliability_approved"
        and programme.get("owner_mandate", {}).get("paid_model_or_provider_calls_authorised")
        is True
        and experiment.get("status") == "approved_one_run"
        and isinstance(confirmation, dict)
        and confirmation.get("confirmed") is True
        and confirmation.get("authorisation_consumed") is False
        and confirmation.get("approved_fault_scenarios") == proposed.get("fault_scenarios")
        and confirmation.get("approved_repetitions_per_scenario")
        == proposed.get("repetitions_per_scenario")
        and confirmation.get("approved_expected_model_calls")
        == proposed.get("expected_model_calls")
        and confirmation.get("approved_maximum_model_calls") == proposed.get("maximum_model_calls")
        and confirmation.get("approved_planner_calls") == proposed.get("planner_calls")
        and confirmation.get("approved_provider_calls") == proposed.get("provider_calls")
    )


def require_authorised_run_inputs(
    args: argparse.Namespace,
    experiment: dict[str, Any],
) -> None:
    confirmation = experiment.get("paid_budget_confirmation", {})
    if args.programme.resolve() != DEFAULT_PROGRAMME.resolve():
        raise SystemExit("Patch reliability requires the committed programme path.")
    expected = {
        "output": confirmation.get("approved_report_path"),
        "run_lock": confirmation.get("approved_run_lock_path"),
    }
    actual = {"output": args.output, "run_lock": args.run_lock}
    for name, approved in expected.items():
        if not isinstance(approved, str) or not approved.strip():
            raise SystemExit(f"Patch reliability lacks an approved {name} path.")
        if actual[name].resolve() != (ROOT / approved).resolve():
            raise SystemExit(f"The patch-reliability {name} path is not authorised.")


def summarise(samples: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [float(item["duration_seconds"]) for item in samples]
    qualities = [float(item["quality_score"]) for item in samples]
    return {
        "scheduled_samples": len(samples),
        "completed_samples": sum(item["status"] == "passed" for item in samples),
        "mean_quality_all_scheduled": round(statistics.fmean(qualities), 2) if qualities else 0.0,
        "p50_latency_seconds": round(percentile(durations, 0.5), 3),
        "p95_latency_seconds": round(percentile(durations, 0.95), 3),
        "total_model_calls": sum(int(item["model_calls"]) for item in samples),
        "total_tokens": sum(int(item["total_tokens"]) for item in samples),
        "citation_and_schema_validity_ratio": round(
            sum(item["citation_and_schema_valid"] is True for item in samples) / len(samples), 4
        )
        if samples
        else 0.0,
        "accepted_field_preservation_ratio": round(
            sum(item["accepted_fields_preserved"] is True for item in samples) / len(samples), 4
        )
        if samples
        else 0.0,
        "token_telemetry_complete_ratio": round(
            sum(int(item["total_tokens"]) > 0 for item in samples) / len(samples), 4
        )
        if samples
        else 0.0,
    }


def per_scenario_summary(samples: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        scenario: {
            "scheduled_samples": len(selected),
            "completed_samples": sum(item["status"] == "passed" for item in selected),
        }
        for scenario in SCENARIOS
        if (selected := [item for item in samples if item["scenario"] == scenario])
    }


def evaluate_targets(
    samples: list[dict[str, Any]],
    summary: dict[str, Any],
    experiment: dict[str, Any],
    *,
    transport_calls: int,
) -> list[dict[str, str]]:
    gate = experiment["machine_gate"]
    budget = experiment["proposed_budget"]
    expected_samples = int(gate["scheduled_samples"])
    scenario_summary = per_scenario_summary(samples)
    checks = {
        "complete_scheduled_sample_set": len(samples) == expected_samples,
        "completion_ratio": summary["completed_samples"] == expected_samples,
        "per_scenario_completion": all(
            item["scheduled_samples"] == REPETITIONS and item["completed_samples"] == REPETITIONS
            for item in scenario_summary.values()
        )
        and len(scenario_summary) == len(SCENARIOS),
        "citation_and_schema_validity": (
            summary["citation_and_schema_validity_ratio"]
            == gate["citation_and_schema_validity_ratio"]
        ),
        "accepted_field_preservation": (
            summary["accepted_field_preservation_ratio"]
            == gate["accepted_field_preservation_ratio"]
        ),
        "mean_quality": summary["mean_quality_all_scheduled"] >= gate["minimum_mean_quality"],
        "p95_latency": (summary["p95_latency_seconds"] <= gate["p95_latency_seconds_maximum"]),
        "total_tokens": summary["total_tokens"] <= gate["total_tokens_maximum"],
        "token_telemetry_complete": (
            summary["token_telemetry_complete_ratio"] == gate["token_telemetry_complete_ratio"]
        ),
        "model_call_budget": (
            budget["expected_model_calls"]
            <= summary["total_model_calls"]
            <= budget["maximum_model_calls"]
        ),
        "transport_call_telemetry_complete": summary["total_model_calls"] == transport_calls,
        "zero_planner_and_provider_budget": (
            budget["planner_calls"] == 0 and budget["provider_calls"] == 0
        ),
    }
    return [
        {"target_id": target_id, "status": "passed" if passed else "failed"}
        for target_id, passed in checks.items()
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen targeted structural-patch reliability gate once."
    )
    parser.add_argument("--programme", type=Path, default=DEFAULT_PROGRAMME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-lock", type=Path, default=DEFAULT_RUN_LOCK)
    return parser.parse_args()


def main_cli() -> int:
    args = parse_args()
    programme = json.loads(args.programme.read_text(encoding="utf-8"))
    if not comparison_authorised(programme):
        raise SystemExit("The autonomous programme does not authorise patch reliability.")
    if not main.local_agent_enabled():
        raise SystemExit("Set FIRSTROLL_LOCAL_AGENT_ENABLED=1 for patch reliability.")
    experiment = reliability_experiment(programme)
    require_authorised_run_inputs(args, experiment)
    require_committed_source()
    if args.output.exists():
        raise SystemExit("The patch-reliability output path already exists.")
    if args.run_lock.exists():
        raise SystemExit("The private patch-reliability lock already exists.")
    validate_private_packet_output_path(args.run_lock)

    revision = source_revision()
    write_private_packets(
        args.run_lock,
        {
            "schema_version": 1,
            "programme_id": programme["programme_id"],
            "experiment_id": EXPERIMENT_ID,
            "source_revision": revision,
            "status": "consumed_on_start",
        },
    )
    packet = synthetic_packet()
    recorder = SafeRecordingTransport()
    service = DeepSeekStudyService(main.settings_store, transport=recorder)
    samples: list[dict[str, Any]] = []
    for repetition in range(1, REPETITIONS + 1):
        offset = (repetition - 1) % len(SCENARIOS)
        ordered = (*SCENARIOS[offset:], *SCENARIOS[:offset])
        for scenario in ordered:
            samples.append(run_patch_sample(service, packet, scenario, repetition))

    summary = summarise(samples)
    scenario_summary = per_scenario_summary(samples)
    targets = evaluate_targets(
        samples,
        summary,
        experiment,
        transport_calls=len(recorder.calls),
    )
    report = {
        "schema_version": 1,
        "programme_id": programme["programme_id"],
        "experiment_id": EXPERIMENT_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": revision,
        "historical_control_path": experiment["historical_control_path"],
        "fixture": {
            "kind": "synthetic_public_targeted_patch_reliability",
            "scenario_count": len(SCENARIOS),
            "repetitions_per_scenario": REPETITIONS,
        },
        "protocol": {
            "planner_calls": 0,
            "provider_calls": 0,
            "failures_scored_zero": True,
            "generated_responses_persisted": False,
        },
        "samples": samples,
        "scenario_summary": scenario_summary,
        "summary": {
            **summary,
            "machine_targets_passed": all(item["status"] == "passed" for item in targets),
        },
        "targets": targets,
    }
    assert_safe_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["machine_targets_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main_cli())
