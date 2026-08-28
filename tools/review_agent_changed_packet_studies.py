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
from app.backend.study_service import GroundedStudy
from tools.review_evidence_packets import (
    configure_input_encoding,
    display_packet,
    source_revision,
    write_private,
)


PROGRAMME_ID = "firstroll-autonomous-research-agent-v1"
DEFAULT_STUDIES = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-changed-packet-studies.json"
)
DEFAULT_PRIVATE_REVIEW = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-changed-packet-review.json"
)
DEFAULT_REDACTED_REVIEW = (
    ROOT / ".firstroll" / "evaluations" / "autonomous-agent-changed-packet-review-redacted.json"
)
EXPECTED_REPETITIONS = {1, 5, 10}


def require_private_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(
            "Autonomous changed-study review files must stay under .firstroll."
        ) from exc
    if not relative.parts or relative.parts[0] != ".firstroll":
        raise ValueError("Autonomous changed-study review files must stay under .firstroll.")
    return resolved


def load_private_studies(path: Path) -> dict[str, Any]:
    resolved = require_private_path(path)
    if not resolved.is_file():
        raise FileNotFoundError("No machine-gated changed-study snapshot exists.")
    if stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise PermissionError("The private changed-study snapshot must use mode 0600.")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if payload.get("programme_id") != PROGRAMME_ID or payload.get("experiment_id") != "A03":
        raise ValueError("The changed-study snapshot belongs to another experiment.")
    if (
        not str(payload.get("source_revision") or "").strip()
        or not str(payload.get("suite_fingerprint") or "").strip()
    ):
        raise ValueError("The changed-study snapshot is not bound to a revision and suite.")
    pairs = payload.get("pairs")
    if (
        not isinstance(pairs, list)
        or len(pairs) != len(EXPECTED_REPETITIONS)
        or {int(pair.get("repetition", 0)) for pair in pairs if isinstance(pair, dict)}
        != EXPECTED_REPETITIONS
    ):
        raise ValueError("The changed-study snapshot lacks the frozen blinded repetitions.")
    for pair in pairs:
        mapping = pair.get("blind_mapping")
        studies = pair.get("studies")
        if (
            not isinstance(mapping, dict)
            or set(mapping) != {"A", "B"}
            or set(mapping.values()) != {"fixed", "candidate"}
            or not isinstance(studies, list)
            or len(studies) != 2
        ):
            raise ValueError("A changed-study pair has an invalid blind mapping.")
        seen = set()
        for item in studies:
            blind_id = str(item.get("blind_id") or "") if isinstance(item, dict) else ""
            if blind_id not in mapping or blind_id in seen:
                raise ValueError("A changed-study pair has invalid blind labels.")
            seen.add(blind_id)
            GroundedStudy.model_validate(item.get("study"))
            EvidencePacket.model_validate(item.get("packet"))
        if seen != set(mapping):
            raise ValueError("A changed-study pair is incomplete.")
    return cast(dict[str, Any], payload)


def display_study(blind_id: str, study: GroundedStudy) -> None:
    print("\n" + "=" * 80)
    print(f"BLIND STUDY {blind_id} — {study.title}")
    print("=" * 80)
    print(f"\nCentral argument\n{study.central_argument}")
    for index, section in enumerate(study.sections, 1):
        print(f"\n[{index}] {section.lens}")
        if section.critic_reports:
            print(f"Critic reports: {section.critic_reports}")
        print(f"Theory explains: {section.theory_explains}")
        print(f"Hypothesis: {section.hypothesis}")
        print(f"Mechanism: {section.mechanism}")
        if section.alternative_reading:
            print(f"Alternative: {section.alternative_reading}")
        print(f"Verify: {section.verify}")
        print(
            "Citations: "
            + ", ".join(
                [
                    *section.source_ids,
                    *section.critic_claim_ids,
                    *section.attributed_source_ids,
                ]
            )
        )
    print(f"\nCreator-intent boundary\n{study.creator_intent_boundary}")
    print("\nNext viewing")
    for item in study.next_viewing:
        print(f"- {item}")


def ask_choice(prompt: str, choices: set[str]) -> str:
    while True:
        value = input(prompt).strip().upper()
        if value in choices:
            return value
        print(f"Enter one of: {', '.join(sorted(choices))}.")


