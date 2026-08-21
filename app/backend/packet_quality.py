from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlparse

from app.backend.evidence import EvidenceItem, EvidencePacket


BLOCKING_PACKET_ISSUES = frozenset(
    {
        "citation_ids_invalid",
        "film_identity_incomplete",
        "film_identity_mismatch",
        "instruction_containment_missing",
        "theory_evidence_missing",
    }
)
PACKET_ISSUES = frozenset(
    {
        *BLOCKING_PACKET_ISSUES,
        "attributed_items_omitted",
        "duplicate_evidence_present",
        "film_specific_evidence_sparse",
        "focus_relevance_low",
        "provenance_incomplete",
        "single_evidence_class",
        "unknown_evidence_language",
    }
)
INSTRUCTION_PATTERNS = (
    re.compile(r"\b(?:ignore|disregard|override)\b.{0,80}\b(?:instruction|policy|prompt|system)\b", re.I),
    re.compile(r"\b(?:reveal|return|print|expose)\b.{0,60}\b(?:api key|credential|prompt|secret)\b", re.I),
    re.compile(r"\b(?:call|invoke|authorise|authorize)\b.{0,40}\b(?:api|tool|function)\b", re.I),
    re.compile(r"<\s*script\b", re.I),
)
WORD_PATTERN = re.compile(r"[\u3400-\u9fff]|[a-z0-9][a-z0-9'-]{2,}", re.I)
LANGUAGE_PATTERN = re.compile(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", re.I)
STOP_WORDS = frozenset(
    {
        "about",
        "against",
        "available",
        "create",
        "film",
        "formal",
        "from",
        "into",
        "should",
        "study",
        "that",
        "the",
        "their",
        "these",
        "this",
        "through",
        "viewing",
        "what",
        "when",
        "where",
        "whether",
        "with",
        "without",
    }
)


def normalise_identity(value: Any) -> str:
    return re.sub(r"[\W_]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def content_tokens(value: Any) -> set[str]:
    return {
        token.casefold()
        for token in WORD_PATTERN.findall(str(value or ""))
        if token.casefold() not in STOP_WORDS
    }


def safe_language(value: Any) -> str:
    language = str(value or "und").strip().casefold()
    return language if LANGUAGE_PATTERN.fullmatch(language) else "und"


def safe_http_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or ""))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def item_has_complete_provenance(item: EvidenceItem) -> bool:
    common = bool(
        item.evidence_id.strip()
        and item.title.strip()
        and item.content.strip()
        and str(item.locator or "").strip()
        and safe_language(item.language) != "und"
    )
    if not common:
        return False
    if item.evidence_type in {"critic_reported", "creator_stated", "film_observed"}:
        return safe_http_url(item.source_url)
    return True


def duplicate_item_count(items: list[EvidenceItem]) -> int:
    duplicates = 0
    prior: list[tuple[str, str, set[str]]] = []
    for item in items:
        normalised = re.sub(r"\s+", " ", item.content.casefold()).strip()
        tokens = content_tokens(normalised)
        duplicate = False
        for prior_type, prior_text, prior_tokens in prior:
            if normalised == prior_text:
                duplicate = True
                break
            if item.evidence_type == prior_type and tokens and prior_tokens:
                overlap = len(tokens & prior_tokens) / max(1, len(tokens | prior_tokens))
                if overlap >= 0.92:
                    duplicate = True
                    break
        duplicates += int(duplicate)
        prior.append((item.evidence_type, normalised, tokens))
    return duplicates


def instruction_item_count(items: Iterable[EvidenceItem]) -> int:
    return sum(
        any(pattern.search(item.content) for pattern in INSTRUCTION_PATTERNS)
        for item in items
    )


def has_instruction_boundary(packet: EvidencePacket) -> bool:
    boundary = " ".join(packet.boundaries).casefold()
    return bool(
        "untrusted" in boundary
        and ("cannot authorise" in boundary or "cannot authorize" in boundary)
        and ("tool" in boundary or "policy" in boundary)
    )


def identity_report(
    packet: EvidencePacket,
    expected: dict[str, Any] | None,
) -> dict[str, Any]:
    film = packet.film_record
    title = str(film.get("title") or "").strip()
    year = film.get("year")
    directors = [str(value).strip() for value in film.get("directors", []) if str(value).strip()]
    complete = bool(title and isinstance(year, int) and directors)
    matches = None
    if expected:
        expected_director = normalise_identity(expected.get("director"))
        matches = bool(
            normalise_identity(title) == normalise_identity(expected.get("title"))
            and year == expected.get("year")
            and expected_director
            and any(normalise_identity(value) == expected_director for value in directors)
        )
    return {
        "complete": complete,
        "expected_supplied": bool(expected),
        "matches_expected": matches,
        "director_count": len(directors),
    }


