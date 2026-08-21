from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.criticism import CriticalClaim, ReviewSource  # noqa: E402
from app.backend.evidence import EvidencePacket  # noqa: E402
from app.backend.packet_quality import assess_evidence_packet  # noqa: E402
from app.backend.video_sources import FilmVideo  # noqa: E402


DEFAULT_CASES = ROOT / "evals" / "packet_quality_cases.json"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "packet-quality-current.json"
FORBIDDEN_RESULT_KEYS = {
    "content",
    "director",
    "excerpt",
    "film",
    "focus",
    "passages",
    "prompt",
    "question",
    "reviews",
    "summary",
    "text",
    "title",
    "videos",
}


def source_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def fixture_fingerprint(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    serialised = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]


def build_packet(case: dict[str, Any]) -> EvidencePacket:
    claims = [CriticalClaim.model_validate(item) for item in case.get("critical_claims", [])]
    reviews = [ReviewSource.model_validate(item) for item in case.get("reviews", [])]
    videos = [FilmVideo.model_validate(item) for item in case.get("videos", [])]
    return EvidencePacket.from_retrieval(
        case["film"],
        case["retrieval"],
        case.get("focus"),
        claims,
        reviews=reviews,
        videos=videos,
    )


def check_case_expectations(case: dict[str, Any], assessment: dict[str, Any]) -> list[str]:
    audit = case.get("audit", {})
    failures = []
    if assessment["identity"]["matches_expected"] is not True:
        failures.append("identity_not_matched")
    required_languages = {str(value).casefold() for value in audit.get("required_languages", [])}
    if not required_languages <= set(assessment["diversity"]["languages"]):
        failures.append("required_language_missing")
    instructions_expected = audit.get("instruction_items_present") is True
    flagged = int(assessment["instruction_safety"]["flagged_items"])
    if instructions_expected and flagged < 1:
        failures.append("instruction_not_detected")
    if not instructions_expected and flagged:
        failures.append("unexpected_instruction_flag")
    if instructions_expected and not assessment["instruction_safety"]["containment_boundary"]:
        failures.append("instruction_not_contained")
    return failures


def assert_report_redacted(report: dict[str, Any]) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).casefold() in FORBIDDEN_RESULT_KEYS:
                    raise ValueError(f"Unsafe packet-quality result field: {key}")
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(report)


def aggregate(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    assessments = [item["assessment"] for item in case_results]
    statuses = Counter(item["status"] for item in assessments)
    issues = Counter(
        issue
        for assessment in assessments
        for issue in assessment.get("issues", [])
    )
    return {
        "case_count": len(case_results),
        "assessed_cases": sum(not item["expectation_failures"] for item in case_results),
        "expectation_failure_count": sum(
            len(item["expectation_failures"]) for item in case_results
        ),
        "packet_status_counts": dict(sorted(statuses.items())),
        "issue_counts": dict(sorted(issues.items())),
        "mean_provenance_completeness": round(
            statistics.mean(
                assessment["provenance"]["completeness_ratio"]
                for assessment in assessments
            ),
            4,
        ),
        "mean_duplicate_ratio": round(
            statistics.mean(
                assessment["duplication"]["duplicate_ratio"]
                for assessment in assessments
            ),
            4,
        ),
        "mean_focus_relevance": round(
            statistics.mean(
                assessment["focus_relevance"]["relevance_ratio"]
                for assessment in assessments
            ),
            4,
        ),
        "flagged_instruction_items": sum(
            assessment["instruction_safety"]["flagged_items"]
            for assessment in assessments
        ),
        "contained_instruction_cases": sum(
            assessment["instruction_safety"]["flagged_items"] > 0
            and assessment["instruction_safety"]["containment_boundary"]
            for assessment in assessments
        ),
        "model_calls": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate synthetic FirstRoll packet quality without synthesis."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case", action="append", dest="case_ids")
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
        raise SystemExit("The packet-quality suite contains no cases.")

    case_results = []
    for index, case in enumerate(cases, start=1):
        packet = build_packet(case)
        assessment = assess_evidence_packet(
            packet,
            expected_identity=case.get("expected_identity"),
        )
        failures = check_case_expectations(case, assessment)
        result = {
            "case_id": case["id"],
            "challenge": case["challenge"],
            "expectation_failures": failures,
            "assessment": assessment,
        }
        case_results.append(result)
        print(
            f"[{index}/{len(cases)}] {case['id']} · {assessment['status']}"
            f" · {len(assessment['issues'])} issue(s)",
            flush=True,
        )

    report = {
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "system": "synthetic_packet_quality_baseline",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": source_revision(),
        "fixture_fingerprint": fixture_fingerprint(args.cases),
        "protocol": {
            "source_cases": args.cases.relative_to(ROOT).as_posix(),
            "synthesis_called": False,
            "private_sources_loaded": False,
            "result_contains_source_text": False,
        },
        "quality_scope": (
            "Deterministic identity, citation readiness, provenance, duplication, lexical focus, "
            "diversity, instruction containment, selection pressure and packet size; not factual "
            "film-analysis correctness or human usefulness."
        ),
        "aggregate": aggregate(case_results),
        "cases": case_results,
    }
    assert_report_redacted(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["aggregate"], indent=2), flush=True)
    print(f"Report: {args.output}", flush=True)
    return 0 if report["aggregate"]["expectation_failure_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main_cli())
