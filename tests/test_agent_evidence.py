from __future__ import annotations

import pytest

from app.backend.agent_evidence import (
    MIN_RECOVERED_INDEPENDENT_ORIGINS,
    assess_agent_evidence,
    choose_deterministic_research_tool,
)
from app.backend.criticism import ReviewSource
from app.backend.evidence import EvidencePacket
from app.backend.research_agent_contract import EvidenceGap, ToolName


FILM = {
    "title": "Example Film",
    "year": 2024,
    "credits": {"directors": ["Example Director"]},
}
THEORY = {
    "passages": [
        {
            "title": "Framing Theory",
            "page": 12,
            "language": "en",
            "excerpt": (
                "Framing and editing organise uncertainty through repeatable spatial relations "
                "that a filmmaker can log, compare and test during close viewing."
            ),
        }
    ],
    "method": "hybrid_rrf",
}
FOCUS = "How do framing and editing organise uncertainty?"


def source(provider: str, domain: str, index: int) -> ReviewSource:
    summary = (
        "A scholarly abstract connects editing rhythm to spatial uncertainty and compares how "
        "recurring cuts redistribute attention across the frame."
        if provider == "Crossref"
        else (
            "The critic reports that framing and editing organise uncertainty through recurring "
            "spatial relations that should be checked during close viewing."
        )
    )
    return ReviewSource(
        source_id=f"R{index}",
        provider=provider,
        review_id=f"review-{index}",
        title="Attributed review",
        summary=summary,
        author="A Critic",
        url=f"https://{domain}/reviews/{index}",
        language="en",
    )


def packet(*reviews: ReviewSource) -> EvidencePacket:
    return EvidencePacket.from_retrieval(FILM, THEORY, FOCUS, reviews=list(reviews))


def test_existing_passed_packet_remains_sufficient_without_diversity_spend() -> None:
    value = packet(source("Guardian", "theguardian.com", 1))

    assessment = assess_agent_evidence(value, initial_packet_status="passed")

    assert assessment.sufficient is True
    assert assessment.recovery_diversity_required is False
    assert assessment.independent_origins == 1


def test_recovered_packet_requires_two_independent_origins() -> None:
    one_origin = packet(source("Letterboxd", "letterboxd.com", 1))
    two_origins = packet(
        source("Letterboxd", "letterboxd.com", 1),
        source("Crossref", "doi.org", 2),
    )

    one = assess_agent_evidence(one_origin, initial_packet_status="limited")
    two = assess_agent_evidence(two_origins, initial_packet_status="limited")

    assert one.sufficient is False
    assert one.independent_origins == 1
    assert EvidenceGap.INDEPENDENT_ORIGINS in one.gaps
    assert two.sufficient is True
    assert two.independent_origins == MIN_RECOVERED_INDEPENDENT_ORIGINS
    assert EvidenceGap.INDEPENDENT_ORIGINS not in two.gaps


def test_www_alias_does_not_count_as_an_independent_origin() -> None:
    value = packet(
        source("Letterboxd", "letterboxd.com", 1),
        source("Crossref", "www.letterboxd.com", 2),
    )

    assessment = assess_agent_evidence(value, initial_packet_status="limited")

    assert assessment.independent_origins == 1
    assert assessment.sufficient is False


def test_safe_agent_summary_contains_aggregates_not_evidence_text() -> None:
    value = packet(source("Letterboxd", "letterboxd.com", 1))
    assessment = assess_agent_evidence(value, initial_packet_status="limited")

    summary = assessment.safe_summary({"status": "passed", "issues": []})

    assert summary["agent_status"] == "needs_research"
    assert summary["agent_gaps"] == [
        EvidenceGap.INDEPENDENT_ORIGINS.value,
        EvidenceGap.EVIDENCE_CLASS_DIVERSITY.value,
    ]
    assert summary["agent_diversity"]["independent_film_origins"] == 1
    assert "The critic reports" not in str(summary)
    assert "letterboxd.com" not in str(summary)


def test_deterministic_baseline_targets_independent_origin_with_crossref() -> None:
    assessment = assess_agent_evidence(
        packet(source("Letterboxd", "letterboxd.com", 1)),
        initial_packet_status="limited",
    )
    allowed = (
        ToolName.FETCH_CROSSREF_RESEARCH,
        ToolName.FETCH_GUARDIAN_REVIEWS,
    )
    states = {
        ToolName.FETCH_CROSSREF_RESEARCH.value: {"state": "ready"},
        ToolName.FETCH_GUARDIAN_REVIEWS.value: {"state": "ready"},
    }

    tool, gap = choose_deterministic_research_tool(assessment, allowed, states)

    assert tool is ToolName.FETCH_CROSSREF_RESEARCH
    assert gap is EvidenceGap.INDEPENDENT_ORIGINS


def test_deterministic_baseline_fails_closed_without_ready_provider() -> None:
    assessment = assess_agent_evidence(packet(), initial_packet_status="limited")

    with pytest.raises(ValueError, match="No ready allow-listed provider"):
        choose_deterministic_research_tool(
            assessment,
            (ToolName.FETCH_GUARDIAN_REVIEWS,),
            {ToolName.FETCH_GUARDIAN_REVIEWS.value: {"state": "unavailable"}},
        )
