from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import stat
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend import main
from app.backend.evidence import EvidencePacket
from app.backend.study_service import GroundedStudy
from tools.evaluate_agent_acquisition import load_case
from tools.evaluate_local_agent import (
    SafeRecordingTransport,
    assert_safe_report,
    packet_fingerprint,
    source_revision,
    validate_private_packet_output_path,
    write_private_packets,
)
from tools.evaluate_text_agent import (
    compare_lanes,
    ratio,
    repetition_lane_order,
    require_committed_source,
    run_synthesis_sample,
    summarise_lane,
)
from tools.review_agent_acquisition_packets import load_private_packets


DEFAULT_CASES = ROOT / "evals" / "agent_cases.json"
DEFAULT_PROGRAMME = ROOT / "evals" / "autonomous_agent_programme.json"
DEFAULT_ACQUISITION_REPORT = (
    ROOT / "evals" / "results" / "autonomous-agent-acquisition-current.json"
)
DEFAULT_ACQUISITION_PACKETS = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-acquisition-packets.json"
)
DEFAULT_ACQUISITION_REVIEW = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-acquisition-review-redacted.json"
)
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "autonomous-agent-changed-packet-current.json"
DEFAULT_PRIVATE_STUDIES = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-changed-packet-studies.json"
)
DEFAULT_RUN_LOCK = ROOT / ".firstroll" / "evaluations" / "autonomous-agent-changed-packet.lock"


def changed_packet_experiment(programme: dict[str, Any]) -> dict[str, Any]:
    return next(item for item in programme["experiments"] if item["id"] == "A03")


def comparison_authorised(programme: dict[str, Any]) -> bool:
    experiment = changed_packet_experiment(programme)
    proposed = experiment.get("proposed_budget", {})
    confirmation = experiment.get("paid_budget_confirmation")
    acquisition_result = programme.get("a01_result")
    return bool(
        programme.get("status") == "a03_changed_packet_synthesis_approved"
        and programme.get("owner_mandate", {}).get("paid_model_or_provider_calls_authorised")
        is True
        and experiment.get("status") == "approved_one_run"
        and isinstance(acquisition_result, dict)
        and acquisition_result.get("machine_targets_passed") is True
        and acquisition_result.get("owner_review_attested") is True
        and acquisition_result.get("selected_lane")
        in {"deterministic_gap_router", "model_gap_planner"}
        and isinstance(confirmation, dict)
        and confirmation.get("confirmed") is True
        and confirmation.get("authorisation_consumed") is False
        and confirmation.get("approved_generation_repetitions_per_lane")
        == proposed.get("generation_repetitions_per_lane")
        and confirmation.get("approved_minimum_synthesis_calls")
        == proposed.get("expected_minimum_synthesis_calls")
        and confirmation.get("approved_maximum_synthesis_calls")
        == proposed.get("maximum_synthesis_calls")
        and confirmation.get("approved_planner_calls") == 0
        and confirmation.get("approved_provider_calls") == 0
    )


