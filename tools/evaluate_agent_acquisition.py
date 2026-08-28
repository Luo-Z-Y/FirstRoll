from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import sys
from time import monotonic
from typing import Any, cast


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend import main
from app.backend.agent_evidence import assess_agent_evidence
from app.backend.evidence import EvidencePacket
from app.backend.local_research_agent import AcquiredSources, LocalResearchGraphServices
from app.backend.packet_quality import assess_evidence_packet
from app.backend.research_agent_contract import ResearchBudgets, TerminalStatus, ToolName
from app.backend.research_graph import (
    ResearchGraphContext,
    ResearchGraphState,
    build_research_graph,
    initial_research_state,
)
from app.backend.study_observability import StudyTrace
from tools.evaluate_local_agent import (
    assert_safe_report,
    packet_fingerprint,
    source_revision,
    validate_private_packet_output_path,
    write_private_packets,
)
from tools.evaluate_text_agent import require_committed_source, require_fresh_output_paths


DEFAULT_CASES = ROOT / "evals" / "agent_cases.json"
DEFAULT_PROGRAMME = ROOT / "evals" / "autonomous_agent_programme.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "autonomous-agent-acquisition-current.json"
DEFAULT_PRIVATE_PACKETS = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-acquisition-packets.json"
)
DEFAULT_RUN_LOCK = ROOT / ".firstroll" / "evaluations" / "autonomous-agent-acquisition.lock"


@dataclass(frozen=True)
class _UnavailableObservation:
    pass


@dataclass(frozen=True)
class FrozenLaneSourcePool:
    pool: FrozenSourcePool
    lane: str

    def status(self) -> dict[str, dict[str, Any]]:
        return cast(dict[str, dict[str, Any]], self.pool.status())

    def acquire(self, tool: ToolName, film: dict[str, Any]) -> AcquiredSources:
        return self.pool.acquire(tool, film, lane=self.lane)


@dataclass
class FrozenSourcePool:
    """Acquire each provider observation once and replay it across ablation lanes."""

    acquirer: Any
    observations: dict[ToolName, AcquiredSources | _UnavailableObservation] = field(
        default_factory=dict
    )
    physical_attempts: list[dict[str, Any]] = field(default_factory=list)
    logical_calls: list[dict[str, Any]] = field(default_factory=list)

    def status(self) -> dict[str, dict[str, Any]]:
        return cast(dict[str, dict[str, Any]], self.acquirer.status())

    def for_lane(self, lane: str) -> FrozenLaneSourcePool:
        return FrozenLaneSourcePool(self, lane)

    def acquire(
        self,
        tool: ToolName,
        film: dict[str, Any],
        *,
        lane: str = "unspecified",
    ) -> AcquiredSources:
        cached = tool in self.observations
        self.logical_calls.append({"lane": lane, "tool": tool.value, "cache_hit": cached})
        if cached:
            observation = self.observations[tool]
            if isinstance(observation, _UnavailableObservation):
                raise RuntimeError("The frozen provider observation was unavailable.")
            return observation

        started_at = monotonic()
        try:
            observation = self.acquirer.acquire(tool, film)
        except Exception:
            self.observations[tool] = _UnavailableObservation()
            self.physical_attempts.append(
                {
                    "tool": tool.value,
                    "status": "failed",
                    "duration_seconds": round(max(0.0, monotonic() - started_at), 3),
                }
            )
            raise
        self.observations[tool] = observation
        self.physical_attempts.append(
            {
                "tool": tool.value,
                "status": "completed",
                "duration_seconds": round(max(0.0, monotonic() - started_at), 3),
                "review_count": len(observation.reviews),
                "video_count": len(observation.videos),
            }
        )
        return observation

    def counterfactual_latency_seconds(self, lane: str) -> float:
        durations = {
            item["tool"]: float(item["duration_seconds"]) for item in self.physical_attempts
        }
        return round(
            sum(
                durations.get(item["tool"], 0.0)
                for item in self.logical_calls
                if item["lane"] == lane
            ),
            3,
        )

    def safe_metrics(self) -> dict[str, Any]:
        return {
            "physical_provider_calls": len(self.physical_attempts),
            "physical_attempts": list(self.physical_attempts),
            "logical_provider_calls": len(self.logical_calls),
            "logical_calls": list(self.logical_calls),
            "cache_hits": sum(item["cache_hit"] for item in self.logical_calls),
            "lane_counterfactual_latency_seconds": {
                lane: self.counterfactual_latency_seconds(lane)
                for lane in sorted({item["lane"] for item in self.logical_calls})
            },
        }


