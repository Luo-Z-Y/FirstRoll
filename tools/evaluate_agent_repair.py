from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
from time import monotonic
from typing import Any, cast


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend import main
from app.backend.criticism import ReviewSource
from app.backend.evidence import EvidencePacket
from app.backend.study_observability import StudyTrace
from app.backend.study_service import (
    DeepSeekStudyService,
    GroundedStudy,
    StudyGenerationError,
)
from tools.evaluate_local_agent import (
    SafeRecordingTransport,
    assert_safe_report,
    source_revision,
    validate_private_packet_output_path,
    write_private_packets,
)
from tools.evaluate_text_agent import require_committed_source


DEFAULT_PROGRAMME = ROOT / "evals" / "autonomous_agent_programme.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "autonomous-agent-repair-current.json"
DEFAULT_RUN_LOCK = ROOT / ".firstroll" / "evaluations" / "autonomous-agent-repair.lock"
SCENARIOS = (
    "one_invalid_citation",
    "one_schema_invalid_field",
    "two_invalid_fields",
)
REPETITIONS = 3
MAX_PATCH_CALLS_PER_SAMPLE = 2


SYNTHETIC_FILM = {
    "title": "Synthetic Film",
    "original_title": "Synthetic Film",
    "year": 2024,
    "credits": {"directors": ["Example Director"]},
    "genres": ["Drama"],
    "source": "synthetic_evaluation_fixture",
}
SYNTHETIC_FOCUS = "How might framing, editing and sound organise uncertainty for close viewing?"
SYNTHETIC_RETRIEVAL = {
    "method": "synthetic_evaluation_fixture",
    "passages": [
        {
            "title": "Spatial Relations",
            "page": 1,
            "language": "en",
            "excerpt": (
                "Framing can distribute attention through repeated spatial relations. A close "
                "viewer can compare entrances, eyelines and boundaries without treating an "
                "analytical hypothesis as a directly observed fact."
            ),
        },
        {
            "title": "Rhythmic Comparison",
            "page": 2,
            "language": "en",
            "excerpt": (
                "Editing and sound can be studied as temporal patterns by logging transitions, "
                "durations and recurrences, then comparing where those patterns converge or split."
            ),
        },
    ],
}


def synthetic_packet() -> EvidencePacket:
    reviews = [
        ReviewSource(
            source_id="R1",
            provider="Guardian",
            review_id="guardian-synthetic",
            title="Synthetic attributed review",
            summary=(
                "The critic reports that spatial withholding and abrupt transitions shape the "
                "film's uncertainty, a claim that should be checked against the selected work."
            ),
            author="Example Critic",
            url="https://theguardian.com/film/synthetic-review",
            language="en",
        ),
        ReviewSource(
            source_id="R2",
            provider="Crossref scholarship",
            review_id="10.0000/synthetic",
            title="Synthetic scholarly abstract",
            summary=(
                "The abstract compares framing boundaries, rhythmic interruption and off-screen "
                "sound as analytical categories rather than verified descriptions of one scene."
            ),
            author="Example Scholar",
            url="https://doi.org/10.0000/synthetic",
            language="en",
        ),
    ]
    return EvidencePacket.from_retrieval(
        SYNTHETIC_FILM,
        SYNTHETIC_RETRIEVAL,
        SYNTHETIC_FOCUS,
        reviews=reviews,
    )


