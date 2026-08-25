from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend import main
from app.backend.local_research_agent import LocalResearchGraphServices
from app.backend.packet_quality import assess_evidence_packet
from app.backend.research_agent_contract import ResearchBudgets, TerminalStatus
from app.backend.research_graph import (
    ResearchGraphContext,
    ResearchGraphState,
    build_research_graph,
    initial_research_state,
)
from app.backend.study_observability import StudyTrace
from app.backend.study_service import DeepSeekStudyService
warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)
from tools.evaluate_workflow import aggregate, configuration_fingerprint, identity_matches, score_study


DEFAULT_CASES = ROOT / "evals" / "agent_cases.json"
DEFAULT_REFERENCE = ROOT / "evals" / "results" / "baseline-reliability-2026-08-21.json"
DEFAULT_DECISION = ROOT / "evals" / "agent_go_no_go.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "local-agent-paired-current.json"
DEFAULT_PRIVATE_PACKETS = ROOT / ".firstroll" / "evaluations" / "local-agent-packets.json"
FORBIDDEN_REPORT_KEYS = frozenset(
    {
        "content",
        "directors",
        "draft",
        "evidence_packet",
        "excerpt",
        "film_record",
        "lens",
        "messages",
        "private_note",
        "prompt",
        "question",
        "reviews",
        "title",
        "videos",
    }
)
HUMAN_TARGETS = frozenset(
    {
        "human_packet_passed_cases",
        "failed_case_source_diversity",
        "failed_case_filmmaker_actionability",
    }
)
DEFERRED_CUTOVER_TARGETS = frozenset({"visible_response_p95_ms"})


@dataclass
class SafeRecordingTransport:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        started_at = time.perf_counter()
        response: dict[str, Any] | None = None
        status = "failed"
        try:
            response = DeepSeekStudyService._request_json(url, payload, key)
            status = "completed"
            return response
        finally:
            raw_usage = response.get("usage") if isinstance(response, dict) else None
            usage = {
                name: value
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")
                if isinstance(raw_usage, dict)
                and isinstance((value := raw_usage.get(name)), int)
                and not isinstance(value, bool)
                and value >= 0
            }
            self.calls.append(
                {
                    "endpoint": url.rsplit("/", 1)[-1],
                    "status": status,
                    "latency_seconds": round(time.perf_counter() - started_at, 3),
                    "model": str(response.get("model") or "")[:100]
                    if isinstance(response, dict)
                    else None,
                    "usage": usage,
                }
            )


def source_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def json_fingerprint(path: Path) -> str:
    payload = load_json(path)
    serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]


def comparison_authorised(decision: dict[str, Any]) -> bool:
    owner_decision = decision.get("owner_decision") or {}
    return bool(
        decision.get("status") == "approved_bounded_local_comparison"
        and owner_decision.get("decision") == "go_bounded_local_comparison"
    )


def case_specs(cases_path: Path, reference_path: Path) -> tuple[str, list[dict[str, Any]]]:
    suite = load_json(cases_path)
    reference = load_json(reference_path)
    identities = {
        item["case_id"]: item.get("resolved_film", {}).get("id")
        for item in reference.get("cases", [])
    }
    specs = []
    for case in suite.get("cases", []):
        case_id = str(case.get("id") or "")
        film_id = str(identities.get(case_id) or "")
        if not case_id or not film_id:
            raise ValueError(f"No canonical film identity is available for {case_id or '?'}.")
        specs.append({**case, "film_id": film_id})
    return str(suite["suite_id"]), specs


def full_suite_selected(
    *,
    suite_id: str,
    suite_fingerprint: str,
    case_count: int,
    subset_requested: bool,
    expected_case_count: int,
) -> bool:
    return bool(
        not subset_requested
        and suite_id == "firstroll-agent-comparison-v1"
        and suite_fingerprint == json_fingerprint(DEFAULT_CASES)
        and case_count == expected_case_count
    )


def safe_study_score(study: dict[str, Any], *, identity_ok: bool) -> dict[str, Any]:
    score = score_study(study, identity_ok=identity_ok)
    score["quality_gate_failed_sections"] = [
        {
            key: item[key]
            for key in ("section", "score", "issues")
            if key in item
        }
        for item in score.get("quality_gate_failed_sections", [])
        if isinstance(item, dict)
    ]
    return score


def packet_fingerprint(packet: Any) -> str:
    return hashlib.sha256(packet.model_dump_json().encode("utf-8")).hexdigest()[:16]


