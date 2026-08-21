from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.backend import main
from app.backend.study_service import DeepSeekStudyService


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "evals" / "agent_cases.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "baseline-current.json"
OBSERVABLE_VERBS = ("log", "compare", "count", "note", "track", "mark", "inspect")
CALIBRATION_MARKERS = ("may", "might", "could", "hypothesis", "test whether", "examine whether", "if")


@dataclass
class RecordingTransport:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        started = time.perf_counter()
        response = DeepSeekStudyService._request_json(url, payload, key)
        usage = response.get("usage") if isinstance(response, dict) else None
        self.calls.append(
            {
                "endpoint": url.rsplit("/", 1)[-1],
                "latency_seconds": round(time.perf_counter() - started, 3),
                "model": response.get("model") if isinstance(response, dict) else None,
                "usage": usage if isinstance(usage, dict) else {},
            }
        )
        return response


def normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def identity_matches(film: dict[str, Any], expected: dict[str, Any]) -> bool:
    directors = film.get("directors") or film.get("credits", {}).get("directors") or []
    expected_director = normalise(expected.get("director"))
    return bool(
        normalise(film.get("title")) == normalise(expected.get("title"))
        and film.get("year") == expected.get("year")
        and any(expected_director == normalise(name) for name in directors)
    )


def score_study(study: dict[str, Any], identity_ok: bool) -> dict[str, Any]:
    sections = study.get("sections") if isinstance(study.get("sections"), list) else []
    sources = study.get("sources") if isinstance(study.get("sources"), list) else []
    source_ids = {str(source.get("id")) for source in sources if isinstance(source, dict)}
    critical_ids = {
        str(claim.get("claim_id"))
        for claim in study.get("critical_claims", [])
        if isinstance(claim, dict)
    }
    attributed_ids = {
        str(source.get("evidence_id"))
        for source in study.get("attributed_sources", [])
        if isinstance(source, dict)
    }
    cited_sources: set[str] = set()
    citations_valid = bool(sections)
    calibrated_sections = 0
    observable_sections = 0
    for section in sections:
        if not isinstance(section, dict):
            citations_valid = False
            continue
        cited = {str(value) for value in section.get("source_ids", [])}
        critics = {str(value) for value in section.get("critic_claim_ids", [])}
        attributed = {str(value) for value in section.get("attributed_source_ids", [])}
        cited_sources.update(cited)
        citations_valid = citations_valid and bool(cited) and cited <= source_ids
        citations_valid = citations_valid and critics <= critical_ids and attributed <= attributed_ids
        combined = " ".join(
            str(section.get(field) or "")
            for field in ("hypothesis", "mechanism", "alternative_reading")
        ).casefold()
        if section.get("status") == "viewing_hypothesis" and any(
            marker in combined for marker in CALIBRATION_MARKERS
        ):
            calibrated_sections += 1
        verify = str(section.get("verify") or "").casefold()
        if any(verb in verify for verb in OBSERVABLE_VERBS):
            observable_sections += 1

    section_count = len(sections)
    quality = study.get("quality") if isinstance(study.get("quality"), dict) else {}
    gate_score = float(quality.get("score") or 0)
    gate_passed = quality.get("status") == "passed"
    structured = bool(
        study.get("title")
        and study.get("central_argument")
        and 4 <= section_count <= 6
        and study.get("creator_intent_boundary")
        and len(study.get("next_viewing") or []) >= 3
    )
    calibration_ratio = calibrated_sections / section_count if section_count else 0
    observable_ratio = observable_sections / section_count if section_count else 0
    target_citations = min(4, len(source_ids))
    coverage_ratio = min(1.0, len(cited_sources) / target_citations) if target_citations else 0
    components = {
        "identity": 15.0 if identity_ok else 0.0,
        "structured_completion": 10.0 if structured else 0.0,
        # Acceptance and prose quality are related but distinct. A blocking failure
        # receives no gate points; an accepted study receives points proportional to
        # its section-average score, so generic wording remains visible in the total.
        "deterministic_quality_gate": round(25 * gate_score, 2) if gate_passed else 0.0,
        "citation_integrity": 20.0 if citations_valid else 0.0,
        "epistemic_calibration": round(10 * calibration_ratio, 2),
        "observable_verification": round(10 * observable_ratio, 2),
        "evidence_coverage": round(10 * coverage_ratio, 2),
    }
    return {
        "score": round(sum(components.values()), 2),
        "components": components,
        "quality_gate_status": quality.get("status", "missing"),
        "quality_gate_score": gate_score,
        "quality_gate_central_issues": quality.get("central_issues", []),
        "quality_gate_failed_sections": [
            section
            for section in quality.get("sections", [])
            if isinstance(section, dict) and section.get("issues")
        ],
        "repair_attempted": bool(quality.get("repair_attempted")),
        "section_count": section_count,
        "valid_citations": citations_valid,
        "distinct_theory_sources_cited": len(cited_sources),
        "available_theory_sources": len(source_ids),
        "calibrated_section_ratio": round(calibration_ratio, 3),
        "observable_verification_ratio": round(observable_ratio, 3),
    }


def percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    interpolated = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(interpolated, 3)


def configuration_fingerprint() -> dict[str, Any]:
    connectors = main.settings_store.public_connectors()
    index = main.library_index.status()
    safe_connectors = {
        connector["id"]: {
            "state": connector["state"],
            "configured": connector["configured"],
            "credential_source": connector["credential_source"],
        }
        for connector in connectors
    }
    value = {
        "model": main.study_service.model,
        "connectors": safe_connectors,
        "library_documents": main.library_catalogue.public_catalogue().get("document_count", 0),
        "index_chunks": index.get("chunk_count", 0),
        "index_schema": index.get("schema_version"),
        "embedding_model": index.get("embedding", {}).get("model"),
    }
    serialised = json.dumps(value, sort_keys=True, separators=(",", ":"))
    value["sha256"] = hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]
    return value


def run_case(client: TestClient, case: dict[str, Any], recorder: RecordingTransport) -> dict[str, Any]:
    started = time.perf_counter()
    timings: dict[str, float] = {}
    result: dict[str, Any] = {
        "case_id": case["id"],
        "challenge": case["challenge"],
        "status": "failed",
        "failure_stage": None,
        "failure_reason": None,
    }
    call_start = len(recorder.calls)
    try:
        stage = time.perf_counter()
        search = client.get("/api/discovery/search", params={"q": case["query"]})
        timings["search"] = round(time.perf_counter() - stage, 3)
        if search.status_code != 200:
            raise RuntimeError(f"search HTTP {search.status_code}: {search.text[:180]}")
        candidates = search.json().get("results", [])
        matches = [film for film in candidates if identity_matches(film, case["expected"])]
        result["candidate_count"] = len(candidates)
        result["identity_ambiguity"] = len(candidates) > 1
        if len(matches) != 1:
            result["failure_stage"] = "identity"
            raise RuntimeError(f"expected exactly one matching identity; found {len(matches)}")
        film = matches[0]
        film_id = str(film["id"])
        result["resolved_film"] = {
            "id": film_id,
            "title": film.get("title"),
            "year": film.get("year"),
            "directors": film.get("directors", []),
        }

        stage = time.perf_counter()
        detail = client.get(f"/api/discovery/films/{film_id}")
        timings["detail"] = round(time.perf_counter() - stage, 3)
        if detail.status_code != 200:
            result["failure_stage"] = "detail"
            raise RuntimeError(f"detail HTTP {detail.status_code}: {detail.text[:180]}")
        film_payload = detail.json().get("film", {})
        result["cached_criticism_providers"] = sorted(
            film_payload.get("critical_research", {}).get("bundles", {}).keys()
        )
        cached_videos = film_payload.get("video_sources", {}).get("bundle") or {}
        result["cached_video_count"] = len(cached_videos.get("videos", []))

        stage = time.perf_counter()
        study_response = client.post(
            f"/api/discovery/films/{film_id}/study",
            json={"question": case["question"]},
        )
        timings["study"] = round(time.perf_counter() - stage, 3)
        if study_response.status_code != 200:
            result["failure_stage"] = "study"
            raise RuntimeError(
                f"study HTTP {study_response.status_code}: {study_response.text[:240]}"
            )
        study = study_response.json().get("study", {})
        result["quality"] = score_study(study, identity_ok=True)
        result["study_summary"] = {
            "title": study.get("title"),
            "central_argument": study.get("central_argument"),
            "section_lenses": [
                section.get("lens") for section in study.get("sections", []) if isinstance(section, dict)
            ],
            "model": study.get("model"),
        }
        result["retrieval"] = {
            "method": study.get("evidence_packet", {}).get("retrieval", {}).get("method"),
            "candidate_count": study.get("evidence_packet", {}).get("retrieval", {}).get(
                "candidate_count", 0
            ),
            "theory_source_count": len(study.get("sources", [])),
            "critical_claim_count": len(study.get("critical_claims", [])),
            "attributed_source_count": len(study.get("attributed_sources", [])),
        }
        result["study_observability"] = study.get("observability", {})
        result["status"] = "passed"
    except Exception as exc:  # The benchmark must record failures and continue to later cases.
        if result["failure_stage"] is None:
            result["failure_stage"] = "search"
        result["failure_reason"] = str(exc)
        result["quality"] = {"score": 0.0}
    finally:
        result["latency_seconds"] = {
            **timings,
            "end_to_end": round(time.perf_counter() - started, 3),
        }
        result["model_calls"] = recorder.calls[call_start:]
    return result


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(item["latency_seconds"]["end_to_end"]) for item in results]
    study_latencies = [
        float(item["latency_seconds"]["study"])
        for item in results
        if "study" in item["latency_seconds"]
    ]
    failures = [item for item in results if item["status"] != "passed"]
    completed = [item for item in results if item["status"] == "passed"]
    quality_scores = [float(item.get("quality", {}).get("score", 0)) for item in completed]
    gate_passes = [
        item
        for item in completed
        if item.get("quality", {}).get("quality_gate_status") == "passed"
    ]
    total_tokens = 0
    model_calls = 0
    for item in results:
        for call in item.get("model_calls", []):
            model_calls += 1
            usage = call.get("usage", {})
            total_tokens += int(usage.get("total_tokens") or 0)
    return {
        "case_count": len(results),
        "successful_cases": len(results) - len(failures),
        "failed_cases": len(failures),
        "operational_failure_rate": round(len(failures) / len(results), 4) if results else None,
        "failure_rate": round(len(failures) / len(results), 4) if results else None,
        "mean_quality_score": round(statistics.mean(quality_scores), 2) if quality_scores else None,
        "median_quality_score": round(statistics.median(quality_scores), 2) if quality_scores else None,
        "quality_gate_pass_rate": (
            round(len(gate_passes) / len(completed), 4) if completed else None
        ),
        "quality_acceptance_failure_rate": (
            round(1 - len(gate_passes) / len(completed), 4) if completed else None
        ),
        "repair_rate": (
            round(
                sum(bool(item.get("quality", {}).get("repair_attempted")) for item in completed)
                / len(completed),
                4,
            )
            if completed
            else None
        ),
        "latency_seconds": {
            "mean_end_to_end": round(statistics.mean(latencies), 3) if latencies else None,
            "p50_end_to_end": percentile(latencies, 0.5),
            "p95_end_to_end": percentile(latencies, 0.95),
            "mean_study": round(statistics.mean(study_latencies), 3) if study_latencies else None,
        },
        "model_calls": model_calls,
        "total_tokens": total_tokens,
        "failure_stages": {
            stage: sum(item.get("failure_stage") == stage for item in failures)
            for stage in ("search", "identity", "detail", "study")
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate FirstRoll's fixed film-study workflow.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case", action="append", dest="case_ids", help="Run only this case ID.")
    return parser.parse_args()


def main_cli() -> int:
    args = parse_args()
    suite = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = suite.get("cases", [])
    if args.case_ids:
        requested = set(args.case_ids)
        cases = [case for case in cases if case.get("id") in requested]
        missing = requested - {case.get("id") for case in cases}
        if missing:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing))}")
    if not cases:
        raise SystemExit("The evaluation suite contains no cases.")

    recorder = RecordingTransport()
    main.study_service._transport = recorder
    client = TestClient(main.app)
    results = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}", flush=True)
        result = run_case(client, case, recorder)
        results.append(result)
        print(
            f"  {result['status']} · quality {result['quality'].get('score', 0):.1f}"
            f" · {result['latency_seconds']['end_to_end']:.2f}s",
            flush=True,
        )

    report = {
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "system": "fixed_workflow_baseline",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "configuration": configuration_fingerprint(),
        },
        "quality_scope": (
            "Automated structural, citation, calibration and verifiability proxy; it does not "
            "establish the factual correctness of unseen film-form claims."
        ),
        "summary": aggregate(results),
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2), flush=True)
    print(f"Report: {args.output}", flush=True)
    return 0 if report["summary"]["failed_cases"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main_cli())