def acquisition_experiment(programme: dict[str, Any]) -> dict[str, Any]:
    return next(item for item in programme["experiments"] if item["id"] == "A01")


def comparison_authorised(programme: dict[str, Any]) -> bool:
    experiment = acquisition_experiment(programme)
    proposed = experiment.get("proposed_budget", {})
    confirmation = experiment.get("paid_budget_confirmation")
    return bool(
        programme.get("status") == "a01_acquisition_ablation_approved"
        and programme.get("owner_mandate", {}).get("paid_model_or_provider_calls_authorised")
        is True
        and experiment.get("status") == "approved_one_run"
        and isinstance(confirmation, dict)
        and confirmation.get("confirmed") is True
        and confirmation.get("authorisation_consumed") is False
        and confirmation.get("approved_maximum_model_planner_calls")
        == proposed.get("maximum_model_planner_calls")
        and confirmation.get("approved_maximum_physical_provider_calls")
        == proposed.get("maximum_physical_provider_calls")
        and confirmation.get("approved_maximum_external_tool_turns_per_active_lane")
        == proposed.get("maximum_external_tool_turns_per_active_lane")
    )


def require_authorised_run_inputs(
    args: argparse.Namespace,
    experiment: dict[str, Any],
) -> None:
    confirmation = experiment.get("paid_budget_confirmation", {})
    if args.programme.resolve() != DEFAULT_PROGRAMME.resolve():
        raise SystemExit("The acquisition ablation requires the committed programme path.")
    expected = {
        "cases": confirmation.get("approved_case_suite_path"),
        "output": confirmation.get("approved_report_path"),
        "private_packets": confirmation.get("approved_private_packet_path"),
        "run_lock": confirmation.get("approved_run_lock_path"),
    }
    actual = {
        "cases": args.cases,
        "output": args.output,
        "private_packets": args.private_packets,
        "run_lock": args.run_lock,
    }
    for name, approved in expected.items():
        if not isinstance(approved, str) or not approved.strip():
            raise SystemExit(f"The acquisition ablation lacks an approved {name} path.")
        if actual[name].resolve() != (ROOT / approved).resolve():
            raise SystemExit(f"The acquisition ablation {name} path is not authorised.")