def citation_readiness(packet: EvidencePacket) -> dict[str, Any]:
    theory_ids = [item.evidence_id for item in packet.theory_sources]
    attributed_ids = [item.evidence_id for item in packet.attributed_sources]
    claim_ids = [claim.claim_id for claim in packet.critical_claims]
    all_ids = theory_ids + attributed_ids + claim_ids
    valid = bool(
        len(all_ids) == len(set(all_ids))
        and all(re.fullmatch(r"S[1-9]\d*", value) for value in theory_ids)
        and all(re.fullmatch(r"E[1-9]\d*", value) for value in attributed_ids)
        and all(re.fullmatch(r"C[1-9]\d*", value) for value in claim_ids)
    )
    return {
        "valid": valid,
        "identifier_count": len(all_ids),
        "unique_identifier_count": len(set(all_ids)),
    }


def assess_evidence_packet(
    packet: EvidencePacket,
    *,
    expected_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return aggregate packet-quality evidence without source text or titles."""

    items = [*packet.theory_sources, *packet.attributed_sources]
    identity = identity_report(packet, expected_identity)
    citation = citation_readiness(packet)
    complete_provenance = sum(item_has_complete_provenance(item) for item in items)
    duplicate_items = duplicate_item_count(items)
    focus_tokens = content_tokens(packet.focus)
    relevant_items = sum(
        bool(focus_tokens & content_tokens(f"{item.title} {item.content}"))
        for item in items
    )
    flagged_instructions = instruction_item_count(items)
    instruction_contained = has_instruction_boundary(packet)
    languages = sorted({safe_language(item.language) for item in items})
    evidence_types = sorted({item.evidence_type for item in items})
    attributed_selection = packet.retrieval.get("attributed_selection", {})
    omitted_items = int(attributed_selection.get("omitted_items", 0) or 0)
    total_items = len(items)
    issues: set[str] = set()

    if not identity["complete"]:
        issues.add("film_identity_incomplete")
    if identity["matches_expected"] is False:
        issues.add("film_identity_mismatch")
    if not packet.theory_sources:
        issues.add("theory_evidence_missing")
    if not packet.attributed_sources and not packet.critical_claims:
        issues.add("film_specific_evidence_sparse")
    if not citation["valid"]:
        issues.add("citation_ids_invalid")
    if total_items and complete_provenance != total_items:
        issues.add("provenance_incomplete")
    if duplicate_items:
        issues.add("duplicate_evidence_present")
    if total_items >= 4 and len(evidence_types) < 2:
        issues.add("single_evidence_class")
    if "und" in languages:
        issues.add("unknown_evidence_language")
    relevance_ratio = relevant_items / total_items if total_items else 0.0
    if total_items and focus_tokens and relevance_ratio < 0.3:
        issues.add("focus_relevance_low")
    if flagged_instructions and not instruction_contained:
        issues.add("instruction_containment_missing")
    if omitted_items:
        issues.add("attributed_items_omitted")

    if not issues:
        status = "passed"
    elif issues & BLOCKING_PACKET_ISSUES:
        status = "failed"
    else:
        status = "limited"
    if not issues <= PACKET_ISSUES:
        raise ValueError("Unknown packet quality issue code.")

    return {
        "schema_version": 1,
        "status": status,
        "issues": sorted(issues),
        "identity": identity,
        "citation_readiness": citation,
        "provenance": {
            "complete_items": complete_provenance,
            "total_items": total_items,
            "completeness_ratio": round(complete_provenance / total_items, 4)
            if total_items
            else 0.0,
        },
        "duplication": {
            "duplicate_items": duplicate_items,
            "selected_items": total_items,
            "duplicate_ratio": round(duplicate_items / total_items, 4)
            if total_items
            else 0.0,
        },
        "focus_relevance": {
            "focus_token_count": len(focus_tokens),
            "relevant_items": relevant_items,
            "total_items": total_items,
            "relevance_ratio": round(relevance_ratio, 4),
        },
        "diversity": {
            "evidence_types": evidence_types,
            "evidence_type_count": len(evidence_types),
            "languages": languages,
            "language_count": len(languages),
            "theory_title_count": len({item.title.casefold() for item in packet.theory_sources}),
            "attributed_origin_count": len(
                {
                    urlparse(str(item.source_url)).netloc.casefold()
                    for item in packet.attributed_sources
                    if safe_http_url(item.source_url)
                }
            ),
        },
        "instruction_safety": {
            "flagged_items": flagged_instructions,
            "containment_boundary": instruction_contained,
        },
        "sufficiency": {
            "state": (
                "insufficient"
                if not packet.theory_sources
                else "sparse"
                if not packet.attributed_sources and not packet.critical_claims
                else "bounded"
                if len(packet.attributed_sources) <= 2
                else "abundant"
            ),
            "theory_sources": len(packet.theory_sources),
            "film_specific_sources": len(packet.attributed_sources),
            "critical_claims": len(packet.critical_claims),
        },
        "selection": {
            "theory_candidates": int(packet.retrieval.get("candidate_count", 0) or 0),
            "theory_selected": len(packet.theory_sources),
            "critical_claims": len(packet.critical_claims),
            "attributed_candidates": int(
                attributed_selection.get("candidate_items", 0) or 0
            ),
            "attributed_selected": len(packet.attributed_sources),
            "attributed_omitted": omitted_items,
            "attributed_truncated": int(
                attributed_selection.get("truncated_items", 0) or 0
            ),
        },
        "size": {
            "packet_characters": len(packet.model_dump_json()),
            "evidence_characters": sum(len(item.content) for item in items),
        },
    }
