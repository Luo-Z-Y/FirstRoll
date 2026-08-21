from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend import main  # noqa: E402
from app.backend.evidence import EvidencePacket  # noqa: E402
from app.backend.study_observability import StudyTrace  # noqa: E402


DEFAULT_CASES = ROOT / "evals" / "agent_cases.json"
DEFAULT_REFERENCE = ROOT / "evals" / "results" / "baseline-2026-08-18.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "packet-baseline-current.json"
PACKET_STAGES = (
    "criticism_cache",
    "video_cache",
    "retrieval_planning",
    "lexical_retrieval",
    "semantic_retrieval",
    "fusion_and_selection",
    "packet_assembly",
)
POST_PACKET_STAGES = (
    "prompt_serialisation",
    "model_transport",
    "validation_and_repair",
)
SAFE_RETRIEVAL_METHOD = re.compile(r"[a-z0-9_]{1,64}")
SAFE_FAILURE_KINDS = {
    "AuthConfigurationError",
    "LookupError",
    "OSError",
    "RuntimeError",
    "StudyGenerationError",
    "TimeoutExpired",
    "ValueError",
}
FORBIDDEN_REPORT_KEYS = {
    "content",
    "excerpt",
    "passages",
    "prompt",
    "question",
    "reviews",
    "source_text",
}