def load_case(path: Path, case_id: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError("The Agent case suite is invalid.")
    matches = [item for item in cases if isinstance(item, dict) and item.get("id") == case_id]
    if len(matches) != 1:
        raise ValueError("The acquisition-ablation case is missing or duplicated.")
    return matches[0]


def prepare_initial_packet(spec: dict[str, Any]) -> EvidencePacket:
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
    return cast(EvidencePacket, prepared["packet"])


def build_lane_services(
    base: LocalResearchGraphServices,
    pool: FrozenSourcePool,
    *,
    lane: str,
    planner_mode: str,
) -> LocalResearchGraphServices:
    return LocalResearchGraphServices(
        detail=base.detail,
        prepare=base.prepare,
        acquirer=cast(Any, pool.for_lane(lane)),
        study_service=base.study_service,
        planner_mode=cast(Any, planner_mode),
    )


def run_acquisition_lane(
    spec: dict[str, Any],
    services: LocalResearchGraphServices,
    *,
    lane: str,
    expected_initial_fingerprint: str,
    maximum_turns: int,
) -> tuple[dict[str, Any], EvidencePacket]:
    state = initial_research_state(
        run_id=f"autonomous-acquisition-{lane}",
        user_id="local-owner",
        question=spec["question"],
        film_query=str(spec["id"]),
        film_id=spec["film_id"],
    )
    final = cast(
        ResearchGraphState,
        build_research_graph().invoke(
            state,
            context=ResearchGraphContext(
                services=services,
                budgets=ResearchBudgets(
                    max_graph_steps=10,
                    max_planning_calls=maximum_turns,
                    max_external_tool_calls=maximum_turns,
                    max_repair_calls=0,
                    max_total_model_calls=maximum_turns,
                ),
                mode="evidence_only",
            ),
            config={"recursion_limit": 64},
        ),
    )
    metrics = services.safe_metrics(state["run_id"])
    if metrics["initial_packet_fingerprint"] != expected_initial_fingerprint:
        raise RuntimeError("An ablation lane did not start from the frozen packet fingerprint.")
    packet = services.private_packet(state["run_id"])
    agent_evidence = metrics["agent_evidence"]
    passed = bool(
        final["status"] is TerminalStatus.EVIDENCE_READY
        and agent_evidence.get("agent_status") == "sufficient"
    )
    return (
        {
            "lane": lane,
            "status": "passed" if passed else "failed",
            "terminal_status": final["status"].value,
            "initial_packet_fingerprint": metrics["initial_packet_fingerprint"],
            "final_packet_fingerprint": metrics["packet_fingerprint"],
            "packet_changed": (
                metrics["packet_fingerprint"] != metrics["initial_packet_fingerprint"]
            ),
            "base_packet_status": metrics["packet_quality"]["status"],
            "agent_status": agent_evidence.get("agent_status"),
            "remaining_gaps": list(agent_evidence.get("agent_gaps", [])),
            "independent_origins": int(
                agent_evidence.get("agent_diversity", {}).get("independent_film_origins", 0)
            ),
            "film_specific_evidence_classes": int(
                agent_evidence.get("agent_diversity", {}).get("film_specific_evidence_classes", 0)
            ),
            "planning_turns": int(metrics["planning_turns"]),
            "model_planner_calls": int(metrics["planner_calls"]),
            "planner_total_tokens": int(metrics["planner_total_tokens"]),
            "planner_latency_seconds": round(
                sum(float(value) for value in metrics["planner_latency_seconds"]), 3
            ),
            "external_tool_calls": int(final["external_tool_calls"]),
            "attempted_tools": [tool.value for tool in final["attempted_tools"]],
            "planning_decisions": list(metrics["planning_decisions"]),
            "tool_attempts": list(metrics["tool_attempts"]),
        },
        packet,
    )


def fixed_lane(packet: EvidencePacket) -> dict[str, Any]:
    fingerprint = packet_fingerprint(packet)
    initial_quality = assess_evidence_packet(packet)
    assessment = assess_agent_evidence(
        packet,
        initial_packet_status=str(initial_quality["status"]),
    )
    return {
        "lane": "fixed_no_acquisition",
        "status": "control",
        "terminal_status": "not_run",
        "initial_packet_fingerprint": fingerprint,
        "final_packet_fingerprint": fingerprint,
        "packet_changed": False,
        "base_packet_status": assessment.base_status,
        "agent_status": "control",
        "remaining_gaps": [gap.value for gap in assessment.gaps],
        "independent_origins": assessment.independent_origins,
        "film_specific_evidence_classes": assessment.film_specific_evidence_classes,
        "planning_turns": 0,
        "model_planner_calls": 0,
        "planner_total_tokens": 0,
        "planner_latency_seconds": 0.0,
        "counterfactual_provider_latency_seconds": 0.0,
        "acquisition_latency_seconds": 0.0,
        "external_tool_calls": 0,
        "attempted_tools": [],
        "planning_decisions": [],
        "tool_attempts": [],
    }


def blind_private_packets(
    packets: dict[str, EvidencePacket],
    *,
    case_id: str,
    revision: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    lanes = sorted(
        packets,
        key=lambda lane: hashlib.sha256(
            f"{revision}\0{case_id}\0{lane}".encode("utf-8")
        ).hexdigest(),
    )
    labels = [chr(ord("A") + index) for index in range(len(lanes))]
    mapping = dict(zip(labels, lanes))
    return (
        [
            {"blind_id": label, "packet": packets[lane].model_dump()}
            for label, lane in mapping.items()
        ],
        mapping,
    )


def evaluate_targets(
    lanes: list[dict[str, Any]],
    source_pool: dict[str, Any],
    experiment: dict[str, Any],
) -> list[dict[str, Any]]:
    by_lane = {item["lane"]: item for item in lanes}
    proposed = experiment["proposed_budget"]
    checks = {
        "all_lanes_share_initial_fingerprint": (
            len({item["initial_packet_fingerprint"] for item in lanes}) == 1
        ),
        "deterministic_lane_completed": (by_lane["deterministic_gap_router"]["status"] == "passed"),
        "model_lane_completed": by_lane["model_gap_planner"]["status"] == "passed",
        "deterministic_lane_independent_origins": (
            by_lane["deterministic_gap_router"]["independent_origins"] >= 2
        ),
        "model_lane_independent_origins": (
            by_lane["model_gap_planner"]["independent_origins"] >= 2
        ),
        "model_planner_call_budget": (
            by_lane["model_gap_planner"]["model_planner_calls"]
            <= proposed["maximum_model_planner_calls"]
        ),
        "shared_physical_provider_budget": (
            source_pool["physical_provider_calls"] <= proposed["maximum_physical_provider_calls"]
        ),
        "active_lane_turn_budget": all(
            by_lane[lane]["external_tool_calls"]
            <= proposed["maximum_external_tool_turns_per_active_lane"]
            for lane in ("deterministic_gap_router", "model_gap_planner")
        ),
        "physical_provider_observations_unique": (
            len({item["tool"] for item in source_pool.get("physical_attempts", [])})
            == source_pool["physical_provider_calls"]
        ),
        "fixed_lane_zero_calls": (
            by_lane["fixed_no_acquisition"]["external_tool_calls"] == 0
            and by_lane["fixed_no_acquisition"]["model_planner_calls"] == 0
        ),
    }
    return [
        {"target_id": target_id, "status": "passed" if passed else "failed"}
        for target_id, passed in checks.items()
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen autonomous Agent acquisition-planner ablation once."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--programme", type=Path, default=DEFAULT_PROGRAMME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--private-packets", type=Path, default=DEFAULT_PRIVATE_PACKETS)
    parser.add_argument("--run-lock", type=Path, default=DEFAULT_RUN_LOCK)
    return parser.parse_args()


def main_cli() -> int:
    args = parse_args()
    programme = json.loads(args.programme.read_text(encoding="utf-8"))
    if not comparison_authorised(programme):
        raise SystemExit("The autonomous programme does not authorise the acquisition ablation.")
    if not main.local_agent_enabled():
        raise SystemExit("Set FIRSTROLL_LOCAL_AGENT_ENABLED=1 for the local ablation.")
    experiment = acquisition_experiment(programme)
    require_authorised_run_inputs(args, experiment)
    require_committed_source()
    require_fresh_output_paths(args.output, args.private_packets)
    if args.run_lock.exists():
        raise SystemExit("The private one-run acquisition lock already exists.")
    validate_private_packet_output_path(args.private_packets)
    validate_private_packet_output_path(args.run_lock)

    spec = load_case(args.cases, str(experiment["case_id"]))
    revision = source_revision()
    initial_packet = prepare_initial_packet(spec)
    initial_fingerprint = packet_fingerprint(initial_packet)
    base = main.build_local_agent_services()
    pool = FrozenSourcePool(base.acquirer)
    write_private_packets(
        args.run_lock,
        {
            "schema_version": 1,
            "programme_id": programme["programme_id"],
            "experiment_id": "A01",
            "source_revision": revision,
            "status": "consumed_on_start",
        },
    )
    maximum_turns = int(
        experiment["proposed_budget"]["maximum_external_tool_turns_per_active_lane"]
    )
    deterministic, deterministic_packet = run_acquisition_lane(
        spec,
        build_lane_services(
            base,
            pool,
            lane="deterministic_gap_router",
            planner_mode="deterministic",
        ),
        lane="deterministic_gap_router",
        expected_initial_fingerprint=initial_fingerprint,
        maximum_turns=maximum_turns,
    )
    model, model_packet = run_acquisition_lane(
        spec,
        build_lane_services(
            base,
            pool,
            lane="model_gap_planner",
            planner_mode="model",
        ),
        lane="model_gap_planner",
        expected_initial_fingerprint=initial_fingerprint,
        maximum_turns=maximum_turns,
    )
    lanes = [fixed_lane(initial_packet), deterministic, model]
    source_pool = pool.safe_metrics()
    for lane in lanes:
        counterfactual = float(
            source_pool["lane_counterfactual_latency_seconds"].get(lane["lane"], 0.0)
        )
        lane["counterfactual_provider_latency_seconds"] = counterfactual
        lane["acquisition_latency_seconds"] = round(
            float(lane["planner_latency_seconds"]) + counterfactual,
            3,
        )
    targets = evaluate_targets(lanes, source_pool, experiment)
    machine_passed = all(item["status"] == "passed" for item in targets)
    suite_fingerprint = hashlib.sha256(
        f"{programme['programme_id']}\0A01\0{spec['id']}\0{initial_fingerprint}".encode("utf-8")
    ).hexdigest()[:16]
    report: dict[str, Any] = {
        "schema_version": 1,
        "programme_id": programme["programme_id"],
        "experiment_id": "A01",
        "source_revision": revision,
        "case_id": spec["id"],
        "suite_fingerprint": suite_fingerprint,
        "initial_packet_fingerprint": initial_fingerprint,
        "lanes": lanes,
        "source_pool": source_pool,
        "targets": targets,
        "summary": {
            "machine_targets_passed": machine_passed,
            "private_packet_snapshot_written": False,
            "human_review_ready": False,
            "model_value_over_deterministic": "pending_blinded_human_review",
        },
    }

    exit_code = 0 if machine_passed else 2
    if machine_passed:
        private_packets, blind_mapping = blind_private_packets(
            {
                "fixed_no_acquisition": initial_packet,
                "deterministic_gap_router": deterministic_packet,
                "model_gap_planner": model_packet,
            },
            case_id=spec["id"],
            revision=revision,
        )
        try:
            write_private_packets(
                args.private_packets,
                {
                    "schema_version": 1,
                    "programme_id": programme["programme_id"],
                    "experiment_id": "A01",
                    "source_revision": revision,
                    "suite_fingerprint": suite_fingerprint,
                    "case_id": spec["id"],
                    "packets": private_packets,
                    "blind_mapping": blind_mapping,
                    "lane_metrics": {
                        item["lane"]: {
                            "external_tool_calls": item["external_tool_calls"],
                            "model_planner_calls": item["model_planner_calls"],
                            "planner_total_tokens": item["planner_total_tokens"],
                            "acquisition_latency_seconds": item["acquisition_latency_seconds"],
                        }
                        for item in lanes
                    },
                },
            )
        except (OSError, ValueError):
            report["post_run_artifact"] = {
                "status": "failed_safe",
                "failure_category": "private_output_write_failed",
                "paid_calls_completed": True,
            }
            exit_code = 3
        else:
            report["summary"]["private_packet_snapshot_written"] = True
            report["summary"]["human_review_ready"] = True

    assert_safe_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main_cli())
