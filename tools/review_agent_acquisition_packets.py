from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import stat
import sys
from typing import Any, cast


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


PROGRAMME_ID = "firstroll-autonomous-research-agent-v1"
SUPPORTED_EXPERIMENT_IDS = {"A01", "A01R"}
EXPECTED_LANES = {
    "fixed_no_acquisition",
    "deterministic_gap_router",
    "model_gap_planner",
}
DEFAULT_PACKETS = ROOT / ".firstroll" / "evaluations" / "autonomous-agent-acquisition-packets.json"
DEFAULT_PRIVATE_REVIEW = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-acquisition-review.json"
)
DEFAULT_REDACTED_REVIEW = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-acquisition-review-redacted.json"
)


def require_private_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Autonomous-Agent review files must stay under .firstroll.") from exc
    if not relative.parts or relative.parts[0] != ".firstroll":
        raise ValueError("Autonomous-Agent review files must stay under .firstroll.")
    return resolved


def load_private_packets(path: Path) -> dict[str, Any]:
    resolved = require_private_path(path)
    if not resolved.is_file():
        raise FileNotFoundError("No machine-gated autonomous acquisition snapshot exists.")
    if stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise PermissionError("The private acquisition snapshot must use mode 0600.")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if (
        payload.get("programme_id") != PROGRAMME_ID
        or payload.get("experiment_id") not in SUPPORTED_EXPERIMENT_IDS
    ):
        raise ValueError("The packet snapshot belongs to another experiment.")
    if (
        not str(payload.get("source_revision") or "").strip()
        or not str(payload.get("suite_fingerprint") or "").strip()
    ):
        raise ValueError("The packet snapshot is not bound to a revision and suite.")

    mapping = payload.get("blind_mapping")
    packets = payload.get("packets")
    lane_metrics = payload.get("lane_metrics")
    if (
        not isinstance(mapping, dict)
        or set(mapping.values()) != EXPECTED_LANES
        or not isinstance(packets, list)
        or len(packets) != len(EXPECTED_LANES)
        or not isinstance(lane_metrics, dict)
        or set(lane_metrics) != EXPECTED_LANES
    ):
        raise ValueError("The blinded acquisition snapshot is incomplete.")
    seen: set[str] = set()
    for item in packets:
        blind_id = str(item.get("blind_id") or "") if isinstance(item, dict) else ""
        if blind_id not in mapping or blind_id in seen or not isinstance(item.get("packet"), dict):
            raise ValueError("The blinded acquisition snapshot contains an invalid packet.")
        seen.add(blind_id)
        EvidencePacket.model_validate(item["packet"])
    if seen != set(mapping):
        raise ValueError("The blinded packet labels do not match their private mapping.")
    return cast(dict[str, Any], payload)