def valid_candidate() -> dict[str, Any]:
    sections = []
    subjects = (
        ("Framing boundaries", "framing and eyeline boundaries"),
        ("Editing rhythm", "cuts and transition intervals"),
        ("Sound relations", "off-screen sound and visible response"),
        ("Alternative pattern", "moments that contradict the dominant pattern"),
    )
    for index, (name, subject) in enumerate(subjects):
        sections.append(
            {
                "lens": name,
                "status": "viewing_hypothesis",
                "critic_reports": (
                    "The attributed sources report a pattern of withholding and interruption; "
                    "this remains a secondary interpretation to verify."
                ),
                "theory_explains": (
                    f"The supplied framework explains how {subject} can organise attention through "
                    "relationships that remain available for comparison rather than assumption."
                ),
                "hypothesis": (
                    f"The film may use {subject} to redistribute uncertainty; test whether the "
                    "pattern recurs at comparable narrative transitions and whether exceptions matter."
                ),
                "mechanism": (
                    f"Because {subject} changes what can be compared before and after a transition, "
                    "the pattern could delay certainty and redirect attention towards relationships."
                ),
                "alternative_reading": (
                    "If counterexamples cluster elsewhere, the apparent pattern might follow the "
                    "viewer's selected sample rather than a sustained formal strategy."
                ),
                "verify": (
                    f"Log each relevant instance in category {index + 1}, compare adjacent examples "
                    "and note counterexamples before deciding whether the hypothesis holds."
                ),
                "source_ids": ["S1", "S2"],
                "critic_claim_ids": [],
                "attributed_source_ids": ["E1", "E2"],
                "confidence": "medium",
            }
        )
    return cast(
        dict[str, Any],
        GroundedStudy.model_validate(
            {
                "title": "A synthetic close-viewing study of uncertainty",
                "central_argument": (
                    "The film might organise uncertainty through relations among framing, editing and "
                    "sound; the following hypotheses specify observable comparisons rather than facts."
                ),
                "sections": sections,
                "creator_intent_boundary": (
                    "No supplied evidence establishes creator intention, so every formal proposition "
                    "remains a viewing hypothesis unless an attributed statement is later added."
                ),
                "next_viewing": [
                    "Log recurring frame boundaries and eyeline changes.",
                    "Compare transition duration with shifts in available information.",
                    "Track off-screen sound against visible reaction and counterexamples.",
                ],
            }
        ).model_dump(),
    )


def fault_candidate(scenario: str) -> tuple[dict[str, Any], tuple[str, ...]]:
    candidate = valid_candidate()
    if scenario == "one_invalid_citation":
        candidate["sections"][0]["source_ids"] = ["S999"]
        return candidate, ("sections.0.source_ids",)
    if scenario == "one_schema_invalid_field":
        candidate["sections"][1]["mechanism"] = "Too short."
        return candidate, ("sections.1.mechanism",)
    if scenario == "two_invalid_fields":
        candidate["sections"][0]["attributed_source_ids"] = ["E999"]
        candidate["sections"][2]["source_ids"] = ["S999"]
        return candidate, (
            "sections.0.attributed_source_ids",
            "sections.2.source_ids",
        )
    if scenario == "one_schema_and_one_citation":
        candidate["sections"][1]["mechanism"] = "Too short."
        candidate["sections"][3]["source_ids"] = ["S999"]
        return candidate, (
            "sections.1.mechanism",
            "sections.3.source_ids",
        )
    raise ValueError("Unknown structural-repair fault scenario.")


def repair_experiment(programme: dict[str, Any]) -> dict[str, Any]:
    return next(item for item in programme["experiments"] if item["id"] == "A02")


def comparison_authorised(programme: dict[str, Any]) -> bool:
    experiment = repair_experiment(programme)
    proposed = experiment.get("proposed_budget", {})
    confirmation = experiment.get("paid_budget_confirmation")
    return bool(
        programme.get("status") == "a02_structural_repair_ablation_approved"
        and programme.get("owner_mandate", {}).get("paid_model_or_provider_calls_authorised")
        is True
        and experiment.get("status") == "approved_one_run"
        and isinstance(confirmation, dict)
        and confirmation.get("confirmed") is True
        and confirmation.get("authorisation_consumed") is False
        and confirmation.get("approved_fault_scenarios") == proposed.get("fault_scenarios")
        and confirmation.get("approved_repetitions_per_lane_per_scenario")
        == proposed.get("repetitions_per_lane_per_scenario")
        and confirmation.get("approved_expected_model_calls")
        == proposed.get("expected_model_calls")
        and confirmation.get("approved_maximum_model_calls") == proposed.get("maximum_model_calls")
    )