def load_private_json(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("The private A01 review must stay under .firstroll.") from exc
    if not relative.parts or relative.parts[0] != ".firstroll":
        raise ValueError("The private A01 review must stay under .firstroll.")
    if not resolved.is_file():
        raise FileNotFoundError("The required private human-review aggregate does not exist.")
    if stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise PermissionError("The private human-review aggregate must use mode 0600.")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("The private human-review aggregate is invalid.")
    return value


def select_a01_packets(
    programme: dict[str, Any],
    machine_report: dict[str, Any],
    private_packets: dict[str, Any],
    human_review: dict[str, Any],
) -> tuple[str, EvidencePacket, EvidencePacket, dict[str, Any]]:
    result = programme.get("a01_result")
    if not isinstance(result, dict):
        raise ValueError("The programme has no accepted A01 result.")
    selected_lane = str(result.get("selected_lane") or "")
    if selected_lane not in {"deterministic_gap_router", "model_gap_planner"}:
        raise ValueError("The accepted acquisition policy lane is invalid.")
    experiment_id = str(result.get("experiment_id") or "A01")
    if experiment_id not in {"A01", "A01R"}:
        raise ValueError("The accepted acquisition experiment is invalid.")
    shared = {
        "programme_id": programme["programme_id"],
        "experiment_id": experiment_id,
        "source_revision": result.get("source_revision"),
        "suite_fingerprint": result.get("suite_fingerprint"),
    }
    for value in (machine_report, private_packets, human_review):
        for key, expected in shared.items():
            if value.get(key) != expected:
                raise ValueError("The A01 machine, packet and human artifacts do not match.")
    if machine_report.get("summary", {}).get("machine_targets_passed") is not True:
        raise ValueError("The A01 machine targets did not pass.")
    if human_review.get("reviewer_attested") is not True:
        raise ValueError("The A01 owner review is not attested.")
    expected_advancement = (
        "advance_A02" if selected_lane == "model_gap_planner" else "prefer_deterministic"
    )
    if human_review.get("summary", {}).get("advancement") != expected_advancement:
        raise ValueError("The selected A01 lane contradicts the blinded human decision.")
    selected_human = human_review.get("lanes", {}).get(selected_lane, {})
    if selected_human.get("passed_packet_rubric") is not True:
        raise ValueError("The selected A01 packet did not pass the human packet rubric.")

    packet_by_lane = {
        lane: EvidencePacket.model_validate(
            next(
                item["packet"]
                for item in private_packets["packets"]
                if item["blind_id"] == blind_id
            )
        )
        for blind_id, lane in private_packets["blind_mapping"].items()
    }
    fixed = packet_by_lane["fixed_no_acquisition"]
    candidate = packet_by_lane[selected_lane]
    machine_lanes = {item["lane"]: item for item in machine_report.get("lanes", [])}
    if packet_fingerprint(fixed) != machine_lanes["fixed_no_acquisition"].get(
        "final_packet_fingerprint"
    ) or packet_fingerprint(candidate) != machine_lanes[selected_lane].get(
        "final_packet_fingerprint"
    ):
        raise ValueError("The private A01 packets do not match their machine fingerprints.")
    acquisition_latency = machine_lanes[selected_lane].get("acquisition_latency_seconds")
    if (
        not isinstance(acquisition_latency, (int, float))
        or isinstance(acquisition_latency, bool)
        or acquisition_latency <= 0
    ):
        raise ValueError("The selected A01 lane lacks complete acquisition latency.")
    return selected_lane, fixed, candidate, machine_lanes[selected_lane]


def evidence_signature(item: Any) -> str:
    if hasattr(item, "model_dump"):
        payload = json.dumps(
            item.model_dump(exclude={"evidence_id"}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        payload = str(item)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def candidate_only_source_ids(
    fixed: EvidencePacket,
    candidate: EvidencePacket,
) -> set[str]:
    fixed_signatures = {evidence_signature(item) for item in fixed.attributed_sources}
    return {
        item.evidence_id
        for item in candidate.attributed_sources
        if evidence_signature(item) not in fixed_signatures
    }


def cited_candidate_only_sources(study: dict[str, Any], candidate_ids: set[str]) -> set[str]:
    return {
        str(source_id)
        for section in study.get("sections", [])
        if isinstance(section, dict)
        for source_id in section.get("attributed_source_ids", [])
        if str(source_id) in candidate_ids
    }


def blind_private_pairs(
    studies: dict[tuple[str, int], dict[str, Any]],
    packets: dict[str, EvidencePacket],
    *,
    repetitions: tuple[int, ...],
    revision: str,
) -> list[dict[str, Any]]:
    pairs = []
    for repetition in repetitions:
        lanes = sorted(
            ("fixed", "candidate"),
            key=lambda lane: hashlib.sha256(
                f"{revision}\0{repetition}\0{lane}".encode("utf-8")
            ).hexdigest(),
        )
        mapping = {chr(ord("A") + index): lane for index, lane in enumerate(lanes)}
        pairs.append(
            {
                "repetition": repetition,
                "studies": [
                    {
                        "blind_id": blind_id,
                        "study": studies[(lane, repetition)],
                        "packet": packets[lane].model_dump(),
                    }
                    for blind_id, lane in mapping.items()
                ],
                "blind_mapping": mapping,
            }
        )
    return pairs


def evaluate_targets(
    experiment: dict[str, Any],
    fixed: dict[str, Any],
    candidate: dict[str, Any],
    comparison: dict[str, Any],
    *,
    source_usage_ratio: float,
    candidate_only_count: int,
    acquisition_latency_seconds: float,
) -> list[dict[str, Any]]:
    gate = experiment["machine_gate"]
    lifecycle_p50 = ratio(
        float(candidate.get("p50_latency_seconds") or 0.0) + acquisition_latency_seconds,
        fixed.get("p50_latency_seconds"),
    )
    lifecycle_p95 = ratio(
        float(candidate.get("p95_latency_seconds") or 0.0) + acquisition_latency_seconds,
        fixed.get("p95_latency_seconds"),
    )

    def at_most(value: Any, maximum: float) -> bool:
        return bool(
            isinstance(value, (int, float)) and not isinstance(value, bool) and value <= maximum
        )

    checks = {
        "fixed_completion_ratio": fixed["completion_ratio"] == gate["completion_ratio"],
        "candidate_completion_ratio": candidate["completion_ratio"] == gate["completion_ratio"],
        "candidate_mean_quality": (
            candidate["mean_quality_all_scheduled"] >= gate["candidate_mean_quality_minimum"]
        ),
        "candidate_quality_improvement": (
            comparison["agent_minus_fixed_mean_quality"]
            >= gate["candidate_minus_fixed_mean_quality_minimum"]
        ),
        "candidate_only_sources_exist": candidate_only_count > 0,
        "candidate_only_source_usage": (
            source_usage_ratio >= gate["candidate_only_source_usage_ratio_minimum"]
        ),
        "synthesis_p50_latency_ratio": at_most(
            comparison["p50_latency_ratio"],
            gate["synthesis_p50_latency_ratio_maximum"],
        ),
        "synthesis_p95_latency_ratio": at_most(
            comparison["p95_latency_ratio"],
            gate["synthesis_p95_latency_ratio_maximum"],
        ),
        "lifecycle_p50_latency_ratio": (
            lifecycle_p50 is not None
            and lifecycle_p50 <= gate["lifecycle_p50_latency_ratio_maximum"]
        ),
        "lifecycle_p95_latency_ratio": (
            lifecycle_p95 is not None
            and lifecycle_p95 <= gate["lifecycle_p95_latency_ratio_maximum"]
        ),
        "total_token_ratio": at_most(
            comparison["total_token_ratio"],
            gate["total_token_ratio_maximum"],
        ),
        "model_call_budget": (
            fixed["model_calls"] + candidate["model_calls"]
            <= experiment["proposed_budget"]["maximum_synthesis_calls"]
        ),
        "fixed_quality_gate_validity": (
            fixed["quality_gate_pass_ratio"] == gate["quality_gate_validity_ratio"]
        ),
        "candidate_quality_gate_validity": (
            candidate["quality_gate_pass_ratio"] == gate["quality_gate_validity_ratio"]
        ),
        "fixed_token_telemetry": (
            fixed["token_usage_complete_ratio"] == gate["token_usage_complete_ratio"]
        ),
        "candidate_token_telemetry": (
            candidate["token_usage_complete_ratio"] == gate["token_usage_complete_ratio"]
        ),
        "fixed_citation_validity": (
            fixed["valid_citation_ratio"] == gate["citation_validity_ratio"]
        ),
        "candidate_citation_validity": (
            candidate["valid_citation_ratio"] == gate["citation_validity_ratio"]
        ),
    }
    observed = {
        "candidate_only_source_usage": source_usage_ratio,
        "lifecycle_p50_latency_ratio": lifecycle_p50,
        "lifecycle_p95_latency_ratio": lifecycle_p95,
    }
    return [
        {
            "target_id": target_id,
            "status": "passed" if passed else "failed",
            **({"observed": observed[target_id]} if target_id in observed else {}),
        }
        for target_id, passed in checks.items()
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare one accepted A01 packet with its exact fixed origin without reacquisition."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--programme", type=Path, default=DEFAULT_PROGRAMME)
    parser.add_argument("--acquisition-report", type=Path, default=DEFAULT_ACQUISITION_REPORT)
    parser.add_argument("--acquisition-packets", type=Path, default=DEFAULT_ACQUISITION_PACKETS)
    parser.add_argument("--acquisition-review", type=Path, default=DEFAULT_ACQUISITION_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--private-studies", type=Path, default=DEFAULT_PRIVATE_STUDIES)
    parser.add_argument("--run-lock", type=Path, default=DEFAULT_RUN_LOCK)
    return parser.parse_args()


def main_cli() -> int:
    args = parse_args()
    programme = json.loads(args.programme.read_text(encoding="utf-8"))
    if not comparison_authorised(programme):
        raise SystemExit("The autonomous programme does not authorise changed-packet synthesis.")
    if not main.local_agent_enabled():
        raise SystemExit("Set FIRSTROLL_LOCAL_AGENT_ENABLED=1 for the local ablation.")
    require_committed_source()
    for path in (args.output, args.private_studies, args.run_lock):
        if path.exists():
            raise SystemExit(f"The required fresh output path already exists: {path.name}")
    validate_private_packet_output_path(args.private_studies)
    validate_private_packet_output_path(args.run_lock)

    experiment = changed_packet_experiment(programme)
    repetitions = int(experiment["proposed_budget"]["generation_repetitions_per_lane"])
    if repetitions != 10:
        raise SystemExit("The frozen changed-packet protocol requires ten repetitions per lane.")
    machine_report = json.loads(args.acquisition_report.read_text(encoding="utf-8"))
    private_packets = load_private_packets(args.acquisition_packets)
    human_review = load_private_json(args.acquisition_review)
    assert_safe_report(machine_report)
    assert_safe_report(human_review)
    selected_lane, fixed_packet, candidate_packet, acquisition_lane = select_a01_packets(
        programme,
        machine_report,
        private_packets,
        human_review,
    )
    spec = load_case(args.cases, str(machine_report["case_id"]))
    revision = source_revision()
    write_private_packets(
        args.run_lock,
        {
            "schema_version": 1,
            "programme_id": programme["programme_id"],
            "experiment_id": "A03",
            "source_revision": revision,
            "status": "consumed_on_start",
        },
    )

    recorder = SafeRecordingTransport()
    original_transport = main.study_service._transport
    main.study_service._transport = recorder
    samples: list[dict[str, Any]] = []
    private_studies: dict[tuple[str, int], dict[str, Any]] = {}
    candidate_ids = candidate_only_source_ids(fixed_packet, candidate_packet)
    packets = {"fixed": fixed_packet, "candidate": candidate_packet}
    try:
        for repetition in range(1, repetitions + 1):
            for protocol_lane in repetition_lane_order(repetition):
                lane = "fixed" if protocol_lane == "fixed" else "candidate"
                captured: list[dict[str, Any]] = []
                sample = run_synthesis_sample(
                    spec,
                    packets[lane],
                    lane=lane,
                    repetition=repetition,
                    recorder=recorder,
                    private_capture=captured.append,
                )
                used = (
                    cited_candidate_only_sources(captured[0], candidate_ids)
                    if lane == "candidate" and captured
                    else set()
                )
                sample["candidate_only_source_used"] = bool(used) if lane == "candidate" else None
                sample["candidate_only_source_count_used"] = len(used)
                samples.append(sample)
                if captured and repetition in experiment["private_human_review_repetitions"]:
                    private_studies[(lane, repetition)] = GroundedStudy.model_validate(
                        {
                            key: captured[0][key]
                            for key in GroundedStudy.model_fields
                            if key in captured[0]
                        }
                    ).model_dump()
    finally:
        main.study_service._transport = original_transport

    fixed_samples = [item for item in samples if item["lane"] == "fixed"]
    candidate_samples = [item for item in samples if item["lane"] == "candidate"]
    fixed_summary = summarise_lane(fixed_samples, scheduled=repetitions)
    candidate_summary = summarise_lane(candidate_samples, scheduled=repetitions)
    planner_tokens = int(acquisition_lane.get("planner_total_tokens", 0) or 0)
    planner_calls = int(acquisition_lane.get("model_planner_calls", 0) or 0)
    comparison = compare_lanes(
        fixed_summary,
        candidate_summary,
        acquisition_planner_tokens=planner_tokens,
        acquisition_planner_calls=planner_calls,
    )
    used_samples = sum(item["candidate_only_source_used"] is True for item in candidate_samples)
    usage_ratio = round(used_samples / repetitions, 6)
    acquisition_latency = float(acquisition_lane.get("acquisition_latency_seconds", 0.0) or 0.0)
    targets = evaluate_targets(
        experiment,
        fixed_summary,
        candidate_summary,
        comparison,
        source_usage_ratio=usage_ratio,
        candidate_only_count=len(candidate_ids),
        acquisition_latency_seconds=acquisition_latency,
    )
    fixed_identity_ratio = round(
        sum(item.get("identity_match") is True for item in fixed_samples) / repetitions,
        6,
    )
    candidate_identity_ratio = round(
        sum(item.get("identity_match") is True for item in candidate_samples) / repetitions,
        6,
    )
    targets.append(
        {
            "target_id": "no_reacquisition_or_planning",
            "status": (
                "passed"
                if all(
                    item.get("graph_counts", {}).get("planning_calls") == 0
                    and item.get("graph_counts", {}).get("external_tool_calls") == 0
                    for item in samples
                )
                else "failed"
            ),
        }
    )
    for target_id, observed in (
        ("fixed_identity_match", fixed_identity_ratio),
        ("candidate_identity_match", candidate_identity_ratio),
    ):
        targets.append(
            {
                "target_id": target_id,
                "status": (
                    "passed"
                    if observed == experiment["machine_gate"]["identity_match_ratio"]
                    else "failed"
                ),
                "observed": observed,
            }
        )
    machine_passed = all(item["status"] == "passed" for item in targets)
    report: dict[str, Any] = {
        "schema_version": 1,
        "programme_id": programme["programme_id"],
        "experiment_id": "A03",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": revision,
        "a01_source_revision": machine_report["source_revision"],
        "suite_fingerprint": machine_report["suite_fingerprint"],
        "case_id": machine_report["case_id"],
        "selected_acquisition_lane": selected_lane,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "model": main.study_service.model,
            "local_agent_enabled": main.local_agent_enabled(),
        },
        "protocol": {
            "generation_repetitions_per_lane": repetitions,
            "alternating_lane_order": True,
            "packet_reacquired": False,
            "failures_scored_zero": True,
            "private_human_review_repetitions": experiment["private_human_review_repetitions"],
        },
        "samples": samples,
        "summary": {
            "fixed": fixed_summary,
            "candidate": candidate_summary,
            "comparison": comparison,
            "candidate_only_source_count": len(candidate_ids),
            "candidate_only_source_usage_ratio": usage_ratio,
            "fixed_identity_match_ratio": fixed_identity_ratio,
            "candidate_identity_match_ratio": candidate_identity_ratio,
            "acquisition_latency_seconds": acquisition_latency,
            "machine_targets_passed": machine_passed,
            "private_study_snapshot_written": False,
            "human_review_ready": False,
        },
        "targets": targets,
    }

    exit_code = 0 if machine_passed else 2
    required_private = {
        (lane, repetition)
        for lane in ("fixed", "candidate")
        for repetition in experiment["private_human_review_repetitions"]
    }
    if machine_passed and set(private_studies) == required_private:
        try:
            write_private_packets(
                args.private_studies,
                {
                    "schema_version": 1,
                    "programme_id": programme["programme_id"],
                    "experiment_id": "A03",
                    "source_revision": revision,
                    "a01_source_revision": machine_report["source_revision"],
                    "suite_fingerprint": machine_report["suite_fingerprint"],
                    "case_id": machine_report["case_id"],
                    "selected_acquisition_lane": selected_lane,
                    "pairs": blind_private_pairs(
                        private_studies,
                        packets,
                        repetitions=tuple(experiment["private_human_review_repetitions"]),
                        revision=revision,
                    ),
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
            report["summary"]["private_study_snapshot_written"] = True
            report["summary"]["human_review_ready"] = True
    elif machine_passed:
        report["post_run_artifact"] = {
            "status": "failed_safe",
            "failure_category": "private_study_capture_incomplete",
            "paid_calls_completed": True,
        }
        exit_code = 3

    assert_safe_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main_cli())
