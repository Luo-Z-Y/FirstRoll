from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend import main
from app.backend.evidence import EvidencePacket
from app.backend.research_agent_contract import ResearchBudgets, TerminalStatus
from app.backend.research_graph import (
    ResearchGraphContext,
    ResearchGraphState,
    build_research_graph,
    initial_research_state,
)
from app.backend.study_observability import StudyTrace
from tools.evaluate_local_agent import (
    SafeRecordingTransport,
    assert_safe_report,
    case_specs,
    identity_matches,
    json_fingerprint,
    packet_fingerprint,
    safe_model_calls,
    safe_study_score,
    source_revision,
    write_private_packets,
)


DEFAULT_CASES = ROOT / "evals" / "agent_cases.json"
DEFAULT_REFERENCE = ROOT / "evals" / "results" / "baseline-reliability-2026-08-21.json"
DEFAULT_PROGRAMME = ROOT / "evals" / "text_agent_programme.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "text-agent-repeated-current.json"
DEFAULT_PRIVATE_PACKETS = ROOT / ".firstroll" / "evaluations" / "text-agent-packets.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def comparison_authorised(programme: dict[str, Any]) -> bool:
    owner = programme.get("owner_revision") or {}
    budget = programme.get("run_budget") or {}
    confirmation = programme.get("owner_budget_confirmation") or {}
    return bool(
        programme.get("status") == "approved_revised_local_comparison"
        and owner.get("decision") == "revise_text_agent"
        and budget.get("paid_run_requires_separate_budget_confirmation") is False
        and confirmation.get("confirmed") is True
        and confirmation.get("authorisation_consumed") is False
        and confirmation.get("approved_minimum_synthesis_calls")
        == budget.get("expected_minimum_synthesis_calls")
        and confirmation.get("approved_maximum_synthesis_calls")
        == budget.get("maximum_synthesis_calls")
        and confirmation.get("approved_maximum_planner_calls")
        == budget.get("maximum_acquisition_planner_calls")
        and confirmation.get("approved_maximum_external_provider_calls")
        == budget.get("maximum_external_provider_calls")
    )


def repetition_lane_order(repetition: int) -> tuple[str, str]:
    if repetition < 1:
        raise ValueError("Repetition numbers start at one.")
    return ("fixed", "agent") if repetition % 2 else ("agent", "fixed")


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = (len(ordered) - 1) * percentile_value
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def ratio(numerator: Any, denominator: Any) -> float | None:
    if not isinstance(numerator, (int, float)) or isinstance(numerator, bool):
        return None
    if not isinstance(denominator, (int, float)) or isinstance(denominator, bool):
        return None
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def summarise_lane(samples: list[dict[str, Any]], *, scheduled: int) -> dict[str, Any]:
    if len(samples) != scheduled:
        raise ValueError("Every scheduled generation sample must remain in the denominator.")
    completed = [sample for sample in samples if sample.get("status") == "passed"]
    quality_scores = [
        float(sample.get("quality", {}).get("score", 0.0) or 0.0)
        if sample.get("status") == "passed"
        else 0.0
        for sample in samples
    ]
    latencies = [float(sample.get("latency_seconds", 0.0) or 0.0) for sample in samples]
    model_calls = [
        call
        for sample in samples
        for call in sample.get("model_calls", [])
        if isinstance(call, dict)
    ]
    tokens = sum(int(call.get("usage", {}).get("total_tokens", 0) or 0) for call in model_calls)
    calls_with_token_usage = sum(
        isinstance(call.get("usage", {}).get("total_tokens"), int)
        and not isinstance(call.get("usage", {}).get("total_tokens"), bool)
        and call.get("usage", {}).get("total_tokens", 0) > 0
        for call in model_calls
    )
    quality_passes = sum(
        sample.get("quality", {}).get("quality_gate_status") == "passed" for sample in completed
    )
    valid_citations = sum(
        sample.get("quality", {}).get("valid_citations") is True for sample in completed
    )
    return {
        "scheduled_samples": scheduled,
        "completed_samples": len(completed),
        "failed_samples": scheduled - len(completed),
        "completion_ratio": round(len(completed) / scheduled, 6),
        "mean_quality_all_scheduled": round(statistics.fmean(quality_scores), 2),
        "quality_standard_deviation": round(statistics.pstdev(quality_scores), 2),
        "minimum_quality": round(min(quality_scores), 2),
        "maximum_quality": round(max(quality_scores), 2),
        "quality_gate_pass_ratio": round(quality_passes / scheduled, 6),
        "valid_citation_ratio": round(valid_citations / scheduled, 6),
        "p50_latency_seconds": percentile(latencies, 0.5),
        "p95_latency_seconds": percentile(latencies, 0.95),
        "model_calls": len(model_calls),
        "token_usage_complete_ratio": round(calls_with_token_usage / len(model_calls), 6)
        if model_calls
        else 0.0,
        "total_tokens": tokens,
    }


