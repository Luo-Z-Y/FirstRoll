from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

from app.backend.evidence import EvidencePacket
from app.backend.packet_quality import assess_evidence_packet, safe_http_url
from app.backend.research_agent_contract import EvidenceGap, ToolName


MIN_RECOVERED_INDEPENDENT_ORIGINS = 2


@dataclass(frozen=True)
class AgentEvidenceAssessment:
    """Safe evidence-gap assessment used by the autonomous research controller."""

    sufficient: bool
    base_status: str
    initial_packet_status: str
    gaps: tuple[EvidenceGap, ...]
    independent_origins: int
    film_specific_evidence_classes: int
    focus_relevance_ratio: float
    recovery_diversity_required: bool

    def safe_summary(self, base_quality: dict[str, Any]) -> dict[str, Any]:
        """Return planner-safe aggregates without source text, titles or URLs."""

        return {
            **base_quality,
            "agent_status": "sufficient" if self.sufficient else "needs_research",
            "agent_gaps": [gap.value for gap in self.gaps],
            "agent_diversity": {
                "independent_film_origins": self.independent_origins,
                "film_specific_evidence_classes": self.film_specific_evidence_classes,
                "minimum_recovered_independent_origins": (
                    MIN_RECOVERED_INDEPENDENT_ORIGINS if self.recovery_diversity_required else 0
                ),
            },
        }


def assess_agent_evidence(
    packet: EvidencePacket,
    *,
    initial_packet_status: str,
) -> AgentEvidenceAssessment:
    """Assess whether autonomous acquisition has closed a real evidence gap.

    A packet that was already sufficient remains untouched. A packet recovered from
    ``limited`` or ``failed`` must not pass merely because one website returned several
    excerpts: it needs at least two independent film-specific origins.
    """

    quality = assess_evidence_packet(packet)
    origins = {
        str(urlparse(str(item.source_url)).hostname or "").casefold().removeprefix("www.")
        for item in packet.attributed_sources
        if safe_http_url(item.source_url)
    }
    origins.discard("")
    evidence_classes: set[str] = {item.evidence_type for item in packet.attributed_sources}
    if packet.critical_claims:
        evidence_classes.add("structured_critical_claim")

    recovery_diversity_required = initial_packet_status != "passed"
    gaps: list[EvidenceGap] = []
    if not packet.attributed_sources and not packet.critical_claims:
        gaps.append(EvidenceGap.FILM_SPECIFIC_EVIDENCE)
    if recovery_diversity_required and len(origins) < MIN_RECOVERED_INDEPENDENT_ORIGINS:
        gaps.append(EvidenceGap.INDEPENDENT_ORIGINS)
    if recovery_diversity_required and len(evidence_classes) < 2:
        gaps.append(EvidenceGap.EVIDENCE_CLASS_DIVERSITY)
    relevance_ratio = float(quality.get("focus_relevance", {}).get("relevance_ratio", 0.0) or 0.0)
    if quality.get("issues") and "focus_relevance_low" in quality["issues"]:
        gaps.append(EvidenceGap.FOCUS_RELEVANCE)

    sufficient = bool(quality["status"] == "passed" and not gaps)
    return AgentEvidenceAssessment(
        sufficient=sufficient,
        base_status=str(quality["status"]),
        initial_packet_status=initial_packet_status,
        gaps=tuple(dict.fromkeys(gaps)),
        independent_origins=len(origins),
        film_specific_evidence_classes=len(evidence_classes),
        focus_relevance_ratio=relevance_ratio,
        recovery_diversity_required=recovery_diversity_required,
    )


TOOL_GAP_CAPABILITIES: dict[ToolName, frozenset[EvidenceGap]] = {
    ToolName.FETCH_GUARDIAN_REVIEWS: frozenset(
        {
            EvidenceGap.FILM_SPECIFIC_EVIDENCE,
            EvidenceGap.INDEPENDENT_ORIGINS,
            EvidenceGap.FOCUS_RELEVANCE,
        }
    ),
    ToolName.FETCH_CROSSREF_RESEARCH: frozenset(
        {
            EvidenceGap.FILM_SPECIFIC_EVIDENCE,
            EvidenceGap.INDEPENDENT_ORIGINS,
            EvidenceGap.EVIDENCE_CLASS_DIVERSITY,
            EvidenceGap.FOCUS_RELEVANCE,
        }
    ),
    ToolName.FETCH_LETTERBOXD_REVIEWS: frozenset(
        {
            EvidenceGap.FILM_SPECIFIC_EVIDENCE,
            EvidenceGap.INDEPENDENT_ORIGINS,
            EvidenceGap.FOCUS_RELEVANCE,
        }
    ),
    ToolName.FETCH_DOUBAN_REVIEWS: frozenset(
        {
            EvidenceGap.FILM_SPECIFIC_EVIDENCE,
            EvidenceGap.INDEPENDENT_ORIGINS,
            EvidenceGap.FOCUS_RELEVANCE,
        }
    ),
    ToolName.SEARCH_YOUTUBE_RESOURCES: frozenset(EvidenceGap),
}


def tool_addresses_gap(tool: ToolName, gap: EvidenceGap) -> bool:
    return gap in TOOL_GAP_CAPABILITIES.get(tool, frozenset())


TOOL_GAP_PRIORITY: dict[EvidenceGap, tuple[ToolName, ...]] = {
    EvidenceGap.FILM_SPECIFIC_EVIDENCE: (
        ToolName.FETCH_GUARDIAN_REVIEWS,
        ToolName.FETCH_CROSSREF_RESEARCH,
        ToolName.FETCH_LETTERBOXD_REVIEWS,
        ToolName.FETCH_DOUBAN_REVIEWS,
        ToolName.SEARCH_YOUTUBE_RESOURCES,
    ),
    EvidenceGap.INDEPENDENT_ORIGINS: (
        ToolName.FETCH_CROSSREF_RESEARCH,
        ToolName.FETCH_GUARDIAN_REVIEWS,
        ToolName.SEARCH_YOUTUBE_RESOURCES,
        ToolName.FETCH_DOUBAN_REVIEWS,
        ToolName.FETCH_LETTERBOXD_REVIEWS,
    ),
    EvidenceGap.EVIDENCE_CLASS_DIVERSITY: (
        ToolName.FETCH_CROSSREF_RESEARCH,
        ToolName.SEARCH_YOUTUBE_RESOURCES,
    ),
    EvidenceGap.FOCUS_RELEVANCE: (
        ToolName.FETCH_CROSSREF_RESEARCH,
        ToolName.FETCH_GUARDIAN_REVIEWS,
        ToolName.SEARCH_YOUTUBE_RESOURCES,
        ToolName.FETCH_DOUBAN_REVIEWS,
        ToolName.FETCH_LETTERBOXD_REVIEWS,
    ),
}


def choose_deterministic_research_tool(
    assessment: AgentEvidenceAssessment,
    allowed_tools: tuple[ToolName, ...],
    provider_states: dict[str, dict[str, Any]],
) -> tuple[ToolName, EvidenceGap]:
    """Return the transparent non-model baseline for acquisition ablations."""

    allowed = set(allowed_tools)
    for gap in assessment.gaps:
        for tool in TOOL_GAP_PRIORITY[gap]:
            state = provider_states.get(tool.value, {})
            if tool in allowed and state.get("state") == "ready":
                return tool, gap
    raise ValueError("No ready allow-listed provider can address the remaining evidence gaps.")


PlannerMode = Literal["model", "deterministic"]