def require_authorised_run_inputs(
    args: argparse.Namespace,
    experiment: dict[str, Any],
) -> None:
    confirmation = experiment.get("paid_budget_confirmation", {})
    if args.programme.resolve() != DEFAULT_PROGRAMME.resolve():
        raise SystemExit("The repair ablation requires the committed programme path.")
    expected = {
        "output": confirmation.get("approved_report_path"),
        "run_lock": confirmation.get("approved_run_lock_path"),
    }
    actual = {"output": args.output, "run_lock": args.run_lock}
    for name, approved in expected.items():
        if not isinstance(approved, str) or not approved.strip():
            raise SystemExit(f"The repair ablation lacks an approved {name} path.")
        if actual[name].resolve() != (ROOT / approved).resolve():
            raise SystemExit(f"The repair ablation {name} path is not authorised.")


def _set_path(value: dict[str, Any], path: str, replacement: Any) -> None:
    parts = path.split(".")
    target: Any = value
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = parts[-1]
    if isinstance(target, list):
        target[int(final)] = replacement
    else:
        target[final] = replacement


def accepted_fields_preserved(
    candidate: dict[str, Any],
    repaired: dict[str, Any],
    repair_paths: tuple[str, ...],
) -> bool:
    candidate_copy = deepcopy(candidate)
    repaired_copy = {
        key: deepcopy(repaired[key]) for key in GroundedStudy.model_fields if key in repaired
    }
    marker = {"firstroll_repair_field": True}
    for path in repair_paths:
        _set_path(candidate_copy, path, marker)
        _set_path(repaired_copy, path, marker)
    return candidate_copy == repaired_copy


def valid_output(
    service: DeepSeekStudyService, result: dict[str, Any], packet: EvidencePacket
) -> bool:
    grounded = GroundedStudy.model_validate(
        {key: result[key] for key in GroundedStudy.model_fields if key in result}
    ).model_dump()
    sources = service._theory_source_records(packet)
    service._validate_result(
        grounded,
        {source["id"] for source in sources},
        {claim.claim_id for claim in packet.critical_claims},
        {source.evidence_id for source in packet.attributed_sources},
    )
    return bool(result.get("quality", {}).get("status") == "passed")


def run_patch_sample(
    service: DeepSeekStudyService,
    packet: EvidencePacket,
    scenario: str,
    repetition: int,
) -> dict[str, Any]:
    candidate, initial_paths = fault_candidate(scenario)
    current = candidate
    paths = initial_paths
    started_at = monotonic()
    model_calls = 0
    total_tokens = 0
    failure_category: str | None = None
    result: dict[str, Any] | None = None
    attempts = 0
    for _ in range(MAX_PATCH_CALLS_PER_SAMPLE):
        attempts += 1
        trace = StudyTrace()
        try:
            result = service.repair_invalid_once(
                current,
                paths,
                evidence_packet=packet,
                trace=trace,
            )
        except StudyGenerationError as exc:
            snapshot = trace.snapshot()
            model_calls += int(snapshot.get("counts", {}).get("model_calls", 0))
            total_tokens += int(snapshot.get("counts", {}).get("total_tokens", 0))
            failure_category = exc.category
            if exc.repair_candidate is not None and exc.repair_paths and attempts < 2:
                current = exc.repair_candidate
                paths = exc.repair_paths
                continue
            break
        except Exception:
            snapshot = trace.snapshot()
            model_calls += int(snapshot.get("counts", {}).get("model_calls", 0))
            total_tokens += int(snapshot.get("counts", {}).get("total_tokens", 0))
            failure_category = "transport_failure"
            break
        snapshot = trace.snapshot()
        model_calls += int(snapshot.get("counts", {}).get("model_calls", 0))
        total_tokens += int(snapshot.get("counts", {}).get("total_tokens", 0))
        break

    valid = False
    preserved = False
    quality_score = 0.0
    if result is not None:
        try:
            valid = valid_output(service, result, packet)
            preserved = accepted_fields_preserved(candidate, result, initial_paths)
            quality_score = round(float(result.get("quality", {}).get("score", 0.0)) * 100, 2)
        except (StudyGenerationError, ValueError, TypeError):
            valid = False
    sample = {
        "scenario": scenario,
        "repetition": repetition,
        "lane": "targeted_field_patch",
        "status": "passed" if valid and preserved else "failed",
        "duration_seconds": round(max(0.0, monotonic() - started_at), 3),
        "model_calls": model_calls,
        "total_tokens": total_tokens,
        "quality_score": quality_score if valid else 0.0,
        "citation_and_schema_valid": valid,
        "accepted_fields_preserved": preserved,
        "repair_attempts": attempts,
    }
    if failure_category is not None:
        sample["failure_category"] = failure_category
    return sample