def warm_evidence(specs: list[dict[str, Any]]) -> dict[str, str]:
    main.library_index.wait_for_embedding_warmup(timeout=300)
    fingerprints: dict[str, str] = {}
    for spec in specs:
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
        fingerprints[spec["id"]] = packet_fingerprint(prepared["packet"])
    return fingerprints


def safe_model_calls(recorder: SafeRecordingTransport, start: int) -> list[dict[str, Any]]:
    return [dict(item) for item in recorder.calls[start:]]


def run_fixed_case(
    spec: dict[str, Any],
    recorder: SafeRecordingTransport,
    expected_packet_fingerprint: str,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    call_start = len(recorder.calls)
    result: dict[str, Any] = {
        "case_id": spec["id"],
        "status": "failed",
        "failure_stage": None,
        "identity_match": False,
    }
    trace = StudyTrace()
    try:
        result["failure_stage"] = "film_context"
        with trace.stage("film_context"):
            film = main.discovery_service.detail(spec["film_id"])["film"]
        identity_ok = identity_matches(film, spec["expected"])
        result["identity_match"] = identity_ok
        if not identity_ok:
            raise RuntimeError("The fixed control resolved the wrong film identity.")
        result["failure_stage"] = "packet_preparation"
        prepared = main.prepare_film_study(
            spec["film_id"],
            film,
            spec["question"],
            public_mode=False,
            trace=trace,
        )
        packet = prepared["packet"]
        fingerprint = packet_fingerprint(packet)
        result["initial_packet_fingerprint"] = fingerprint
        if fingerprint != expected_packet_fingerprint:
            raise RuntimeError("The fixed evidence snapshot changed after warm-up.")
        result["failure_stage"] = "synthesis"
        study = main.study_service.generate(
            film,
            prepared["reading"].get("passages", []),
            spec["question"],
            prepared["claims"],
            evidence_packet=packet,
            trace=trace,
        )
        result.update(
            status="passed",
            failure_stage=None,
            quality=safe_study_score(study, identity_ok=True),
            packet_quality=study.get("packet_quality", assess_evidence_packet(packet)),
            study_observability=study.get("observability", {}),
        )
    except Exception as exc:
        trace.finish("failed")
        result["failure_type"] = type(exc).__name__
        result.setdefault("quality", {"score": 0.0})
    finally:
        elapsed = round(time.perf_counter() - started_at, 3)
        result["latency_seconds"] = {"study": elapsed, "end_to_end": elapsed}
        result["model_calls"] = safe_model_calls(recorder, call_start)
    return result


def run_agent_case(
    spec: dict[str, Any],
    recorder: SafeRecordingTransport,
    expected_packet_fingerprint: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    started_at = time.perf_counter()
    call_start = len(recorder.calls)
    run_id = str(uuid4())
    result: dict[str, Any] = {
        "case_id": spec["id"],
        "status": "failed",
        "failure_stage": "graph",
        "identity_match": False,
    }
    private_packet: dict[str, Any] | None = None
    adapter: LocalResearchGraphServices | None = None
    try:
        adapter = main.build_local_agent_services()
        graph = build_research_graph()
        state = initial_research_state(
            run_id=run_id,
            user_id="local-paired-evaluation",
            question=spec["question"],
            film_query=spec["query"],
            film_id=spec["film_id"],
        )
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
                        max_calls_per_external_tool=1,
                    ),
                ),
                config={"recursion_limit": 64},
            ),
        )
        metrics = adapter.safe_metrics(run_id)
        if metrics["initial_packet_fingerprint"] != expected_packet_fingerprint:
            raise RuntimeError("The Agent evidence snapshot differs from the paired control.")
        packet = adapter.private_packet(run_id)
        identity_ok = identity_matches(packet.film_record, spec["expected"])
        result["identity_match"] = identity_ok
        study = final.get("draft") if isinstance(final.get("draft"), dict) else {}
        terminal = final["status"]
        completed = terminal is TerminalStatus.COMPLETE and identity_ok
        result.update(
            status="passed" if completed else "failed",
            failure_stage=None if completed else "graph",
            terminal_status=terminal.value,
            quality=safe_study_score(study, identity_ok=identity_ok),
            packet_quality=metrics["packet_quality"],
            initial_packet_quality=metrics["initial_packet_quality"],
            initial_packet_fingerprint=metrics["initial_packet_fingerprint"],
            packet_fingerprint=metrics["packet_fingerprint"],
            study_observability=metrics["study_observability"],
            planner_calls=metrics["planner_calls"],
            planner_latency_seconds=metrics["planner_latency_seconds"],
            planner_prompt_tokens=metrics["planner_prompt_tokens"],
            planner_completion_tokens=metrics["planner_completion_tokens"],
            planner_total_tokens=metrics["planner_total_tokens"],
            tool_attempts=metrics["tool_attempts"],
            acquired_reviews=metrics["acquired_reviews"],
            acquired_videos=metrics["acquired_videos"],
            graph_counts={
                "steps": final["step_count"],
                "planning_calls": final["planning_calls"],
                "external_tool_calls": final["external_tool_calls"],
                "synthesis_calls": final["synthesis_calls"],
                "repair_calls": final["repair_calls"],
            },
            attempted_tools=[tool.value for tool in final["attempted_tools"]],
            tool_failure_count=len(final["tool_failures"]),
            event_kinds=[item.kind for item in final["events"]],
        )
        private_packet = packet.model_dump()
    except Exception as exc:
        result["failure_type"] = type(exc).__name__
        result.setdefault("quality", {"score": 0.0})
        if adapter is not None:
            try:
                metrics = adapter.safe_metrics(run_id)
                result["initial_packet_quality"] = metrics["initial_packet_quality"]
                result["packet_quality"] = metrics["packet_quality"]
                result["tool_attempts"] = metrics["tool_attempts"]
            except (KeyError, RuntimeError):
                pass
    finally:
        elapsed = round(time.perf_counter() - started_at, 3)
        result["latency_seconds"] = {"study": elapsed, "end_to_end": elapsed}
        result["model_calls"] = safe_model_calls(recorder, call_start)
    return result, private_packet


