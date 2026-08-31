from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"
DEFAULT_OUTPUT = RESULTS / "agent-benchmark-audit-current.json"
INPUT_PATHS = {
    "fixed_reliability": RESULTS / "baseline-reliability-2026-08-21.json",
    "original_agent": RESULTS / "local-agent-paired-2026-08-24.json",
    "repeated_agent": RESULTS / "text-agent-repeated-2026-08-25.json",
    "structural_agent": RESULTS / "text-agent-structural-repair-2026-08-25.json",
    "acquisition_ablation": RESULTS / "autonomous-agent-acquisition-2026-08-28.json",
    "repair_ablation": RESULTS / "autonomous-agent-repair-2026-08-28.json",
    "packet_latency": RESULTS / "packet-latency-prewarm-2026-08-21.json",
    "tooling_smoke": RESULTS / "benchmark-tooling-smoke-2026-08-31.json",
    "programme": ROOT / "evals" / "autonomous_agent_programme.json",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Benchmark input must be a JSON object: {path}")
    return value


def source_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_packet_quality(report: dict[str, Any]) -> dict[str, Any]:
    changed_cases = {
        item["case_id"]
        for item in report["acquisition_cases"]
        if item.get("packet_changed") is True
    }
    scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for sample in report["samples"]:
        case_id = str(sample.get("case_id") or "")
        if case_id not in changed_cases:
            continue
        quality = sample.get("quality")
        score = quality.get("score") if isinstance(quality, dict) else None
        lane = str(sample.get("lane") or "")
        if isinstance(score, int | float) and not isinstance(score, bool) and lane:
            scores[case_id][lane].append(float(score))
    values = []
    for case_id in sorted(changed_cases):
        fixed = scores[case_id].get("fixed", [])
        agent = scores[case_id].get("agent", [])
        fixed_mean = round(statistics.mean(fixed), 2) if fixed else None
        agent_mean = round(statistics.mean(agent), 2) if agent else None
        values.append(
            {
                "case_id": case_id,
                "fixed_mean_quality": fixed_mean,
                "agent_mean_quality": agent_mean,
                "agent_minus_fixed": (
                    round(agent_mean - fixed_mean, 2)
                    if fixed_mean is not None and agent_mean is not None
                    else None
                ),
            }
        )
    return {"changed_case_count": len(changed_cases), "cases": values}


def experiment(programme: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    return next(item for item in programme["experiments"] if item["id"] == experiment_id)


def build_audit(
    *,
    recorded_at: str,
    benchmark_subject_revision: str,
) -> dict[str, Any]:
    inputs = {name: load_json(path) for name, path in INPUT_PATHS.items()}
    fixed = inputs["fixed_reliability"]
    paired = inputs["original_agent"]
    repeated = inputs["repeated_agent"]
    structural = inputs["structural_agent"]
    acquisition = inputs["acquisition_ablation"]
    repair = inputs["repair_ablation"]
    packet = inputs["packet_latency"]
    tooling = inputs["tooling_smoke"]
    programme = inputs["programme"]

    acquisition_lanes = {item["lane"]: item for item in acquisition["lanes"]}
    a01r = experiment(programme, "A01R")
    a02r = experiment(programme, "A02R")
    a03 = experiment(programme, "A03")

    artefacts = [
        {
            "name": name,
            "path": str(path.relative_to(ROOT)),
            "sha256": fingerprint(path),
            "source_revision": inputs[name].get("source_revision"),
        }
        for name, path in INPUT_PATHS.items()
    ]

    return {
        "schema_version": 1,
        "audit_id": "firstroll-agent-benchmark-audit-v1",
        "recorded_at": recorded_at,
        "benchmark_subject_revision": benchmark_subject_revision,
        "scope": (
            "Redacted synthesis of immutable FirstRoll benchmark artefacts plus mock-only "
            "third-party tooling qualification; this audit makes no model or provider call."
        ),
        "input_artefacts": artefacts,
        "current_benchmark": {
            "fixed_workflow_reference": {
                "source_revision": fixed["source_revision"],
                "observations": fixed["summary"]["case_count"],
                "completion_ratio": round(
                    fixed["summary"]["successful_cases"] / fixed["summary"]["case_count"], 4
                ),
                "mean_quality": fixed["summary"]["mean_quality_score"],
                "p50_end_to_end_seconds": fixed["summary"]["latency_seconds"]["p50_end_to_end"],
                "p95_end_to_end_seconds": fixed["summary"]["latency_seconds"]["p95_end_to_end"],
                "model_calls": fixed["summary"]["model_calls"],
                "total_tokens": fixed["summary"]["total_tokens"],
                "interpretation": "five-case capability checkpoint, not reliability evidence",
            },
            "original_local_agent": {
                "source_revision": paired["source_revision"],
                "fixed_completion_ratio": round(
                    paired["summary"]["fixed"]["successful_cases"]
                    / paired["summary"]["fixed"]["case_count"],
                    4,
                ),
                "agent_completion_ratio": round(
                    paired["summary"]["agent"]["successful_cases"]
                    / paired["summary"]["agent"]["case_count"],
                    4,
                ),
                "fixed_mean_quality": paired["summary"]["fixed"]["mean_quality_score"],
                "agent_mean_quality": paired["summary"]["agent"]["mean_quality_score"],
                "machine_targets_passed": paired["summary"]["local_machine_targets_passed"],
            },
            "repeated_synthesis": {
                "source_revision": repeated["source_revision"],
                "scheduled_samples_per_lane": repeated["summary"]["fixed"]["scheduled_samples"],
                "fixed_completion_ratio": repeated["summary"]["fixed"]["completion_ratio"],
                "agent_completion_ratio": repeated["summary"]["agent"]["completion_ratio"],
                "agent_minus_fixed_mean_quality": repeated["summary"]["comparison"][
                    "agent_minus_fixed_mean_quality"
                ],
                "p50_latency_ratio": repeated["summary"]["comparison"]["p50_latency_ratio"],
                "p95_latency_ratio": repeated["summary"]["comparison"]["p95_latency_ratio"],
                "token_ratio": repeated["summary"]["comparison"]["total_token_ratio"],
                "machine_targets_passed": repeated["summary"]["local_machine_targets_passed"],
            },
            "structural_revision": {
                "source_revision": structural["source_revision"],
                "scheduled_samples_per_lane": structural["summary"]["fixed"]["scheduled_samples"],
                "fixed_completion_ratio": structural["summary"]["fixed"]["completion_ratio"],
                "agent_completion_ratio": structural["summary"]["agent"]["completion_ratio"],
                "agent_minus_fixed_mean_quality": structural["summary"]["comparison"][
                    "agent_minus_fixed_mean_quality"
                ],
                "p50_latency_ratio": structural["summary"]["comparison"]["p50_latency_ratio"],
                "p95_latency_ratio": structural["summary"]["comparison"]["p95_latency_ratio"],
                "token_ratio": structural["summary"]["comparison"]["total_token_ratio"],
                "repair_samples_observed": (
                    structural["summary"]["agent"]["targeted_structural_repair_samples"]
                    + structural["summary"]["agent"]["targeted_quality_repair_samples"]
                    + structural["summary"]["agent"]["full_regeneration_samples"]
                ),
                "machine_targets_passed": structural["summary"]["local_machine_targets_passed"],
                "evaluation_artefacts_complete": structural["summary"][
                    "evaluation_artifacts_complete"
                ],
                "changed_packet_quality": changed_packet_quality(structural),
            },
            "A01_acquisition_ablation": {
                "source_revision": acquisition["source_revision"],
                "model_planner_calls": acquisition_lanes["model_gap_planner"][
                    "model_planner_calls"
                ],
                "physical_provider_observations": acquisition["source_pool"][
                    "physical_provider_calls"
                ],
                "deterministic_lane_status": acquisition_lanes["deterministic_gap_router"][
                    "status"
                ],
                "model_lane_status": acquisition_lanes["model_gap_planner"]["status"],
                "machine_targets_passed": acquisition["summary"]["machine_targets_passed"],
                "human_review_ready": acquisition["summary"]["human_review_ready"],
            },
            "A02_repair_ablation": {
                "source_revision": repair["source_revision"],
                "targeted_patch_scheduled": repair["summary"]["targeted_field_patch"][
                    "scheduled_samples"
                ],
                "targeted_patch_completed": repair["summary"]["targeted_field_patch"][
                    "completed_samples"
                ],
                "targeted_patch_valid_ratio": repair["summary"]["targeted_field_patch"][
                    "valid_output_ratio"
                ],
                "targeted_patch_p95_seconds": repair["summary"]["targeted_field_patch"][
                    "p95_latency_seconds"
                ],
                "regeneration_completed": repair["summary"]["complete_regeneration"][
                    "completed_samples"
                ],
                "regeneration_valid_ratio": repair["summary"]["complete_regeneration"][
                    "valid_output_ratio"
                ],
                "machine_targets_passed": repair["summary"]["machine_targets_passed"],
            },
            "packet_preparation": {
                "source_revision": packet["source_revision"],
                "samples": packet["summary"]["sample_count"],
                "failed_samples": packet["summary"]["failed_samples"],
                "cold_p95_ms": packet["summary"]["cold"]["p95_ms"],
                "warm_p95_ms": packet["summary"]["warm"]["p95_ms"],
                "scope": "model-free packet preparation after explicit encoder prewarm",
            },
            "current_unrun_gates": {
                "A01R": {
                    "status": a01r["status"],
                    "planner_protocol": a01r["planner_protocol"]["request"],
                    "paid_budget_confirmed": a01r["paid_budget_confirmation"] is not None,
                },
                "A02R": {
                    "status": a02r["status"],
                    "scheduled_samples": a02r["machine_gate"]["scheduled_samples"],
                    "paid_budget_confirmed": a02r["paid_budget_confirmation"] is not None,
                },
                "A03": {
                    "status": a03["status"],
                    "paid_budget_confirmed": a03["paid_budget_confirmation"] is not None,
                },
            },
        },
        "third_party_tooling": {
            "qualification_report": "evals/results/benchmark-tooling-smoke-2026-08-31.json",
            "qualification_status": tooling["qualification_status"],
            "guidellm_version": tooling["tools"]["guidellm"]["version"],
            "lm_eval_version": tooling["tools"]["lm_evaluation_harness"]["version"],
            "external_model_provider_calls": tooling["external_model_provider_calls"],
            "current_firstroll_performance_measured": False,
            "current_firstroll_quality_measured": False,
        },
        "coverage_assessment": [
            {
                "dimension": "fixed_workflow_capability",
                "status": "measured_five_cases_not_reliability",
            },
            {
                "dimension": "agent_completion_and_quality",
                "status": "historical_mixed_results_current_revision_unmeasured",
            },
            {
                "dimension": "native_tool_call_provider_compatibility",
                "status": "synthetic_only",
            },
            {
                "dimension": "planner_value_against_deterministic_router",
                "status": "not_demonstrated",
            },
            {
                "dimension": "targeted_patch_capability",
                "status": "promising_nine_samples_reliability_unmeasured",
            },
            {
                "dimension": "changed_packet_causal_study_value",
                "status": "not_demonstrated",
            },
            {
                "dimension": "owner_attested_agent_usefulness",
                "status": "absent",
            },
            {
                "dimension": "serving_ttft_itl_and_concurrency",
                "status": "not_applicable_until_benchmark_endpoint_exists",
            },
            {
                "dimension": "claim_audit_edit_and_coach_provider_behaviour",
                "status": "synthetic_only",
            },
        ],
        "improvement_priorities": [
            {
                "priority": 1,
                "id": "validate_native_acquisition_causally",
                "action": "Run A01R once under its frozen class-aware and native-protocol gate, then obtain personal blinded packet review.",
                "blocked_by": "fresh_exact_A01R_budget",
            },
            {
                "priority": 2,
                "id": "establish_patch_reliability",
                "action": "Run A02R's 24 controlled patch samples and retain every failed or second-call sample.",
                "blocked_by": "fresh_exact_A02R_budget",
            },
            {
                "priority": 3,
                "id": "prove_changed_packet_study_value",
                "action": "Run A03 only with the exact accepted A01R packet and owner-review repetitions 1, 5 and 10.",
                "blocked_by": "A01R_machine_and_human_pass_plus_fresh_A03_budget",
            },
            {
                "priority": 4,
                "id": "add_model_level_grounding_diagnostics",
                "action": "Run the 12-case commit-safe lm-eval claim-support task as a diagnostic; do not substitute it for FirstRoll graph or human gates.",
                "blocked_by": "separate_exact_12_call_model_budget_and_fresh_private_output",
            },
            {
                "priority": 5,
                "id": "measure_serving_only_when_representative",
                "action": "Use GuideLLM first for single-stream native planner transport, then bounded concurrency only against an authorised benchmark endpoint; never report mock throughput as FirstRoll performance.",
                "blocked_by": "representative_OpenAI_compatible_benchmark_endpoint_and_exact_request_budget",
            },
            {
                "priority": 6,
                "id": "broaden_reliability",
                "action": "Collect at least twenty comparable observations per retained critical strategy and validate audit, edit and coach with the real provider before hosted routing.",
                "blocked_by": "earlier_causal_gates",
            },
        ],
        "conclusion": {
            "fixed_production_workflow_retained": True,
            "autonomous_agent_value_demonstrated": False,
            "autonomous_agent_reliable": False,
            "native_tool_calling_provider_validated": False,
            "targeted_patch_is_promising": True,
            "third_party_tooling_ready_for_bounded_future_runs": True,
            "new_paid_benchmark_authorised": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a redacted audit of FirstRoll's existing Agent benchmark evidence."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--recorded-at", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--subject-revision", default=source_revision())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_audit(
        recorded_at=str(args.recorded_at),
        benchmark_subject_revision=str(args.subject_revision),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["conclusion"], indent=2))
    print(f"Report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