def run_regeneration_sample(
    service: DeepSeekStudyService,
    packet: EvidencePacket,
    scenario: str,
    repetition: int,
) -> dict[str, Any]:
    trace = StudyTrace()
    started_at = monotonic()
    result: dict[str, Any] | None = None
    failure_category: str | None = None
    try:
        result = service.generate_once(
            SYNTHETIC_FILM,
            [],
            SYNTHETIC_FOCUS,
            evidence_packet=packet,
            trace=trace,
        )
    except StudyGenerationError as exc:
        failure_category = exc.category
    except Exception:
        failure_category = "transport_failure"
    snapshot = trace.snapshot()
    valid = False
    quality_score = 0.0
    if result is not None:
        try:
            valid = valid_output(service, result, packet)
            quality_score = round(float(result.get("quality", {}).get("score", 0.0)) * 100, 2)
        except (StudyGenerationError, ValueError, TypeError):
            valid = False
    sample = {
        "scenario": scenario,
        "repetition": repetition,
        "lane": "complete_regeneration",
        "status": "passed" if valid else "failed",
        "duration_seconds": round(max(0.0, monotonic() - started_at), 3),
        "model_calls": int(snapshot.get("counts", {}).get("model_calls", 0)),
        "total_tokens": int(snapshot.get("counts", {}).get("total_tokens", 0)),
        "quality_score": quality_score if valid else 0.0,
        "citation_and_schema_valid": valid,
        "accepted_fields_preserved": None,
        "repair_attempts": 0,
    }
    if failure_category is not None:
        sample["failure_category"] = failure_category
    return sample


def percentile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def lane_summary(samples: list[dict[str, Any]], lane: str) -> dict[str, Any]:
    selected = [item for item in samples if item["lane"] == lane]
    durations = [float(item["duration_seconds"]) for item in selected]
    return {
        "scheduled_samples": len(selected),
        "completed_samples": sum(item["status"] == "passed" for item in selected),
        "mean_quality_all_scheduled": round(
            statistics.fmean(float(item["quality_score"]) for item in selected), 2
        )
        if selected
        else 0.0,
        "p50_latency_seconds": round(percentile(durations, 0.5), 3),
        "p95_latency_seconds": round(percentile(durations, 0.95), 3),
        "total_model_calls": sum(int(item["model_calls"]) for item in selected),
        "total_tokens": sum(int(item["total_tokens"]) for item in selected),
        "valid_output_ratio": round(
            sum(item["citation_and_schema_valid"] is True for item in selected) / len(selected), 4
        )
        if selected
        else 0.0,
    }


def ratio(left: float, right: float) -> float | None:
    return round(left / right, 6) if right > 0 else None