def percentile(values: Sequence[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(value, 3)


def load_case_specs(cases_path: Path, reference_path: Path) -> list[dict[str, Any]]:
    suite = json.loads(cases_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    resolved = {
        item["case_id"]: item.get("resolved_film", {}).get("id")
        for item in reference.get("cases", [])
    }
    specs = []
    for case in suite.get("cases", []):
        case_id = str(case.get("id") or "")
        film_id = str(resolved.get(case_id) or "")
        if not case_id or not film_id:
            raise ValueError(f"The reference result has no canonical film ID for {case_id or '?'}.")
        specs.append(
            {
                "case_id": case_id,
                "film_id": film_id,
                "question": str(case.get("question") or ""),
                "redaction_values": [
                    str(case.get("query") or ""),
                    str(case.get("question") or ""),
                    str(case.get("expected", {}).get("title") or ""),
                    str(case.get("expected", {}).get("director") or ""),
                ],
            }
        )
    if not specs:
        raise ValueError("The packet benchmark suite contains no cases.")
    return specs


def safe_packet_metrics(packet: EvidencePacket) -> dict[str, int]:
    attributed = packet.retrieval.get("attributed_selection", {})
    theory_candidates = int(packet.retrieval.get("candidate_count", 0))
    return {
        "theory_candidates": theory_candidates,
        "theory_sources": len(packet.theory_sources),
        "theory_unselected": max(0, theory_candidates - len(packet.theory_sources)),
        "critical_claims": len(packet.critical_claims),
        "attributed_candidates": int(attributed.get("candidate_items", 0)),
        "attributed_sources": len(packet.attributed_sources),
        "attributed_omitted": int(attributed.get("omitted_items", 0)),
        "attributed_truncated": int(attributed.get("truncated_items", 0)),
        "boundaries": len(packet.boundaries),
        "theory_characters": sum(len(item.content) for item in packet.theory_sources),
        "critical_claim_characters": sum(
            len(claim.model_dump_json()) for claim in packet.critical_claims
        ),
        "attributed_characters": sum(len(item.content) for item in packet.attributed_sources),
        "packet_json_characters": len(packet.model_dump_json()),
    }


def safe_retrieval_method(value: Any) -> str:
    method = str(value or "unknown").strip().casefold()
    return method if SAFE_RETRIEVAL_METHOD.fullmatch(method) else "other"


def safe_failure_kind(exc: BaseException) -> str:
    name = type(exc).__name__
    return name if name in SAFE_FAILURE_KINDS else "PacketBenchmarkError"


def stage_map(observability: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(stage.get("name")): stage
        for stage in observability.get("stages", [])
        if isinstance(stage, dict)
    }


def packet_sample(
    spec: dict[str, Any],
    *,
    sample_kind: str,
    sample_index: int,
    film: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        selected_film = film or main.discovery_service.detail(spec["film_id"])["film"]
    except Exception as exc:
        return {
            "sample_kind": sample_kind,
            "sample_index": sample_index,
            "status": "failed",
            "failure_stage": "film_context",
            "failure_kind": safe_failure_kind(exc),
        }

    trace = StudyTrace()
    trace.skip("film_context")
    try:
        prepared = main.prepare_film_study(
            spec["film_id"],
            selected_film,
            spec["question"],
            public_mode=False,
            trace=trace,
        )
        for stage in POST_PACKET_STAGES:
            trace.skip(stage)
        trace.finish("completed")
        observability = trace.snapshot()
        stages = stage_map(observability)
        return {
            "sample_kind": sample_kind,
            "sample_index": sample_index,
            "status": "completed",
            "packet_prepare_ms": stages["end_to_end"]["duration_ms"],
            "retrieval_method": safe_retrieval_method(
                prepared["reading"].get("method")
            ),
            "packet_metrics": safe_packet_metrics(prepared["packet"]),
            "observability": observability,
        }
    except Exception as exc:
        trace.finish("failed")
        observability = trace.snapshot()
        failed_stage = next(
            (
                name
                for name, stage in stage_map(observability).items()
                if stage.get("status") == "failed"
            ),
            "packet_preparation",
        )
        return {
            "sample_kind": sample_kind,
            "sample_index": sample_index,
            "status": "failed",
            "failure_stage": failed_stage,
            "failure_kind": safe_failure_kind(exc),
            "observability": observability,
        }


def latency_summary(samples: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [sample for sample in samples if sample.get("status") == "completed"]
    values = [float(sample["packet_prepare_ms"]) for sample in completed]
    return {
        "attempted": len(samples),
        "completed": len(completed),
        "failed": len(samples) - len(completed),
        "mean_ms": round(statistics.mean(values), 3) if values else None,
        "p50_ms": percentile(values, 0.5),
        "p95_ms": percentile(values, 0.95),
        "minimum_ms": round(min(values), 3) if values else None,
        "maximum_ms": round(max(values), 3) if values else None,
    }


def stage_summary(samples: Sequence[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name in PACKET_STAGES:
        durations = []
        statuses: Counter[str] = Counter()
        for sample in samples:
            stage = stage_map(sample.get("observability", {})).get(name)
            if not stage:
                continue
            status = str(stage.get("status") or "unknown")
            statuses[status] += 1
            if int(stage.get("attempts") or 0) > 0:
                durations.append(float(stage.get("duration_ms") or 0))
        summary[name] = {
            "status_counts": dict(sorted(statuses.items())),
            "mean_ms": round(statistics.mean(durations), 3) if durations else None,
            "p50_ms": percentile(durations, 0.5),
            "p95_ms": percentile(durations, 0.95),
        }
    return summary


def packet_metric_summary(samples: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [sample for sample in samples if sample.get("status") == "completed"]
    names = sorted(
        {
            name
            for sample in completed
            for name in sample.get("packet_metrics", {})
        }
    )
    result: dict[str, Any] = {}
    for name in names:
        values = [int(sample["packet_metrics"][name]) for sample in completed]
        result[name] = {
            "minimum": min(values),
            "median": percentile(values, 0.5),
            "maximum": max(values),
        }
    return result


def configuration_fingerprint() -> dict[str, Any]:
    connectors = main.settings_store.public_connectors()
    index = main.library_index.status()
    value = {
        "runtime": "local_private_edition",
        "connectors": {
            item["id"]: {
                "state": item["state"],
                "configured": item["configured"],
                "credential_source": item["credential_source"],
            }
            for item in connectors
        },
        "library_documents": main.library_catalogue.public_catalogue().get(
            "document_count", 0
        ),
        "index_chunks": index.get("chunk_count", 0),
        "index_schema": index.get("schema_version"),
        "embedding_state": index.get("embedding", {}).get("state"),
        "embedding_model": index.get("embedding", {}).get("model"),
    }
    serialised = json.dumps(value, sort_keys=True, separators=(",", ":"))
    value["sha256"] = hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]
    return value


def git_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()


def run_cold_child(
    spec: dict[str, Any],
    sample_index: int,
    *,
    cases_path: Path,
    reference_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child-case",
        spec["case_id"],
        "--sample-index",
        str(sample_index),
        "--cases",
        str(cases_path),
        "--reference",
        str(reference_path),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "sample_kind": "cold",
            "sample_index": sample_index,
            "status": "failed",
            "failure_stage": "packet_preparation",
            "failure_kind": safe_failure_kind(exc),
        }
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        sample = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        return {
            "sample_kind": "cold",
            "sample_index": sample_index,
            "status": "failed",
            "failure_stage": "child_process",
            "failure_kind": "PacketBenchmarkError",
        }
    return sample if isinstance(sample, dict) else {
        "sample_kind": "cold",
        "sample_index": sample_index,
        "status": "failed",
        "failure_stage": "child_process",
        "failure_kind": "PacketBenchmarkError",
    }


def assert_report_redacted(report: dict[str, Any], specs: Sequence[dict[str, Any]]) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).casefold() in FORBIDDEN_REPORT_KEYS:
                    raise ValueError(f"Unsafe packet benchmark field: {key}")
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(report)
    serialised = json.dumps(report, ensure_ascii=False)
    for spec in specs:
        for value in spec.get("redaction_values", []):
            if value and value in serialised:
                raise ValueError("A film query, question, title or director entered the report.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark FirstRoll evidence-packet preparation without calling a model."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--warm-samples", type=int, default=5)
    parser.add_argument("--cold-processes", type=int, default=2)
    parser.add_argument("--child-timeout", type=int, default=300)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--child-case", help=argparse.SUPPRESS)
    parser.add_argument("--sample-index", type=int, default=1, help=argparse.SUPPRESS)
    return parser.parse_args()


def child_cli(args: argparse.Namespace, specs: Sequence[dict[str, Any]]) -> int:
    matches = [spec for spec in specs if spec["case_id"] == args.child_case]
    if len(matches) != 1:
        sample = {
            "sample_kind": "cold",
            "sample_index": args.sample_index,
            "status": "failed",
            "failure_stage": "case_selection",
            "failure_kind": "ValueError",
        }
    else:
        sample = packet_sample(
            matches[0],
            sample_kind="cold",
            sample_index=args.sample_index,
        )
    print(json.dumps(sample, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0 if sample["status"] == "completed" else 1


def main_cli() -> int:
    args = parse_args()
    if args.warm_samples < 1 or args.cold_processes < 1:
        raise SystemExit("Warm samples and cold processes must both be positive.")
    specs = load_case_specs(args.cases, args.reference)
    if args.child_case:
        return child_cli(args, specs)
    if args.case_ids:
        requested = set(args.case_ids)
        specs = [spec for spec in specs if spec["case_id"] in requested]
        missing = requested - {spec["case_id"] for spec in specs}
        if missing:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing))}")

    case_reports = []
    all_cold: list[dict[str, Any]] = []
    all_warm: list[dict[str, Any]] = []
    for case_number, spec in enumerate(specs, start=1):
        print(f"[{case_number}/{len(specs)}] {spec['case_id']}", flush=True)
        cold = []
        for sample_index in range(1, args.cold_processes + 1):
            sample = run_cold_child(
                spec,
                sample_index,
                cases_path=args.cases,
                reference_path=args.reference,
                timeout_seconds=args.child_timeout,
            )
            cold.append(sample)
            print(
                f"  cold {sample_index}: {sample['status']}"
                + (
                    f" · {sample['packet_prepare_ms']:.3f} ms"
                    if sample["status"] == "completed"
                    else ""
                ),
                flush=True,
            )

        try:
            film = main.discovery_service.detail(spec["film_id"])["film"]
            warmup = packet_sample(
                spec,
                sample_kind="warmup",
                sample_index=0,
                film=film,
            )
            warm = [
                packet_sample(
                    spec,
                    sample_kind="warm",
                    sample_index=sample_index,
                    film=film,
                )
                for sample_index in range(1, args.warm_samples + 1)
            ]
        except Exception as exc:
            warmup = {
                "sample_kind": "warmup",
                "sample_index": 0,
                "status": "failed",
                "failure_stage": "film_context",
                "failure_kind": safe_failure_kind(exc),
            }
            warm = [
                {
                    "sample_kind": "warm",
                    "sample_index": sample_index,
                    "status": "failed",
                    "failure_stage": "film_context",
                    "failure_kind": safe_failure_kind(exc),
                }
                for sample_index in range(1, args.warm_samples + 1)
            ]
        for sample in warm:
            print(
                f"  warm {sample['sample_index']}: {sample['status']}"
                + (
                    f" · {sample['packet_prepare_ms']:.3f} ms"
                    if sample["status"] == "completed"
                    else ""
                ),
                flush=True,
            )

        all_cold.extend(cold)
        all_warm.extend(warm)
        case_reports.append(
            {
                "case_id": spec["case_id"],
                "canonical_film_id": spec["film_id"],
                "warmup_status": warmup["status"],
                "cold": {
                    "summary": latency_summary(cold),
                    "samples": cold,
                },
                "warm": {
                    "summary": latency_summary(warm),
                    "samples": warm,
                },
            }
        )

    all_samples = all_cold + all_warm
    report = {
        "schema_version": 1,
        "suite_id": "firstroll-pre-agent-packet-v1",
        "system": "fixed_workflow_packet_preparation",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": git_revision(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "configuration": configuration_fingerprint(),
        },
        "protocol": {
            "source_cases": args.cases.relative_to(ROOT).as_posix(),
            "canonical_identity_reference": args.reference.relative_to(ROOT).as_posix(),
            "runtime": "local_private_edition",
            "model_calls": 0,
            "film_resolution_timed": False,
            "warmups_per_case": 1,
            "warm_samples_per_case": args.warm_samples,
            "cold_processes_per_case": args.cold_processes,
            "percentile_method": "linear_interpolation_n_minus_1",
            "packet_stages": list(PACKET_STAGES),
        },
        "quality_scope": (
            "Packet latency and aggregate shape only; no generated-study or factual-quality claim."
        ),
        "summary": {
            "case_count": len(case_reports),
            "sample_count": len(all_samples),
            "failed_samples": sum(sample["status"] != "completed" for sample in all_samples),
            "cold": latency_summary(all_cold),
            "warm": latency_summary(all_warm),
            "cold_stages": stage_summary(all_cold),
            "warm_stages": stage_summary(all_warm),
            "packet_metrics": packet_metric_summary(all_samples),
        },
        "cases": case_reports,
    }
    assert_report_redacted(report, specs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"]["warm"], indent=2), flush=True)
    print(f"Report: {args.output}", flush=True)
    return 0 if report["summary"]["failed_samples"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main_cli())
