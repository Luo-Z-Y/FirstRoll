from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.backend.criticism import CriticalClaim


EvidenceKind = Literal[
    "film_record",
    "theory_framework",
    "critic_reported",
    "creator_stated",
    "film_observed",
    "model_hypothesis",
]


class EvidenceItem(BaseModel):
    """One typed, attributable item that may be supplied to the study model."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    evidence_type: EvidenceKind
    title: str
    content: str
    locator: str | None = None
    source_url: str | None = None
    language: str = "und"
    licence: str | None = None
    permitted_claims: list[str] = Field(default_factory=list)


class EvidencePacket(BaseModel):
    """The complete, inspectable boundary around one synthesis request."""

    model_config = ConfigDict(extra="forbid")

    focus: str
    film_record: dict[str, Any]
    theory_sources: list[EvidenceItem]
    critical_claims: list[CriticalClaim] = Field(default_factory=list)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    boundaries: list[str] = Field(default_factory=list)

    @classmethod
    def from_retrieval(
        cls,
        film: dict[str, Any],
        retrieval: dict[str, Any],
        focus: str | None,
        critical_claims: list[CriticalClaim] | None = None,
    ) -> "EvidencePacket":
        credits = film.get("credits") or {}
        record = {
            "title": film.get("title"),
            "original_title": film.get("original_title"),
            "year": film.get("year"),
            "directors": credits.get("directors") or film.get("directors") or [],
            "writers": credits.get("writers") or [],
            "cinematographers": credits.get("cinematographers") or [],
            "runtime_minutes": film.get("runtime_minutes"),
            "genres": film.get("genres") or [],
            "countries": film.get("countries") or [],
            "overview": film.get("overview"),
            "record_source": film.get("source"),
            "overview_source": film.get("overview_source"),
        }
        items = []
        for index, passage in enumerate(retrieval.get("passages", []), start=1):
            items.append(
                EvidenceItem(
                    evidence_id=f"S{index}",
                    evidence_type="theory_framework",
                    title=str(passage.get("title") or "Local source"),
                    content=str(passage.get("excerpt") or ""),
                    locator=f"PDF p. {passage.get('page', '?')}",
                    language=str(passage.get("language") or "und"),
                    permitted_claims=[
                        "define or explain an analytical concept",
                        "motivate a viewing question",
                    ],
                )
            )
        return cls(
            focus=(focus or "Create a rigorous formal study dossier for this film.").strip(),
            film_record=record,
            theory_sources=items,
            critical_claims=critical_claims or [],
            retrieval={
                "method": retrieval.get("method", "fts"),
                "plan": retrieval.get("plan", []),
                "candidate_count": retrieval.get("candidate_count", 0),
                "embedding": retrieval.get("embedding", {}),
            },
            boundaries=[
                "Theory sources explain concepts; they do not describe this film.",
                "Criticism reports an attributed interpretation; it is not direct observation.",
                "Without a supplied clip, film-form claims remain viewing hypotheses.",
                "Creator intention requires an attributed creator statement.",
            ],
        )
