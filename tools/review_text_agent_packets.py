from __future__ import annotations

import argparse
import json
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.evidence import EvidencePacket
from tools.review_evidence_packets import (
    RUBRIC_DIMENSIONS,
    RUBRIC_QUESTIONS,
    ask_score,
    case_passes,
    configure_input_encoding,
    display_packet,
    source_revision,
    write_private,
)


DEFAULT_PACKETS = ROOT / ".firstroll" / "evaluations" / "text-agent-packets.json"
DEFAULT_PRIVATE_REVIEW = ROOT / ".firstroll" / "evaluations" / "text-agent-human-review.json"
DEFAULT_REDACTED_REVIEW = (
    ROOT / ".firstroll" / "evaluations" / "text-agent-human-review-redacted.json"
)


def require_private_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Text-Agent review files must stay under .firstroll.") from exc
    if not relative.parts or relative.parts[0] != ".firstroll":
        raise ValueError("Text-Agent review files must stay under .firstroll.")
    return resolved


def load_private_packets(path: Path) -> dict[str, Any]:
    resolved = require_private_path(path)
    if not resolved.is_file():
        raise FileNotFoundError("No machine-gated text-Agent packet snapshot exists for review.")
    if stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise PermissionError("The private packet snapshot must use mode 0600.")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if payload.get("programme_id") != "firstroll-text-agent-v1":
        raise ValueError("The packet snapshot belongs to another programme.")
    if (
        not str(payload.get("source_revision") or "").strip()
        or not str(payload.get("suite_fingerprint") or "").strip()
    ):
        raise ValueError("The packet snapshot is not bound to a revision and suite.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("The packet snapshot contains no changed Agent packet.")
    seen: set[str] = set()
    for item in cases:
        case_id = str(item.get("case_id") or "") if isinstance(item, dict) else ""
        if not case_id or case_id in seen or not isinstance(item.get("packet"), dict):
            raise ValueError("The packet snapshot has an invalid or duplicate case.")
        seen.add(case_id)
        EvidencePacket.model_validate(item["packet"])
    return payload


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
    passed = sum(item["passed"] for item in cases)
    return {
        "schema_version": 1,
        "programme_id": "firstroll-text-agent-v1",
        "suite_id": "firstroll-text-agent-changed-packet-review-v1",
        "recorded_at": review.get("recorded_at"),
        "source_revision": review.get("source_revision"),
        "suite_fingerprint": review.get("suite_fingerprint"),
        "reviewer_attested": review.get("reviewer_attested") is True,
        "quality_scope": (
            "Human review of machine-gated changed Agent packets; no evidence text or "
            "reviewer notes."
        ),
        "summary": {
            "case_count": len(cases),
            "passed_cases": passed,
            "failed_cases": len(cases) - passed,
            "pass_ratio": round(passed / len(cases), 4) if cases else 0.0,
        },
        "cases": cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review changed text-Agent packets privately after all machine gates pass."
    )
    parser.add_argument("--packets", type=Path, default=DEFAULT_PACKETS)
    parser.add_argument("--private-output", type=Path, default=DEFAULT_PRIVATE_REVIEW)
    parser.add_argument("--redacted-output", type=Path, default=DEFAULT_REDACTED_REVIEW)
    return parser.parse_args()


def main_cli() -> int:
    configure_input_encoding()
    args = parse_args()
    packets = load_private_packets(args.packets)
    private_output = require_private_path(args.private_output)
    redacted_output = require_private_path(args.redacted_output)
    revision = str(packets.get("source_revision") or "")
    if revision != source_revision():
        raise SystemExit(
            "The packet snapshot belongs to another revision; review it from that exact checkpoint."
        )
    review: dict[str, Any] = {
        "schema_version": 1,
        "programme_id": "firstroll-text-agent-v1",
        "source_revision": revision,
        "suite_fingerprint": packets.get("suite_fingerprint"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_attested": False,
        "cases": [],
    }
    if private_output.is_file():
        review = json.loads(private_output.read_text(encoding="utf-8"))
        if review.get("source_revision") != revision or review.get(
            "suite_fingerprint"
        ) != packets.get("suite_fingerprint"):
            raise SystemExit("The saved human review belongs to another revision or suite.")
    completed = {str(item.get("case_id") or "") for item in review.get("cases", [])}

    try:
        for item in packets["cases"]:
            case_id = str(item["case_id"])
            if case_id in completed:
                continue
            packet = EvidencePacket.model_validate(item["packet"])
            display_packet(case_id, packet.film_record, packet)
            print("\nHUMAN RUBRIC — AGENT-CHANGED PACKET")
            print(
                "A pass needs at least 4 for relevance, traceability and actionability, "
                "with no dimension below 3. Rate the evidence you personally inspected."
            )
            scores = {}
            for dimension in RUBRIC_DIMENSIONS:
                print(f"\n{RUBRIC_QUESTIONS[dimension]}")
                scores[dimension] = ask_score(dimension)
            note = input("Optional private reviewer note (excluded from the aggregate): ").strip()
            review.setdefault("cases", []).append(
                {"case_id": case_id, "scores": scores, "private_note": note}
            )
            write_private(private_output, review)
    except (KeyboardInterrupt, EOFError):
        write_private(private_output, review)
        print(f"\nReview saved for later: {private_output}")
        return 2

    expected = {str(item["case_id"]) for item in packets["cases"]}
    completed = {str(item.get("case_id") or "") for item in review.get("cases", [])}
    if completed != expected:
        write_private(private_output, review)
        print("Every changed packet must be reviewed before attestation.")
        return 2
    attestation = input(
        "\nType YES to attest that you personally inspected every changed Agent packet: "
    ).strip()
    review["reviewer_attested"] = attestation == "YES"
    review["recorded_at"] = datetime.now(timezone.utc).isoformat()
    write_private(private_output, review)
    if not review["reviewer_attested"]:
        print("Attestation was not recorded; no redacted aggregate was written.")
        return 2
    redacted = aggregate_review(review)
    write_private(redacted_output, redacted)
    print(json.dumps(redacted["summary"], indent=2))
    print(f"Private review: {private_output}")
    print(f"Redacted aggregate: {redacted_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