def compare_lanes(
    fixed_summary: dict[str, Any],
    agent_summary: dict[str, Any],
    *,
    acquisition_planner_tokens: int = 0,
    acquisition_planner_calls: int = 0,
) -> dict[str, Any]:
    return {
        "agent_minus_fixed_mean_quality": round(
            float(agent_summary["mean_quality_all_scheduled"])
            - float(fixed_summary["mean_quality_all_scheduled"]),
            2,
        ),
        "p50_latency_ratio": ratio(
            agent_summary.get("p50_latency_seconds"),
            fixed_summary.get("p50_latency_seconds"),
        ),
        "p95_latency_ratio": ratio(
            agent_summary.get("p95_latency_seconds"),
            fixed_summary.get("p95_latency_seconds"),
        ),
        "total_token_ratio": ratio(
            int(agent_summary.get("total_tokens", 0) or 0) + acquisition_planner_tokens,
            fixed_summary.get("total_tokens"),
        ),
        "agent_acquisition_planner_calls": acquisition_planner_calls,
        "agent_total_model_calls_including_acquisition": (
            int(agent_summary.get("model_calls", 0) or 0) + acquisition_planner_calls
        ),
        "agent_acquisition_planner_tokens": acquisition_planner_tokens,
        "agent_total_tokens_including_acquisition": (
            int(agent_summary.get("total_tokens", 0) or 0) + acquisition_planner_tokens
        ),
    }


def target_status(observed: Any, target: dict[str, Any]) -> str:
    threshold = target["threshold"]
    comparison = target["comparison"]
    if observed is None:
        return "failed"
    if comparison == "eq":
        return "passed" if observed == threshold else "failed"
    if comparison == "gte":
        return "passed" if observed >= threshold else "failed"
    if comparison == "lte":
        return "passed" if observed <= threshold else "failed"
    raise ValueError(f"Unknown target comparison: {comparison}")