def aggregate_review(review: dict[str, Any], packets: dict[str, Any]) -> dict[str, Any]:
    by_blind_id = {
        str(item.get("blind_id") or ""): {
            dimension: int(item.get("scores", {}).get(dimension, 0))
            for dimension in RUBRIC_DIMENSIONS
        }
        for item in review.get("packets", [])
    }
    if len(review.get("packets", [])) != len(by_blind_id) or set(by_blind_id) != set(
        packets["blind_mapping"]
    ):
        raise ValueError("Every blinded packet must have exactly one complete human score.")
    by_lane = {lane: by_blind_id[blind_id] for blind_id, lane in packets["blind_mapping"].items()}
    lane_results = {}
    for lane, scores in by_lane.items():
        lane_results[lane] = {
            "scores": scores,
            "total_score": sum(scores.values()),
            "passed_packet_rubric": case_passes(scores),
            "external_tool_calls": int(packets["lane_metrics"][lane].get("external_tool_calls", 0)),
            "model_planner_calls": int(packets["lane_metrics"][lane].get("model_planner_calls", 0)),
        }

    model = lane_results["model_gap_planner"]
    deterministic = lane_results["deterministic_gap_router"]
    model_not_below_primary = bool(
        model["scores"]["source_diversity"] >= deterministic["scores"]["source_diversity"]
        and model["scores"]["filmmaker_actionability"]
        >= deterministic["scores"]["filmmaker_actionability"]
    )
    model_beats_or_is_more_efficient = bool(
        model["total_score"] > deterministic["total_score"]
        or (
            model["total_score"] == deterministic["total_score"]
            and model["external_tool_calls"] < deterministic["external_tool_calls"]
        )
    )
    reviewer_attested = review.get("reviewer_attested") is True
    model_value_demonstrated = bool(
        reviewer_attested
        and model["passed_packet_rubric"]
        and model_not_below_primary
        and model_beats_or_is_more_efficient
    )
    return {
        "schema_version": 1,
        "programme_id": PROGRAMME_ID,
        "experiment_id": packets["experiment_id"],
        "recorded_at": review.get("recorded_at"),
        "source_revision": packets.get("source_revision"),
        "suite_fingerprint": packets.get("suite_fingerprint"),
        "reviewer_attested": reviewer_attested,
        "quality_scope": (
            "Owner scores for three blinded acquisition packets; no source text, lane labels shown "
            "during review or reviewer notes."
        ),
        "lanes": lane_results,
        "summary": {
            "model_packet_passed_rubric": model["passed_packet_rubric"],
            "model_primary_scores_not_below_deterministic": model_not_below_primary,
            "model_beats_or_is_more_efficient_than_deterministic": (
                model_beats_or_is_more_efficient
            ),
            "model_planner_value_demonstrated": model_value_demonstrated,
            "advancement": "advance_A02" if model_value_demonstrated else "prefer_deterministic",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review autonomous acquisition packets privately and blind to lane identity."
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
    revision = str(packets["source_revision"])
    if revision != source_revision():
        raise SystemExit(
            "The acquisition snapshot belongs to another revision; review that exact checkpoint."
        )

    review: dict[str, Any] = {
        "schema_version": 1,
        "programme_id": PROGRAMME_ID,
        "experiment_id": packets["experiment_id"],
        "source_revision": revision,
        "suite_fingerprint": packets["suite_fingerprint"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_attested": False,
        "packets": [],
    }
    if private_output.is_file():
        review = json.loads(private_output.read_text(encoding="utf-8"))
        if (
            review.get("experiment_id") != packets["experiment_id"]
            or review.get("source_revision") != revision
            or review.get("suite_fingerprint") != packets["suite_fingerprint"]
        ):
            raise SystemExit("The saved review belongs to another revision or suite.")
    completed = {str(item.get("blind_id") or "") for item in review.get("packets", [])}

    try:
        for item in packets["packets"]:
            blind_id = str(item["blind_id"])
            if blind_id in completed:
                continue
            packet = EvidencePacket.model_validate(item["packet"])
            display_packet(f"Blind packet {blind_id}", packet.film_record, packet)
            print("\nHUMAN RUBRIC — BLINDED AUTONOMOUS ACQUISITION PACKET")
            print(
                "Lane identity is hidden. A packet pass needs at least 4 for relevance, "
                "traceability and actionability, with no dimension below 3."
            )
            scores = {}
            for dimension in RUBRIC_DIMENSIONS:
                print(f"\n{RUBRIC_QUESTIONS[dimension]}")
                scores[dimension] = ask_score(dimension)
            note = input("Optional private note (excluded from the aggregate): ").strip()
            review.setdefault("packets", []).append(
                {"blind_id": blind_id, "scores": scores, "private_note": note}
            )
            write_private(private_output, review)
    except (KeyboardInterrupt, EOFError):
        write_private(private_output, review)
        print(f"\nReview saved for later: {private_output}")
        return 2

    expected = {str(item["blind_id"]) for item in packets["packets"]}
    completed = {str(item.get("blind_id") or "") for item in review.get("packets", [])}
    if completed != expected:
        write_private(private_output, review)
        print("Every blinded packet must be reviewed before attestation.")
        return 2
    attestation = input(
        "\nType YES to attest that you personally inspected all three blinded packets: "
    ).strip()
    review["reviewer_attested"] = attestation == "YES"
    review["recorded_at"] = datetime.now(timezone.utc).isoformat()
    write_private(private_output, review)
    if not review["reviewer_attested"]:
        print("Attestation was not recorded; no redacted aggregate was written.")
        return 2

    redacted = aggregate_review(review, packets)
    write_private(redacted_output, redacted)
    print(json.dumps(redacted["summary"], indent=2))
    print("Lane mapping was revealed only after attestation in the redacted score aggregate.")
    print(f"Private review: {private_output}")
    print(f"Redacted aggregate: {redacted_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
