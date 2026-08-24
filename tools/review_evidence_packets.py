from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CASES = ROOT / "evals" / "agent_cases.json"
DEFAULT_REFERENCE = ROOT / "evals" / "results" / "baseline-2026-08-18.json"
DEFAULT_PRIVATE_OUTPUT = ROOT / ".firstroll" / "evaluations" / "human-packet-review.json"
DEFAULT_REDACTED_OUTPUT = (
    ROOT / ".firstroll" / "evaluations" / "human-packet-review-redacted.json"
)
RUBRIC_DIMENSIONS = (
    "focus_relevance",
    "traceability",
    "source_diversity",
    "epistemic_calibration",
    "filmmaker_actionability",
)
RUBRIC_QUESTIONS = {
    "focus_relevance": "Does the selected evidence directly help answer the stated focus?",
    "traceability": "Can you tell who said what and return to the source or private locator?",
    "source_diversity": "Does the packet balance useful evidence without repetitive padding?",
    "epistemic_calibration": "Are observations, reports, frameworks and hypotheses kept separate?",
    "filmmaker_actionability": "Would this support a more precise close viewing or formal test?",
}


def configure_input_encoding(stream: Any | None = None) -> None:
    stream = stream or sys.stdin
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def source_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def load_case_specs(cases_path: Path, reference_path: Path) -> list[dict[str, Any]]:
    suite = json.loads(cases_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    identities = {
        item["case_id"]: item.get("resolved_film", {}).get("id")
        for item in reference.get("cases", [])
    }
    specs = []
    for case in suite.get("cases", []):
        case_id = str(case.get("id") or "")
        film_id = str(identities.get(case_id) or "")
        if not case_id or not film_id:
            raise ValueError(f"No canonical identity is available for {case_id or '?'}.")
        specs.append(
            {
                "case_id": case_id,
                "film_id": film_id,
                "focus": str(case.get("question") or ""),
            }
        )
    return specs


def case_passes(scores: dict[str, int]) -> bool:
    return bool(
        set(scores) == set(RUBRIC_DIMENSIONS)
        and all(1 <= value <= 5 for value in scores.values())
        and scores["focus_relevance"] >= 4
        and scores["traceability"] >= 4
        and scores["filmmaker_actionability"] >= 4
        and min(scores.values()) >= 3
    )


def aggregate_review(review: dict[str, Any]) -> dict[str, Any]:
    cases = []
    for item in review.get("cases", []):
        scores = {
            dimension: int(item.get("scores", {}).get(dimension, 0))
            for dimension in RUBRIC_DIMENSIONS
        }
        cases.append(
            {
                "case_id": str(item.get("case_id") or ""),
                "scores": scores,
                "passed": case_passes(scores),
            }
        )
    dimension_means = {
        dimension: round(
            sum(item["scores"][dimension] for item in cases) / len(cases), 2
        )
        if cases
        else None
        for dimension in RUBRIC_DIMENSIONS
    }
    passed = sum(item["passed"] for item in cases)
    return {
        "schema_version": 1,
        "suite_id": "firstroll-human-packet-review-v1",
        "programme_id": "firstroll-pre-agent-hardening-v1",
        "recorded_at": review.get("recorded_at"),
        "source_revision": review.get("source_revision"),
        "reviewer_attested": review.get("reviewer_attested") is True,
        "quality_scope": (
            "Human packet focus relevance, traceability, source diversity, epistemic "
            "calibration and filmmaker actionability; no private evidence or reviewer notes."
        ),
        "summary": {
            "case_count": len(cases),
            "passed_cases": passed,
            "failed_cases": len(cases) - passed,
            "pass_ratio": round(passed / len(cases), 4) if cases else 0.0,
            "dimension_means": dimension_means,
        },
        "cases": cases,
    }


def write_private(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def display_packet(case_id: str, film: dict[str, Any], packet: Any) -> None:
    print("\n" + "=" * 88)
    print(f"CASE: {case_id}")
    print(
        f"FILM: {film.get('title')} ({film.get('year')}) · "
        f"{', '.join(film.get('directors') or film.get('credits', {}).get('directors') or [])}"
    )
    print(f"FOCUS: {packet.focus}")
    print("=" * 88)
    print("\nTHEORY FRAMEWORKS")
    for item in packet.theory_sources:
        print(f"\n[{item.evidence_id}] {item.title} · {item.locator} · {item.language}")
        print(item.content)
    print("\nATTRIBUTED SOURCES")
    if not packet.attributed_sources:
        print("(none selected)")
    for item in packet.attributed_sources:
        print(
            f"\n[{item.evidence_id}] {item.evidence_type} · {item.title} · "
            f"{item.locator} · {item.language}"
        )
        print(f"Source: {item.source_url or 'private/local locator only'}")
        print(item.content)
    print("\nCRITIC CLAIMS")
    if not packet.critical_claims:
        print("(none selected)")
    for claim in packet.critical_claims:
        print(f"\n[{claim.claim_id}] source {claim.source_id}")
        print(claim.critic_claim)
    print("\nEPISTEMIC BOUNDARIES")
    for boundary in packet.boundaries:
        print(f"- {boundary}")
    print("\nSELECTION MANIFESTS (aggregate only)")
    for key in ("theory_selection", "critical_selection", "attributed_selection"):
        print(f"- {key}: {json.dumps(packet.retrieval.get(key, {}), ensure_ascii=False)}")


def ask_score(dimension: str) -> int:
    while True:
        raw = input(f"{dimension.replace('_', ' ').title()} [1–5]: ").strip()
        if raw.casefold() in {"q", "quit"}:
            raise KeyboardInterrupt
        try:
            score = int(raw)
        except ValueError:
            score = 0
        if 1 <= score <= 5:
            return score
        print("Enter a whole number from 1 to 5, or q to stop and resume later.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review private FirstRoll evidence packets locally using the human rubric."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--private-output", type=Path, default=DEFAULT_PRIVATE_OUTPUT)
    parser.add_argument("--redacted-output", type=Path, default=DEFAULT_REDACTED_OUTPUT)
    parser.add_argument("--case", action="append", dest="case_ids")
    return parser.parse_args()


def main_cli() -> int:
    configure_input_encoding()
    args = parse_args()
    from app.backend import main
    from app.backend.packet_quality import assess_evidence_packet
    from app.backend.study_observability import StudyTrace

    specs = load_case_specs(args.cases, args.reference)
    if args.case_ids:
        requested = set(args.case_ids)
        specs = [item for item in specs if item["case_id"] in requested]
        missing = requested - {item["case_id"] for item in specs}
        if missing:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing))}")
    review = {
        "schema_version": 1,
        "suite_id": "firstroll-human-packet-review-private-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": source_revision(),
        "reviewer_attested": False,
        "cases": [],
    }
    if args.private_output.is_file():
        review = json.loads(args.private_output.read_text(encoding="utf-8"))
        if review.get("source_revision") != source_revision():
            raise SystemExit(
                "The saved review belongs to another revision. Move it aside and start a fresh "
                "review for the current packet selection."
            )
    completed = {item["case_id"] for item in review.get("cases", [])}
    main.library_index.wait_for_embedding_warmup(timeout=300)

    try:
        for spec in specs:
            if spec["case_id"] in completed:
                continue
            film = main.discovery_service.detail(spec["film_id"])["film"]
            trace = StudyTrace()
            trace.skip("film_context")
            prepared = main.prepare_film_study(
                spec["film_id"],
                film,
                spec["focus"],
                public_mode=False,
                trace=trace,
            )
            packet = prepared["packet"]
            display_packet(spec["case_id"], film, packet)
            quality = assess_evidence_packet(packet)
            print("\nAUTOMATED PACKET DIAGNOSTIC (not your score)")
            print(json.dumps(quality, ensure_ascii=False, indent=2))
            print("\nHUMAN RUBRIC")
            print(
                "Use 1 for a clear failure, 3 for useful evidence with material gaps, and 5 "
                "for strong performance throughout. A passing case needs at least 4 for "
                "relevance, traceability and actionability, with no dimension below 3."
            )
            scores = {}
            for dimension in RUBRIC_DIMENSIONS:
                print(f"\n{RUBRIC_QUESTIONS[dimension]}")
                scores[dimension] = ask_score(dimension)
            note = input("Optional private reviewer note (not included in redacted output): ").strip()
            review.setdefault("cases", []).append(
                {"case_id": spec["case_id"], "scores": scores, "private_note": note}
            )
            write_private(args.private_output, review)
    except (KeyboardInterrupt, EOFError):
        write_private(args.private_output, review)
        print(f"\nReview saved for later: {args.private_output}")
        return 2

    expected_ids = {item["case_id"] for item in load_case_specs(args.cases, args.reference)}
    reviewed_ids = {item["case_id"] for item in review.get("cases", [])}
    if expected_ids != reviewed_ids:
        print("The selected subset is saved, but all five cases are required before attestation.")
        write_private(args.private_output, review)
        return 2
    attestation = input(
        "\nType YES to attest that you personally inspected all five packet evidence sets: "
    ).strip()
    review["reviewer_attested"] = attestation == "YES"
    review["recorded_at"] = datetime.now(timezone.utc).isoformat()
    write_private(args.private_output, review)
    if not review["reviewer_attested"]:
        print("Attestation was not recorded; no redacted gate result was written.")
        return 2
    redacted = aggregate_review(review)
    write_private(args.redacted_output, redacted)
    print(json.dumps(redacted["summary"], indent=2))
    print(f"Private review: {args.private_output}")
    print(f"Redacted gate result: {args.redacted_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
