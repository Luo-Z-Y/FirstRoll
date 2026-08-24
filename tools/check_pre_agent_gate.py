from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCORECARD = ROOT / "evals" / "pre_agent_scorecard.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "pre-agent-machine-gate-current.json"
DEFAULT_HUMAN_REVIEW = ROOT / ".firstroll" / "evaluations" / "human-packet-review-redacted.json"
MEASURED_LOCAL_STAGE_STATUSES = {"completed", "failed", "degraded"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def safe_evidence_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return path.name
    if relative.parts and relative.parts[0] == ".firstroll":
        return "local-only human packet review aggregate"
    return relative.as_posix()


def target_result(
    target_id: str,
    observed: float | int | None,
    *,
    evidence_path: str,
    status: str,
    threshold: float | int | None,
    comparison: str,
) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "status": status,
        "observed": observed,
        "comparison": comparison,
        "threshold": threshold,
        "evidence_path": evidence_path,
    }


def compare_target(
    target_id: str,
    observed: float | int,
    target: dict[str, Any],
    evidence_path: str,
) -> dict[str, Any]:
    comparison = target["comparison"]
    threshold = target["threshold"]
    if comparison == "eq":
        passed = observed == threshold
    elif comparison == "lt":
        passed = observed < threshold
    elif comparison == "lte":
        passed = observed <= threshold
    elif comparison == "gte":
        passed = observed >= threshold
    else:
        raise ValueError(f"Unsupported gate comparison: {comparison}")
    return target_result(
        target_id,
        observed,
        evidence_path=evidence_path,
        status="passed" if passed else "failed",
        threshold=threshold,
        comparison=comparison,
    )


def trace_coverage(workflow: dict[str, Any], stage_names: list[str]) -> float:
    cases = [case for case in workflow.get("cases", []) if case.get("status") == "passed"]
    expected = len(cases) * len(stage_names)
    if not expected:
        return 0.0
    covered = 0
    for case in cases:
        stages = {
            stage.get("name"): stage.get("status")
            for stage in case.get("study_observability", {}).get("stages", [])
        }
        covered += sum(stages.get(name) in MEASURED_LOCAL_STAGE_STATUSES for name in stage_names)
    return round(covered / expected, 4)


def citation_ratio(workflow: dict[str, Any]) -> float:
    completed = [case for case in workflow.get("cases", []) if case.get("status") == "passed"]
    if not completed:
        return 0.0
    return round(
        sum(case.get("quality", {}).get("valid_citations") is True for case in completed)
        / len(completed),
        4,
    )


def instruction_containment_ratio(synthetic: dict[str, Any]) -> float:
    flagged = [
        case["assessment"]["instruction_safety"]
        for case in synthetic.get("cases", [])
        if case.get("assessment", {}).get("instruction_safety", {}).get("flagged_items", 0)
        > 0
    ]
    if not flagged:
        return 0.0
    return round(
        sum(item.get("containment_boundary") is True for item in flagged) / len(flagged),
        4,
    )


def relative_p95_regression(scorecard: dict[str, Any]) -> float:
    reduction = scorecard["measured_checkpoints"]["synthesis_reliability"][
        "paired_p95_reduction_from_selection"
    ]
    return round(-float(reduction), 6)