def aggregate_review(review: dict[str, Any], studies: dict[str, Any]) -> dict[str, Any]:
    mapping_by_repetition = {
        int(pair["repetition"]): pair["blind_mapping"] for pair in studies["pairs"]
    }
    reviews = review.get("pairs", [])
    if (
        len(reviews) != len(EXPECTED_REPETITIONS)
        or {int(item.get("repetition", 0)) for item in reviews} != EXPECTED_REPETITIONS
    ):
        raise ValueError("Every frozen study pair must have one human decision.")

    pairs = []
    candidate_usefulness_wins = 0
    candidate_evidence_losses = 0
    candidate_severe_concerns = 0
    for item in reviews:
        repetition = int(item["repetition"])
        mapping = mapping_by_repetition[repetition]

        def lane_for(choice: str) -> str:
            if choice not in {"A", "B", "TIE"}:
                raise ValueError("A blinded preference has an invalid choice.")
            return "tie" if choice == "TIE" else str(mapping[choice])

        usefulness = lane_for(str(item["usefulness_preference"]))
        evidence = lane_for(str(item["evidence_responsibility_preference"]))
        if set(item.get("severe_grounding_concern", {})) != {"A", "B"}:
            raise ValueError("A blinded grounding decision is incomplete.")
        severe = {
            str(mapping[blind_id]): bool(value)
            for blind_id, value in item["severe_grounding_concern"].items()
        }
        candidate_usefulness_wins += int(usefulness == "candidate")
        candidate_evidence_losses += int(evidence == "fixed")
        candidate_severe_concerns += int(severe["candidate"])
        pairs.append(
            {
                "repetition": repetition,
                "usefulness_preference": usefulness,
                "evidence_responsibility_preference": evidence,
                "severe_grounding_concern": severe,
            }
        )
    attested = review.get("reviewer_attested") is True
    passed = bool(
        attested
        and candidate_usefulness_wins >= 2
        and candidate_evidence_losses == 0
        and candidate_severe_concerns == 0
    )
    return {
        "schema_version": 1,
        "programme_id": PROGRAMME_ID,
        "experiment_id": "A03",
        "recorded_at": review.get("recorded_at"),
        "source_revision": studies.get("source_revision"),
        "suite_fingerprint": studies.get("suite_fingerprint"),
        "reviewer_attested": attested,
        "quality_scope": (
            "Owner preferences for three predeclared blinded fixed/candidate study pairs; no study "
            "text, packet text or reviewer notes."
        ),
        "pairs": sorted(pairs, key=lambda item: item["repetition"]),
        "summary": {
            "candidate_usefulness_preferred_pairs": candidate_usefulness_wins,
            "candidate_evidence_responsibility_losses": candidate_evidence_losses,
            "candidate_severe_grounding_concerns": candidate_severe_concerns,
            "human_gate_passed": passed,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review three changed-packet study pairs privately and blind to lane identity."
    )
    parser.add_argument("--studies", type=Path, default=DEFAULT_STUDIES)
    parser.add_argument("--private-output", type=Path, default=DEFAULT_PRIVATE_REVIEW)
    parser.add_argument("--redacted-output", type=Path, default=DEFAULT_REDACTED_REVIEW)
    return parser.parse_args()


def main_cli() -> int:
    configure_input_encoding()
    args = parse_args()
    studies = load_private_studies(args.studies)
    private_output = require_private_path(args.private_output)
    redacted_output = require_private_path(args.redacted_output)
    revision = str(studies["source_revision"])
    if revision != source_revision():
        raise SystemExit(
            "The changed-study snapshot belongs to another revision; review that exact checkpoint."
        )
    review: dict[str, Any] = {
        "schema_version": 1,
        "programme_id": PROGRAMME_ID,
        "experiment_id": "A03",
        "source_revision": revision,
        "suite_fingerprint": studies["suite_fingerprint"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_attested": False,
        "pairs": [],
    }
    if private_output.is_file():
        review = json.loads(private_output.read_text(encoding="utf-8"))
        if (
            review.get("source_revision") != revision
            or review.get("suite_fingerprint") != studies["suite_fingerprint"]
        ):
            raise SystemExit("The saved review belongs to another revision or suite.")
    completed = {int(item["repetition"]) for item in review.get("pairs", [])}

    try:
        for pair in sorted(studies["pairs"], key=lambda item: item["repetition"]):
            repetition = int(pair["repetition"])
            if repetition in completed:
                continue
            print(f"\n{'#' * 80}\nBLINDED PAIR — REPETITION {repetition}\n{'#' * 80}")
            for item in sorted(pair["studies"], key=lambda value: value["blind_id"]):
                packet = EvidencePacket.model_validate(item["packet"])
                display_packet(
                    f"Blind packet {item['blind_id']}",
                    packet.film_record,
                    packet,
                )
                display_study(
                    str(item["blind_id"]),
                    GroundedStudy.model_validate(item["study"]),
                )
            usefulness = ask_choice(
                "\nWhich study is more useful to a filmmaker? A / B / TIE: ",
                {"A", "B", "TIE"},
            )
            evidence = ask_choice(
                "Which study uses its evidence more responsibly? A / B / TIE: ",
                {"A", "B", "TIE"},
            )
            severe = {
                blind_id: ask_choice(
                    f"Does study {blind_id} contain a severe unsupported or overstated claim? YES / NO: ",
                    {"YES", "NO"},
                )
                == "YES"
                for blind_id in ("A", "B")
            }
            note = input("Optional private note (excluded from aggregate): ").strip()
            review.setdefault("pairs", []).append(
                {
                    "repetition": repetition,
                    "usefulness_preference": usefulness,
                    "evidence_responsibility_preference": evidence,
                    "severe_grounding_concern": severe,
                    "private_note": note,
                }
            )
            write_private(private_output, review)
    except (KeyboardInterrupt, EOFError):
        write_private(private_output, review)
        print(f"\nReview saved for later: {private_output}")
        return 2

    if {int(item["repetition"]) for item in review.get("pairs", [])} != EXPECTED_REPETITIONS:
        write_private(private_output, review)
        print("Every frozen pair must be reviewed before attestation.")
        return 2
    attestation = input(
        "\nType YES to attest that you personally inspected all three blinded study pairs: "
    ).strip()
    review["reviewer_attested"] = attestation == "YES"
    review["recorded_at"] = datetime.now(timezone.utc).isoformat()
    write_private(private_output, review)
    if not review["reviewer_attested"]:
        print("Attestation was not recorded; no redacted aggregate was written.")
        return 2
    redacted = aggregate_review(review, studies)
    write_private(redacted_output, redacted)
    print(json.dumps(redacted["summary"], indent=2))
    print("Lane identities were revealed only after attestation in the score-only aggregate.")
    print(f"Private review: {private_output}")
    print(f"Redacted aggregate: {redacted_output}")
    return 0 if redacted["summary"]["human_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main_cli())