def ratio(numerator: Any, denominator: Any) -> float | None:
    if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)):
        return None
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def target_result(
    target_id: str,
    observed: Any,
    target: dict[str, Any],
    *,
    status: str | None = None,
) -> dict[str, Any]:
    comparison = target["comparison"]
    threshold = target["threshold"]
    if status is None:
        if observed is None:
            status = "failed"
        elif comparison == "eq":
            status = "passed" if observed == threshold else "failed"
        elif comparison == "gte":
            status = "passed" if observed >= threshold else "failed"
        elif comparison == "lte":
            status = "passed" if observed <= threshold else "failed"
        else:
            raise ValueError(f"Unknown comparison {comparison} for {target_id}.")
    return {
        "target_id": target_id,
        "status": status,
        "observed": observed,
        "comparison": comparison,
        "threshold": threshold,
    }


def evaluate_candidate_targets(
    decision: dict[str, Any],
    fixed_summary: dict[str, Any],
    agent_summary: dict[str, Any],
    agent_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    targets = decision["candidate_targets"]
    completed = [item for item in agent_cases if item["status"] == "passed"]
    valid_citations = (
        sum(bool(item.get("quality", {}).get("valid_citations")) for item in completed)
        / len(completed)
        if completed
        else 0.0
    )
    identity_ratio = (
        sum(bool(item.get("identity_match")) for item in agent_cases) / len(agent_cases)
        if agent_cases
        else 0.0
    )
    containment_ratio = (
        sum(
            bool(item.get("packet_quality", {}).get("instruction_safety", {}).get(
                "containment_boundary"
            ))
            for item in agent_cases
        )
        / len(agent_cases)
        if agent_cases
        else 0.0
    )
    observed = {
        "fixed_suite_completion_ratio": (
            len(completed) / len(agent_cases) if agent_cases else 0.0
        ),
        "mean_automated_quality": agent_summary.get("mean_quality_score"),
        "quality_gate_pass_ratio": agent_summary.get("quality_gate_pass_rate"),
        "valid_citation_ratio": round(valid_citations, 4),
        "identity_match_ratio": round(identity_ratio, 4),
        "instruction_containment_ratio": round(containment_ratio, 4),
        "paired_end_to_end_p50_ratio": ratio(
            agent_summary.get("latency_seconds", {}).get("p50_end_to_end"),
            fixed_summary.get("latency_seconds", {}).get("p50_end_to_end"),
        ),
        "paired_end_to_end_p95_ratio": ratio(
            agent_summary.get("latency_seconds", {}).get("p95_end_to_end"),
            fixed_summary.get("latency_seconds", {}).get("p95_end_to_end"),
        ),
        "paired_total_token_ratio": ratio(
            agent_summary.get("total_tokens"), fixed_summary.get("total_tokens")
        ),
    }
    results = []
    for target_id, target in targets.items():
        if target_id in HUMAN_TARGETS:
            results.append(
                target_result(target_id, None, target, status="pending_human_review")
            )
        elif target_id in DEFERRED_CUTOVER_TARGETS:
            results.append(
                target_result(target_id, None, target, status="deferred_no_product_route")
            )
        else:
            results.append(target_result(target_id, observed.get(target_id), target))
    return results


def policy_checks(agent_cases: list[dict[str, Any]], decision: dict[str, Any]) -> list[dict[str, Any]]:
    limits = decision["candidate_limits"]
    sufficient_external_calls = sum(
        int(item.get("graph_counts", {}).get("external_tool_calls", 0))
        for item in agent_cases
        if item.get("initial_packet_quality", {}).get("status") == "passed"
    )
    sufficient_packet_mutations = sum(
        item.get("packet_fingerprint") != item.get("initial_packet_fingerprint")
        for item in agent_cases
        if item.get("initial_packet_quality", {}).get("status") == "passed"
    )
    maximum_planner_calls = max(
        (int(item.get("graph_counts", {}).get("planning_calls", 0)) for item in agent_cases),
        default=0,
    )
    maximum_external_calls = max(
        (int(item.get("graph_counts", {}).get("external_tool_calls", 0)) for item in agent_cases),
        default=0,
    )
    repeated_tools = sum(
        len(item.get("attempted_tools", [])) != len(set(item.get("attempted_tools", [])))
        for item in agent_cases
    )
    return [
        {
            "check_id": "sufficient_packet_external_calls",
            "status": "passed" if sufficient_external_calls == 0 else "failed",
            "observed": sufficient_external_calls,
            "threshold": limits["external_calls_for_sufficient_packet"],
        },
        {
            "check_id": "sufficient_packet_mutations",
            "status": "passed" if sufficient_packet_mutations == 0 else "failed",
            "observed": sufficient_packet_mutations,
            "threshold": 0,
        },
        {
            "check_id": "maximum_planner_calls",
            "status": (
                "passed"
                if maximum_planner_calls <= limits["maximum_planner_calls_for_insufficient_packet"]
                else "failed"
            ),
            "observed": maximum_planner_calls,
            "threshold": limits["maximum_planner_calls_for_insufficient_packet"],
        },
        {
            "check_id": "maximum_external_calls",
            "status": (
                "passed"
                if maximum_external_calls <= limits["maximum_external_calls_for_insufficient_packet"]
                else "failed"
            ),
            "observed": maximum_external_calls,
            "threshold": limits["maximum_external_calls_for_insufficient_packet"],
        },
        {
            "check_id": "repeated_provider_tools",
            "status": "passed" if repeated_tools == 0 else "failed",
            "observed": repeated_tools,
            "threshold": 0,
        },
    ]


def fixed_control_checks(summary: dict[str, Any]) -> list[dict[str, Any]]:
    case_count = int(summary.get("case_count") or 0)
    completed = int(summary.get("successful_cases") or 0)
    ratio_value = completed / case_count if case_count else 0.0
    return [
        {
            "check_id": "fixed_control_completion_ratio",
            "status": "passed" if ratio_value == 1.0 else "failed",
            "observed": round(ratio_value, 4),
            "threshold": 1.0,
        }
    ]


def assert_safe_report(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_REPORT_KEYS:
                raise ValueError(f"Unsafe report key at {path}.{key}.")
            assert_safe_report(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_safe_report(item, f"{path}[{index}]")


def write_private_packets(path: Path, payload: dict[str, Any]) -> None:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Private packet output must stay under .firstroll.") from exc
    if not relative.parts or relative.parts[0] != ".firstroll":
        raise ValueError("Private packet output must stay under .firstroll.")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the default-off local fixed/Agent paired evaluation."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--private-packets", type=Path, default=DEFAULT_PRIVATE_PACKETS)
    parser.add_argument("--case", action="append", dest="case_ids")
    return parser.parse_args()


def main_cli() -> int:
    args = parse_args()
    if not main.local_agent_enabled():
        raise SystemExit(
            "Set FIRSTROLL_LOCAL_AGENT_ENABLED=1 explicitly for the approved local comparison."
        )
    decision = load_json(args.decision)
    if not comparison_authorised(decision):
        raise SystemExit(
            "The machine-readable decision does not authorise another local comparison run."
        )
    suite_id, specs = case_specs(args.cases, args.reference)
    if args.case_ids:
        requested = set(args.case_ids)
        specs = [item for item in specs if item["id"] in requested]
        missing = requested - {item["id"] for item in specs}
        if missing:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing))}")
    if not specs:
        raise SystemExit("The paired evaluation contains no cases.")

    expected_fingerprints = warm_evidence(specs)
    configuration = configuration_fingerprint()
    recorder = SafeRecordingTransport()
    main.study_service._transport = recorder
    fixed_results: list[dict[str, Any]] = []
    agent_results: list[dict[str, Any]] = []
    private_cases: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        print(f"[{index}/{len(specs)}] {spec['id']} · fixed", flush=True)
        fixed = run_fixed_case(spec, recorder, expected_fingerprints[spec["id"]])
        fixed_results.append(fixed)
        print(
            f"  {fixed['status']} · quality {fixed.get('quality', {}).get('score', 0):.1f} "
            f"· {fixed['latency_seconds']['end_to_end']:.2f}s",
            flush=True,
        )
        print(f"[{index}/{len(specs)}] {spec['id']} · agent", flush=True)
        agent, private_packet = run_agent_case(
            spec, recorder, expected_fingerprints[spec["id"]]
        )
        agent_results.append(agent)
        if private_packet is not None:
            private_cases.append({"case_id": spec["id"], "packet": private_packet})
        print(
            f"  {agent['status']} · quality {agent.get('quality', {}).get('score', 0):.1f} "
            f"· {agent['latency_seconds']['end_to_end']:.2f}s",
            flush=True,
        )

    suite_fingerprint = json_fingerprint(args.cases)
    full_suite = full_suite_selected(
        suite_id=suite_id,
        suite_fingerprint=suite_fingerprint,
        case_count=len(specs),
        subset_requested=bool(args.case_ids),
        expected_case_count=int(decision["fixed_control"]["completed_cases"]),
    )
    fixed_summary = aggregate(fixed_results)
    agent_summary = aggregate(agent_results)
    target_results = evaluate_candidate_targets(
        decision, fixed_summary, agent_summary, agent_results
    )
    checks = [
        *fixed_control_checks(fixed_summary),
        *policy_checks(agent_results, decision),
    ]
    local_machine_results = [
        item
        for item in target_results
        if item["target_id"] not in HUMAN_TARGETS | DEFERRED_CUTOVER_TARGETS
    ]
    local_machine_passed = (
        full_suite
        and bool(local_machine_results)
        and all(item["status"] == "passed" for item in local_machine_results)
        and all(item["status"] == "passed" for item in checks)
    )
    report = {
        "schema_version": 1,
        "suite_id": suite_id,
        "system": "default_off_local_agent_paired_evaluation",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": source_revision(),
        "decision_id": decision["decision_id"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "configuration": configuration,
            "suite_fingerprint": suite_fingerprint,
            "initial_packet_fingerprints": expected_fingerprints,
            "decision_sha256": hashlib.sha256(
                args.decision.read_bytes()
            ).hexdigest()[:16],
        },
        "controls": decision["paired_controls"],
        "summary": {
            "full_frozen_suite": full_suite,
            "fixed": fixed_summary,
            "agent": agent_summary,
            "paired": {
                "p50_end_to_end_ratio": ratio(
                    agent_summary.get("latency_seconds", {}).get("p50_end_to_end"),
                    fixed_summary.get("latency_seconds", {}).get("p50_end_to_end"),
                ),
                "p95_end_to_end_ratio": ratio(
                    agent_summary.get("latency_seconds", {}).get("p95_end_to_end"),
                    fixed_summary.get("latency_seconds", {}).get("p95_end_to_end"),
                ),
                "total_token_ratio": ratio(
                    agent_summary.get("total_tokens"), fixed_summary.get("total_tokens")
                ),
            },
            "local_machine_targets_passed": local_machine_passed,
            "human_review_ready": local_machine_passed and len(private_cases) == len(specs),
            "production_cutover_ready": False,
        },
        "candidate_targets": target_results,
        "policy_checks": checks,
        "cases": [
            {"case_id": spec["id"], "fixed": fixed, "agent": agent}
            for spec, fixed, agent in zip(specs, fixed_results, agent_results, strict=True)
        ],
        "redaction": {
            "generated_section_lens_removed": True,
            "failed_exception_details_removed": True,
            "source_and_prompt_fields_rejected": True,
        },
        "privacy_scope": (
            "Versioned output contains aggregate identity, quality, timing, token, tool and packet "
            "diagnostics only. Full candidate packets are written separately under ignored "
            ".firstroll only when local machine targets pass."
        ),
    }
    assert_safe_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["summary"]["human_review_ready"]:
        write_private_packets(
            args.private_packets,
            {
                "schema_version": 1,
                "suite_id": suite_id,
                "source_revision": report["source_revision"],
                "configuration_fingerprint": configuration["sha256"],
                "cases": private_cases,
            },
        )
        print(f"Private packet snapshot: {args.private_packets.relative_to(ROOT)}", flush=True)
    print(json.dumps(report["summary"], indent=2), flush=True)
    print(f"Report: {args.output}", flush=True)
    return 0 if local_machine_passed else 1


if __name__ == "__main__":
    sys.exit(main_cli())