def evaluate_targets(
    programme: dict[str, Any],
    fixed_summary: dict[str, Any],
    agent_summary: dict[str, Any],
    comparison: dict[str, Any],
    acquisition_cases: list[dict[str, Any]],
    samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sufficient_cases = [
        case for case in acquisition_cases if case.get("initial_packet_status") == "passed"
    ]
    sufficient_external_calls = sum(
        int(case.get("external_tool_calls", 0) or 0) for case in sufficient_cases
    )
    target_case = next(
        (
            case
            for case in acquisition_cases
            if case.get("case_id") == "the-thing-ambiguous-identity"
        ),
        {},
    )
    repeated_provider_calls = sum(
        len(case.get("attempted_tools", [])) - len(set(case.get("attempted_tools", [])))
        for case in acquisition_cases
    )
    observations = {
        "fixed_sample_completion_ratio": fixed_summary.get("completion_ratio"),
        "agent_sample_completion_ratio": agent_summary.get("completion_ratio"),
        "agent_mean_automated_quality": agent_summary.get("mean_quality_all_scheduled"),
        "agent_minus_fixed_mean_quality": comparison.get("agent_minus_fixed_mean_quality"),
        "quality_gate_pass_ratio": min(
            float(fixed_summary.get("quality_gate_pass_ratio", 0.0) or 0.0),
            float(agent_summary.get("quality_gate_pass_ratio", 0.0) or 0.0),
        ),
        "valid_citation_ratio": min(
            float(fixed_summary.get("valid_citation_ratio", 0.0) or 0.0),
            float(agent_summary.get("valid_citation_ratio", 0.0) or 0.0),
        ),
        "token_usage_complete_ratio": min(
            float(fixed_summary.get("token_usage_complete_ratio", 0.0) or 0.0),
            float(agent_summary.get("token_usage_complete_ratio", 0.0) or 0.0),
        ),
        "planner_token_usage_complete": all(
            int(case.get("planning_calls", 0) or 0) == 0
            or int(case.get("planner_total_tokens", 0) or 0) > 0
            for case in acquisition_cases
        ),
        "identity_match_ratio": round(
            sum(sample.get("identity_match") is True for sample in samples) / max(1, len(samples)),
            6,
        ),
        "instruction_containment_ratio": round(
            sum(case.get("instruction_containment") is True for case in acquisition_cases)
            / max(1, len(acquisition_cases)),
            6,
        ),
        "sufficient_packet_external_calls": sufficient_external_calls,
        "sufficient_packet_mutations": sum(
            case.get("packet_changed") is True for case in sufficient_cases
        ),
        "target_packet_final_status": target_case.get("final_packet_status"),
        "target_packet_changed": target_case.get("packet_changed"),
        "repeated_provider_calls": repeated_provider_calls,
        "repeated_p50_latency_ratio": comparison.get("p50_latency_ratio"),
        "repeated_p95_latency_ratio": comparison.get("p95_latency_ratio"),
        "repeated_total_token_ratio": comparison.get("total_token_ratio"),
    }
    return [
        {
            "target_id": target_id,
            "status": target_status(observations.get(target_id), target),
            "observed": observations.get(target_id),
            "comparison": target["comparison"],
            "threshold": target["threshold"],
        }
        for target_id, target in programme["comparison_targets"].items()
    ]


def _initial_state(spec: dict[str, Any]) -> ResearchGraphState:
    return initial_research_state(
        run_id=str(uuid4()),
        user_id="local-repeated-text-evaluation",
        question=spec["question"],
        film_query=spec["query"],
        film_id=spec["film_id"],
    )


def prepare_fixed_packet(spec: dict[str, Any]) -> tuple[EvidencePacket, dict[str, Any]]:
    film = main.discovery_service.detail(spec["film_id"])["film"]
    trace = StudyTrace()
    trace.skip("film_context")
    prepared = main.prepare_film_study(
        spec["film_id"],
        film,
        spec["question"],
        public_mode=False,
        trace=trace,
    )
    return prepared["packet"], film


def acquire_agent_packet(
    spec: dict[str, Any],
    expected_packet: EvidencePacket,
) -> tuple[dict[str, Any], EvidencePacket | None]:
    adapter = main.build_local_agent_services()
    graph = build_research_graph()
    state = _initial_state(spec)
    final = cast(
        ResearchGraphState,
        graph.invoke(
            state,
            context=ResearchGraphContext(
                services=adapter,
                budgets=ResearchBudgets(
                    max_graph_steps=8,
                    max_planning_calls=2,
                    max_external_tool_calls=2,
                    max_repair_calls=2,
                ),
                mode="evidence_only",
            ),
            config={"recursion_limit": 64},
        ),
    )
    metrics = adapter.safe_metrics(state["run_id"])
    initial_fingerprint = metrics["initial_packet_fingerprint"]
    expected_fingerprint = packet_fingerprint(expected_packet)
    if initial_fingerprint != expected_fingerprint:
        raise RuntimeError("The Agent and fixed lanes did not start from the same packet.")
    packet = adapter.private_packet(state["run_id"])
    initial_quality = metrics["initial_packet_quality"]
    final_quality = metrics["packet_quality"]
    result = {
        "case_id": spec["id"],
        "status": "passed" if final["status"] is TerminalStatus.EVIDENCE_READY else "failed",
        "terminal_status": final["status"].value,
        "initial_packet_status": initial_quality.get("status"),
        "final_packet_status": final_quality.get("status"),
        "initial_packet_fingerprint": initial_fingerprint,
        "packet_fingerprint": metrics["packet_fingerprint"],
        "planning_calls": final["planning_calls"],
        "planner_total_tokens": metrics["planner_total_tokens"],
        "external_tool_calls": final["external_tool_calls"],
        "attempted_tools": [tool.value for tool in final["attempted_tools"]],
        "tool_attempts": metrics["tool_attempts"],
        "acquired_reviews": metrics["acquired_reviews"],
        "acquired_videos": metrics["acquired_videos"],
        "instruction_containment": bool(
            final_quality.get("instruction_safety", {}).get("containment_boundary")
        ),
        "packet_changed": metrics["packet_fingerprint"] != initial_fingerprint,
    }
    return result, packet if result["status"] == "passed" else None


def run_synthesis_sample(
    spec: dict[str, Any],
    packet: EvidencePacket,
    *,
    lane: str,
    repetition: int,
    recorder: SafeRecordingTransport,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    call_start = len(recorder.calls)
    result: dict[str, Any] = {
        "case_id": spec["id"],
        "lane": lane,
        "repetition": repetition,
        "status": "failed",
        "terminal_status": "failed_safe",
        "identity_match": False,
        "quality": {"score": 0.0, "valid_citations": False},
        "packet_fingerprint": packet_fingerprint(packet),
        "graph_counts": {"steps": 0, "synthesis_calls": 0, "repair_calls": 0},
        "study_attempts": [],
    }
    try:
        adapter = main.build_local_agent_services().for_frozen_packet(packet)
        graph = build_research_graph()
        state = _initial_state(spec)
        final = cast(
            ResearchGraphState,
            graph.invoke(
                state,
                context=ResearchGraphContext(
                    services=adapter,
                    budgets=ResearchBudgets(
                        max_graph_steps=6,
                        max_planning_calls=0,
                        max_external_tool_calls=0,
                        max_repair_calls=2,
                        max_total_model_calls=3,
                    ),
                    mode="synthesis_only",
                ),
                config={"recursion_limit": 64},
            ),
        )
        metrics = adapter.safe_metrics(state["run_id"])
        draft = final.get("draft") if isinstance(final.get("draft"), dict) else {}
        identity_ok = identity_matches(packet.film_record, spec["expected"])
        completed = final["status"] is TerminalStatus.COMPLETE and identity_ok
        result.update(
            status="passed" if completed else "failed",
            terminal_status=final["status"].value,
            identity_match=identity_ok,
            quality=safe_study_score(draft, identity_ok=identity_ok),
            graph_counts={
                "steps": final["step_count"],
                "synthesis_calls": final["synthesis_calls"],
                "repair_calls": final["repair_calls"],
            },
            study_attempts=metrics["study_attempts"],
        )
    except Exception as exc:
        result["failure_type"] = type(exc).__name__
    finally:
        result["latency_seconds"] = round(time.perf_counter() - started_at, 3)
        result["model_calls"] = safe_model_calls(recorder, call_start)
    return result


def failed_synthesis_sample(
    case_id: str,
    lane: str,
    repetition: int,
    *,
    terminal_status: str,
    failure_type: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case_id": case_id,
        "lane": lane,
        "repetition": repetition,
        "status": "failed",
        "terminal_status": terminal_status,
        "identity_match": False,
        "quality": {"score": 0.0, "valid_citations": False},
        "latency_seconds": 0.0,
        "graph_counts": {"steps": 0, "synthesis_calls": 0, "repair_calls": 0},
        "study_attempts": [],
        "model_calls": [],
    }
    if failure_type:
        result["failure_type"] = failure_type
    return result


def build_report(
    *,
    programme: dict[str, Any],
    suite_id: str,
    suite_fingerprint: str,
    acquisition_cases: list[dict[str, Any]],
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    repetitions = int(programme["comparison_protocol"]["generation_repetitions_per_lane_per_case"])
    case_count = int(programme["comparison_protocol"]["case_count"])
    scheduled = repetitions * case_count
    fixed_samples = [sample for sample in samples if sample.get("lane") == "fixed"]
    agent_samples = [sample for sample in samples if sample.get("lane") == "agent"]
    fixed_summary = summarise_lane(fixed_samples, scheduled=scheduled)
    agent_summary = summarise_lane(agent_samples, scheduled=scheduled)
    comparison = compare_lanes(
        fixed_summary,
        agent_summary,
        acquisition_planner_tokens=sum(
            int(case.get("planner_total_tokens", 0) or 0) for case in acquisition_cases
        ),
        acquisition_planner_calls=sum(
            int(case.get("planning_calls", 0) or 0) for case in acquisition_cases
        ),
    )
    targets = evaluate_targets(
        programme,
        fixed_summary,
        agent_summary,
        comparison,
        acquisition_cases,
        samples,
    )
    machine_passed = all(target["status"] == "passed" for target in targets)
    report = {
        "schema_version": 2,
        "programme_id": programme["programme_id"],
        "suite_id": suite_id,
        "suite_fingerprint": suite_fingerprint,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": source_revision(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "model": main.study_service.model,
            "local_agent_enabled": main.local_agent_enabled(),
        },
        "protocol": {
            "generation_repetitions_per_lane_per_case": repetitions,
            "scheduled_generation_samples_per_lane": scheduled,
            "maximum_repairs_per_sample": 2,
            "failures_scored_zero": True,
            "alternating_lane_order": True,
            "packet_acquired_once_before_generation": True,
            "same_generation_controller_for_both_lanes": True,
        },
        "summary": {
            "fixed": fixed_summary,
            "agent": agent_summary,
            "comparison": comparison,
            "local_machine_targets_passed": machine_passed,
            "human_packet_review_ready": machine_passed,
            "production_cutover_ready": False,
        },
        "targets": targets,
        "acquisition_cases": acquisition_cases,
        "samples": samples,
        "privacy_scope": (
            "Aggregate packet, quality, attempt, timing, token and tool fields only; no prompts, "
            "film questions, generated prose, source text, private passages or credentials."
        ),
    }
    assert_safe_report(report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the revised isolated repeated local text-Agent comparison."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--programme", type=Path, default=DEFAULT_PROGRAMME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--private-packets", type=Path, default=DEFAULT_PRIVATE_PACKETS)
    return parser.parse_args()


def main_cli() -> int:
    args = parse_args()
    programme = load_json(args.programme)
    if os.getenv("FIRSTROLL_LOCAL_AGENT_ENABLED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise SystemExit("Set FIRSTROLL_LOCAL_AGENT_ENABLED=1 explicitly.")
    if not comparison_authorised(programme):
        raise SystemExit(
            "The machine-readable decision does not authorise another repeated comparison."
        )
    suite_id, specs = case_specs(args.cases, args.reference)
    expected_count = int(programme["comparison_protocol"]["case_count"])
    if len(specs) != expected_count:
        raise SystemExit("The complete frozen five-case suite is required.")
    repetitions = int(programme["comparison_protocol"]["generation_repetitions_per_lane_per_case"])
    if repetitions != 3:
        raise SystemExit("The frozen revised protocol requires exactly three repetitions.")

    main.library_index.wait_for_embedding_warmup(timeout=300)
    recorder = SafeRecordingTransport()
    original_transport = main.study_service._transport
    main.study_service._transport = recorder
    acquisition_cases: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    private_cases: list[dict[str, Any]] = []
    try:
        for spec in specs:
            try:
                fixed_packet, _ = prepare_fixed_packet(spec)
                acquisition, agent_packet = acquire_agent_packet(spec, fixed_packet)
            except Exception as exc:
                acquisition_cases.append(
                    {
                        "case_id": spec["id"],
                        "status": "failed",
                        "terminal_status": "failed_safe",
                        "initial_packet_status": "unknown",
                        "final_packet_status": "unknown",
                        "planning_calls": 0,
                        "planner_total_tokens": 0,
                        "external_tool_calls": 0,
                        "attempted_tools": [],
                        "tool_attempts": [],
                        "acquired_reviews": 0,
                        "acquired_videos": 0,
                        "instruction_containment": False,
                        "packet_changed": False,
                        "failure_type": type(exc).__name__,
                    }
                )
                for repetition in range(1, repetitions + 1):
                    for lane in repetition_lane_order(repetition):
                        samples.append(
                            failed_synthesis_sample(
                                spec["id"],
                                lane,
                                repetition,
                                terminal_status="packet_preparation_failed",
                                failure_type=type(exc).__name__,
                            )
                        )
                continue
            acquisition_cases.append(acquisition)
            if agent_packet is None:
                for repetition in range(1, repetitions + 1):
                    for lane in repetition_lane_order(repetition):
                        if lane == "fixed":
                            samples.append(
                                run_synthesis_sample(
                                    spec,
                                    fixed_packet,
                                    lane="fixed",
                                    repetition=repetition,
                                    recorder=recorder,
                                )
                            )
                        else:
                            samples.append(
                                failed_synthesis_sample(
                                    spec["id"],
                                    "agent",
                                    repetition,
                                    terminal_status=acquisition["terminal_status"],
                                )
                            )
                continue
            if acquisition["packet_changed"]:
                private_cases.append({"case_id": spec["id"], "packet": agent_packet.model_dump()})
            packets = {"fixed": fixed_packet, "agent": agent_packet}
            for repetition in range(1, repetitions + 1):
                for lane in repetition_lane_order(repetition):
                    samples.append(
                        run_synthesis_sample(
                            spec,
                            packets[lane],
                            lane=lane,
                            repetition=repetition,
                            recorder=recorder,
                        )
                    )
    finally:
        main.study_service._transport = original_transport

    report = build_report(
        programme=programme,
        suite_id=suite_id,
        suite_fingerprint=json_fingerprint(args.cases),
        acquisition_cases=acquisition_cases,
        samples=samples,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if report["summary"]["local_machine_targets_passed"]:
        write_private_packets(
            args.private_packets,
            {
                "schema_version": 1,
                "programme_id": programme["programme_id"],
                "source_revision": report["source_revision"],
                "suite_fingerprint": report["suite_fingerprint"],
                "cases": private_cases,
            },
        )
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["local_machine_targets_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main_cli())
