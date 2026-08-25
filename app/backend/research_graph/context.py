from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.backend.research_agent_contract import (
    DEFAULT_BUDGETS,
    EvidenceRef,
    ResearchBudgets,
    ToolFailure,
    ToolName,
)
from app.backend.research_graph.state import ResearchGraphState


@dataclass(frozen=True)
class FilmResolution:
    film_id: str | None = None
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolObservation:
    evidence: tuple[EvidenceRef, ...] = ()
    failure: ToolFailure | None = None


@dataclass(frozen=True)
class DraftResult:
    draft: dict[str, Any]


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    report: dict[str, Any]


class ResearchGraphServices(Protocol):
    """Application capabilities used by graph nodes and replaceable by test fakes."""

    def resolve_film(self, state: ResearchGraphState) -> FilmResolution: ...

    def load_existing_evidence(
        self,
        state: ResearchGraphState,
    ) -> tuple[EvidenceRef, ...]: ...

    def evidence_is_sufficient(self, state: ResearchGraphState) -> bool: ...

    def choose_tool(
        self,
        state: ResearchGraphState,
        allowed_tools: tuple[ToolName, ...],
    ) -> ToolName: ...

    def run_tool(self, state: ResearchGraphState, tool: ToolName) -> ToolObservation: ...

    def synthesise(self, state: ResearchGraphState) -> DraftResult: ...

    def validate(self, state: ResearchGraphState) -> ValidationResult: ...

    def repair(self, state: ResearchGraphState) -> DraftResult: ...


@dataclass(frozen=True)
class ResearchGraphContext:
    """Runtime capabilities plus local-only evaluation isolation mode."""

    services: ResearchGraphServices
    budgets: ResearchBudgets = field(default_factory=lambda: DEFAULT_BUDGETS)
    mode: Literal["full", "evidence_only", "synthesis_only"] = "full"