def evaluate(scorecard: dict[str, Any], human_review_path: Path) -> list[dict[str, Any]]:
    checkpoints = scorecard["measured_checkpoints"]
    targets = scorecard["targets"]
    hierarchy_path = ROOT / checkpoints["ui_hierarchy"]["result_path"]
    state_path = ROOT / checkpoints["ui_states_accessibility"]["result_path"]
    packet_path = ROOT / checkpoints["packet_selection_candidate"]["packet_result_path"]
    synthetic_path = ROOT / checkpoints["packet_selection_candidate"]["synthetic_result_path"]
    workflow_path = ROOT / checkpoints["synthesis_reliability"]["result_path"]
    hierarchy = load_json(hierarchy_path)
    state = load_json(state_path)
    packet = load_json(packet_path)
    synthetic = load_json(synthetic_path)
    workflow = load_json(workflow_path)

    observed = {
        "stage_observability_ratio": trace_coverage(
            workflow, scorecard["latency_stages"]
        ),
        "ui_visible_response_p95_ms": hierarchy["summary"]["visible_response_p95_ms"],
        "ui_core_journey_blockers": hierarchy["summary"]["journey_blockers"],
        "ui_critical_accessibility_defects": state["summary"][
            "critical_accessibility_defects"
        ],
        "warm_packet_prepare_p95_seconds": round(
            packet["summary"]["warm"]["p95_ms"] / 1000, 6
        ),
        "median_prompt_tokens": checkpoints["synthesis_reliability"][
            "prompt_token_median"
        ],
        "p95_prompt_tokens": checkpoints["synthesis_reliability"]["prompt_token_p95"],
        "packet_duplicate_ratio": packet["summary"]["packet_quality"][
            "maximum_duplicate_ratio"
        ],
        "packet_provenance_completeness": packet["summary"]["packet_quality"][
            "mean_provenance_completeness"
        ],
        "packet_citation_integrity": citation_ratio(workflow),
        "retrieved_instruction_containment": instruction_containment_ratio(synthetic),
        "fixed_suite_completion_ratio": round(
            workflow["summary"]["successful_cases"] / workflow["summary"]["case_count"],
            4,
        ),
        "mean_quality_score_completed": workflow["summary"]["mean_quality_score"],
        "quality_gate_pass_ratio_completed": workflow["summary"]["quality_gate_pass_rate"],
        "paired_end_to_end_median_reduction": checkpoints["synthesis_reliability"][
            "paired_median_reduction_from_selection"
        ],
        "paired_end_to_end_p95_regression": relative_p95_regression(scorecard),
    }
    evidence_paths = {
        "stage_observability_ratio": checkpoints["synthesis_reliability"]["result_path"],
        "ui_visible_response_p95_ms": checkpoints["ui_hierarchy"]["result_path"],
        "ui_core_journey_blockers": checkpoints["ui_hierarchy"]["result_path"],
        "ui_critical_accessibility_defects": checkpoints["ui_states_accessibility"][
            "result_path"
        ],
        "warm_packet_prepare_p95_seconds": checkpoints["packet_selection_candidate"][
            "packet_result_path"
        ],
        "median_prompt_tokens": checkpoints["synthesis_reliability"]["result_path"],
        "p95_prompt_tokens": checkpoints["synthesis_reliability"]["result_path"],
        "packet_duplicate_ratio": checkpoints["packet_selection_candidate"][
            "packet_result_path"
        ],
        "packet_provenance_completeness": checkpoints["packet_selection_candidate"][
            "packet_result_path"
        ],
        "packet_citation_integrity": checkpoints["synthesis_reliability"]["result_path"],
        "retrieved_instruction_containment": checkpoints["packet_selection_candidate"][
            "synthetic_result_path"
        ],
        "fixed_suite_completion_ratio": checkpoints["synthesis_reliability"]["result_path"],
        "mean_quality_score_completed": checkpoints["synthesis_reliability"]["result_path"],
        "quality_gate_pass_ratio_completed": checkpoints["synthesis_reliability"]["result_path"],
        "paired_end_to_end_median_reduction": checkpoints["synthesis_reliability"][
            "result_path"
        ],
        "paired_end_to_end_p95_regression": checkpoints["synthesis_reliability"][
            "result_path"
        ],
    }
    results = [
        compare_target(target_id, value, targets[target_id], evidence_paths[target_id])
        for target_id, value in observed.items()
    ]

    human_target = targets["human_packet_pass_ratio"]
    if human_review_path.is_file():
        human_review = load_json(human_review_path)
        pass_ratio = human_review.get("summary", {}).get("pass_ratio")
        case_count = human_review.get("summary", {}).get("case_count")
        attested = human_review.get("reviewer_attested") is True
        if not isinstance(pass_ratio, (int, float)):
            raise ValueError("The human packet review has no numeric pass ratio.")
        if case_count != 5 or not attested:
            results.append(
                target_result(
                    "human_packet_pass_ratio",
                    float(pass_ratio),
                    evidence_path=safe_evidence_path(human_review_path),
                    status="pending_human_review",
                    threshold=human_target["threshold"],
                    comparison=human_target["comparison"],
                )
            )
        else:
            results.append(
                compare_target(
                    "human_packet_pass_ratio",
                    float(pass_ratio),
                    human_target,
                    safe_evidence_path(human_review_path),
                )
            )
    else:
        results.append(
            target_result(
                "human_packet_pass_ratio",
                None,
                evidence_path="local-only human packet review aggregate",
                status="pending_human_review",
                threshold=human_target["threshold"],
                comparison=human_target["comparison"],
            )
        )
    return results


def build_report(
    scorecard: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    revision: str | None = None,
) -> dict[str, Any]:
    required_targets = set(scorecard["agent_entry_gate"]["required_target_ids"])
    result_ids = {item["target_id"] for item in results}
    missing = required_targets - result_ids
    if missing:
        raise ValueError(f"Missing gate target results: {', '.join(sorted(missing))}")
    step_status = {item["id"]: item["status"] for item in scorecard["steps"]}
    required_steps = set(scorecard["agent_entry_gate"]["required_completed_steps"])
    incomplete_steps = sorted(
        step_id for step_id in required_steps if step_status.get(step_id) != "complete"
    )
    failures = [item for item in results if item["status"] == "failed"]
    pending = [item for item in results if item["status"].startswith("pending")]
    targets_ready = not failures and not pending
    entry_ready = targets_ready and not incomplete_steps
    return {
        "schema_version": 1,
        "suite_id": "firstroll-pre-agent-machine-gate-v1",
        "programme_id": scorecard["programme_id"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": revision or source_revision(),
        "summary": {
            "required_targets": len(required_targets),
            "passed_targets": sum(item["status"] == "passed" for item in results),
            "failed_targets": len(failures),
            "pending_targets": len(pending),
            "required_steps": len(required_steps),
            "completed_required_steps": len(required_steps) - len(incomplete_steps),
            "all_machine_targets_passed": not failures,
            "agent_entry_ready": entry_ready,
        },
        "targets": sorted(results, key=lambda item: item["target_id"]),
        "blocking_reasons": [
            *[f"failed:{item['target_id']}" for item in failures],
            *[f"pending:{item['target_id']}" for item in pending],
            *[f"incomplete:{step_id}" for step_id in incomplete_steps],
        ],
        "step_status": step_status,
        "privacy_scope": (
            "Reads versioned aggregate results and an optional redacted human score only; never "
            "loads packets, prompts, private books, source text, vectors or provider caches."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate FirstRoll's Pre-Agent scorecard without reading private evidence."
    )
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--human-review", type=Path, default=DEFAULT_HUMAN_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main_cli() -> int:
    args = parse_args()
    scorecard = load_json(args.scorecard)
    results = evaluate(scorecard, args.human_review)
    try:
        report = build_report(scorecard, results)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2), flush=True)
    print(f"Report: {args.output}", flush=True)
    return 1 if report["summary"]["failed_targets"] else 0


if __name__ == "__main__":
    sys.exit(main_cli())
