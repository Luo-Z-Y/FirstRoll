from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.backend.evidence import EvidencePacket


ClaimSupportLabel = Literal[
    "directly_supported",
    "reasonable_interpretation",
    "unsupported",
    "stronger_than_evidence",
]
CoachAction = Literal["log", "compare", "count", "track", "mark", "inspect"]
WEAK_CLAIM_LABELS = frozenset({"unsupported", "stronger_than_evidence"})


class ClaimAuditItem(BaseModel):
    """One concise support judgement, never hidden chain-of-thought."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=3, max_length=100)
    label: ClaimSupportLabel
    source_ids: list[str] = Field(min_length=1, max_length=12)
    support_note: str = Field(min_length=20, max_length=320)


class StudyClaimAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClaimAuditItem] = Field(min_length=1, max_length=40)


class FilmmakerExercise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=4, max_length=120)
    action: CoachAction
    instruction: str = Field(min_length=40, max_length=600)
    study_path: str = Field(min_length=3, max_length=100)
    source_ids: list[str] = Field(min_length=1, max_length=8)
    success_signal: str = Field(min_length=20, max_length=300)
    uncertainty_boundary: str = Field(min_length=30, max_length=360)


class FilmmakerCoach(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercises: list[FilmmakerExercise] = Field(min_length=3, max_length=6)


def grounded_study_payload(study: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "title",
        "central_argument",
        "sections",
        "creator_intent_boundary",
        "next_viewing",
    }
    return {key: study[key] for key in fields if key in study}


def audited_claim_paths(study: dict[str, Any]) -> tuple[str, ...]:
    paths = ["central_argument"]
    sections = study.get("sections")
    if not isinstance(sections, list):
        return tuple(paths)
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        for field in (
            "critic_reports",
            "theory_explains",
            "hypothesis",
            "mechanism",
            "alternative_reading",
        ):
            if section.get(field):
                paths.append(f"sections.{index}.{field}")
    return tuple(paths)


def path_source_ids(study: dict[str, Any], path: str) -> set[str]:
    sections = study.get("sections")
    if path == "central_argument":
        if not isinstance(sections, list):
            return set()
        return {
            str(source_id)
            for section in sections
            if isinstance(section, dict)
            for field in ("source_ids", "critic_claim_ids", "attributed_source_ids")
            for source_id in section.get(field, [])
        }
    parts = path.split(".")
    if (
        len(parts) != 3
        or parts[0] != "sections"
        or not parts[1].isdigit()
        or not isinstance(sections, list)
        or int(parts[1]) >= len(sections)
        or not isinstance(sections[int(parts[1])], dict)
    ):
        return set()
    section = sections[int(parts[1])]
    return {
        str(source_id)
        for field in ("source_ids", "critic_claim_ids", "attributed_source_ids")
        for source_id in section.get(field, [])
    }


def packet_source_ids(packet: EvidencePacket) -> set[str]:
    return {
        *(item.evidence_id for item in packet.theory_sources),
        *(item.evidence_id for item in packet.attributed_sources),
        *(item.claim_id for item in packet.critical_claims),
    }


def validate_claim_audit(
    study: dict[str, Any],
    audit: StudyClaimAudit,
    packet: EvidencePacket,
) -> None:
    expected = set(audited_claim_paths(study))
    observed = [item.path for item in audit.items]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError("The claim audit must cover every required study path exactly once.")
    packet_ids = packet_source_ids(packet)
    for item in audit.items:
        allowed = path_source_ids(study, item.path)
        supplied = set(item.source_ids)
        if not supplied <= packet_ids or not supplied <= allowed:
            raise ValueError("The claim audit cited evidence outside the audited study path.")
        field = item.path.rsplit(".", 1)[-1]
        if field == "critic_reports" and not any(
            source_id.startswith(("C", "E")) for source_id in supplied
        ):
            raise ValueError("A critic report must cite criticism or attributed evidence.")
        if field == "theory_explains" and not any(
            source_id.startswith("S") for source_id in supplied
        ):
            raise ValueError("A theory explanation must cite a theory source.")
        if field in {"hypothesis", "alternative_reading", "central_argument"} and item.label == (
            "directly_supported"
        ):
            raise ValueError("An interpretive study claim cannot be labelled directly supported.")


def weak_claim_paths(audit: StudyClaimAudit) -> tuple[str, ...]:
    return tuple(item.path for item in audit.items if item.label in WEAK_CLAIM_LABELS)


def validate_filmmaker_coach(
    study: dict[str, Any],
    audit: StudyClaimAudit,
    coach: FilmmakerCoach,
    packet: EvidencePacket,
) -> None:
    audit_by_path = {item.path: item for item in audit.items}
    packet_ids = packet_source_ids(packet)
    paths = [exercise.study_path for exercise in coach.exercises]
    if len(paths) != len(set(paths)):
        raise ValueError("Filmmaker exercises must use distinct accepted study paths.")
    for exercise in coach.exercises:
        audited = audit_by_path.get(exercise.study_path)
        if audited is None or audited.label in WEAK_CLAIM_LABELS:
            raise ValueError("A filmmaker exercise cannot rely on an unaudited or weak claim.")
        allowed = path_source_ids(study, exercise.study_path)
        supplied = set(exercise.source_ids)
        if not supplied <= packet_ids or not supplied <= allowed:
            raise ValueError("A filmmaker exercise cited evidence outside its accepted claim.")
        if not re.search(
            rf"\b{re.escape(exercise.action)}\b",
            exercise.instruction.casefold(),
        ):
            raise ValueError("The exercise instruction must state its observable action.")
        boundary = exercise.uncertainty_boundary.casefold()
        if not any(
            term in boundary for term in ("hypothesis", "interpretation", "uncertain")
        ) or not any(term in boundary for term in ("not ", "does not", "cannot")):
            raise ValueError("The exercise must retain an explicit uncertainty boundary.")