def evaluate_targets(
    samples: list[dict[str, Any]],
    patch: dict[str, Any],
    regeneration: dict[str, Any],
    maximum_model_calls: int,
    transport_calls: int | None = None,
) -> list[dict[str, Any]]:
    patch_samples = [item for item in samples if item["lane"] == "targeted_field_patch"]
    checks = {
        "complete_scheduled_sample_set": len(samples) == len(SCENARIOS) * REPETITIONS * 2,
        "patch_completion_ratio": patch["completed_samples"] == len(patch_samples),
        "regeneration_completion_ratio": (
            regeneration["completed_samples"] == regeneration["scheduled_samples"]
        ),
        "patch_schema_and_citation_validity": patch["valid_output_ratio"] == 1.0,
        "accepted_field_preservation": all(
            item["accepted_fields_preserved"] is True for item in patch_samples
        ),
        "patch_p50_latency_ratio": (
            ratio(patch["p50_latency_seconds"], regeneration["p50_latency_seconds"]) is not None
            and cast(
                float, ratio(patch["p50_latency_seconds"], regeneration["p50_latency_seconds"])
            )
            <= 0.8
        ),
        "patch_p95_latency_ratio": (
            ratio(patch["p95_latency_seconds"], regeneration["p95_latency_seconds"]) is not None
            and cast(
                float, ratio(patch["p95_latency_seconds"], regeneration["p95_latency_seconds"])
            )
            <= 0.9
        ),
        "patch_token_ratio": (
            ratio(patch["total_tokens"], regeneration["total_tokens"]) is not None
            and cast(float, ratio(patch["total_tokens"], regeneration["total_tokens"])) <= 0.6
        ),
        "patch_quality_non_inferiority": (
            patch["mean_quality_all_scheduled"] >= regeneration["mean_quality_all_scheduled"] - 1.0
        ),
        "total_model_call_budget": (
            patch["total_model_calls"] + regeneration["total_model_calls"] <= maximum_model_calls
        ),
        "transport_call_telemetry_complete": (
            transport_calls is None
            or patch["total_model_calls"] + regeneration["total_model_calls"] == transport_calls
        ),
    }
    return [
        {"target_id": target_id, "status": "passed" if passed else "failed"}
        for target_id, passed in checks.items()
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen structural field-patch versus regeneration ablation once."
    )
    parser.add_argument("--programme", type=Path, default=DEFAULT_PROGRAMME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-lock", type=Path, default=DEFAULT_RUN_LOCK)
    return parser.parse_args()


def main_cli() -> int:
    args = parse_args()
    programme = json.loads(args.programme.read_text(encoding="utf-8"))
    if not comparison_authorised(programme):
        raise SystemExit("The autonomous programme does not authorise the repair ablation.")
    if not main.local_agent_enabled():
        raise SystemExit("Set FIRSTROLL_LOCAL_AGENT_ENABLED=1 for the local ablation.")
    experiment = repair_experiment(programme)
    require_authorised_run_inputs(args, experiment)
    require_committed_source()
    if args.output.exists():
        raise SystemExit("The repair-ablation output path already exists.")
    if args.run_lock.exists():
        raise SystemExit("The private one-run repair lock already exists.")
    validate_private_packet_output_path(args.run_lock)

    revision = source_revision()
    packet = synthetic_packet()
    recorder = SafeRecordingTransport()
    service = DeepSeekStudyService(main.settings_store, transport=recorder)
    write_private_packets(
        args.run_lock,
        {
            "schema_version": 1,
            "programme_id": programme["programme_id"],
            "experiment_id": "A02",
            "source_revision": revision,
            "status": "consumed_on_start",
        },
    )

    samples = []
    for repetition in range(1, REPETITIONS + 1):
        order = (
            ("targeted_field_patch", "complete_regeneration")
            if repetition % 2
            else ("complete_regeneration", "targeted_field_patch")
        )
        for scenario in SCENARIOS:
            for lane in order:
                if lane == "targeted_field_patch":
                    samples.append(run_patch_sample(service, packet, scenario, repetition))
                else:
                    samples.append(run_regeneration_sample(service, packet, scenario, repetition))

    patch = lane_summary(samples, "targeted_field_patch")
    regeneration = lane_summary(samples, "complete_regeneration")
    targets = evaluate_targets(
        samples,
        patch,
        regeneration,
        int(experiment["proposed_budget"]["maximum_model_calls"]),
        transport_calls=len(recorder.calls),
    )
    report = {
        "schema_version": 1,
        "programme_id": programme["programme_id"],
        "experiment_id": "A02",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": revision,
        "fixture": {
            "kind": "synthetic_public_fault_injection",
            "scenario_count": len(SCENARIOS),
            "repetitions_per_lane_per_scenario": REPETITIONS,
        },
        "samples": samples,
        "summary": {
            "targeted_field_patch": patch,
            "complete_regeneration": regeneration,
            "comparison": {
                "p50_latency_ratio": ratio(
                    patch["p50_latency_seconds"], regeneration["p50_latency_seconds"]
                ),
                "p95_latency_ratio": ratio(
                    patch["p95_latency_seconds"], regeneration["p95_latency_seconds"]
                ),
                "total_token_ratio": ratio(patch["total_tokens"], regeneration["total_tokens"]),
                "patch_minus_regeneration_quality": round(
                    patch["mean_quality_all_scheduled"]
                    - regeneration["mean_quality_all_scheduled"],
                    2,
                ),
            },
            "total_model_calls": len(recorder.calls),
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
