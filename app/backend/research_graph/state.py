from __future__ import annotations

from typing import Annotated, Any, TypedDict

from app.backend.research_agent_contract import (
    DEFAULT_BUDGETS,
    EvidenceRef,
    NextAction,
    TerminalStatus,
    ToolFailure,
    ToolName,
)
from app.backend.research_graph.events import ResearchEvent


MAX_EVENT_ITEMS = 40
MAX_FAILURE_ITEMS = 12


def merge_evidence(
    current: tuple[EvidenceRef, ...],
    update: tuple[EvidenceRef, ...],
) -> tuple[EvidenceRef, ...]:
    """Deduplicate evidence while enforcing the default prompt-state limits."""

    merged: dict[str, EvidenceRef] = {item.evidence_id: item for item in current}
    for item in update:
        merged.setdefault(item.evidence_id, item)

    bounded: list[EvidenceRef] = []
    characters = 0
    for item in merged.values():
        if len(bounded) >= DEFAULT_BUDGETS.max_evidence_items:
            break
        if characters + len(item.content) > DEFAULT_BUDGETS.max_evidence_characters:
            break
        bounded.append(item)
        characters += len(item.content)
    return tuple(bounded)


def merge_unique_tools(
    current: tuple[ToolName, ...],
    update: tuple[ToolName, ...],
) -> tuple[ToolName, ...]:
    return tuple(dict.fromkeys((*current, *update)))


def merge_failures(
    current: tuple[ToolFailure, ...],
    update: tuple[ToolFailure, ...],
) -> tuple[ToolFailure, ...]:
    return (*current, *update)[-MAX_FAILURE_ITEMS:]


def merge_events(
    current: tuple[ResearchEvent, ...],
    update: tuple[ResearchEvent, ...],
) -> tuple[ResearchEvent, ...]:
    return (*current, *update)[-MAX_EVENT_ITEMS:]


class ResearchGraphState(TypedDict):
    # Framework-neutral Agent contract.
    run_id: str
    user_id: str
    question: str
    film_query: str
    film_id: str | None
    film_candidates: tuple[str, ...]
    existing_evidence_checked: bool
    evidence: Annotated[tuple[EvidenceRef, ...], merge_evidence]
    evidence_sufficient: bool
    attempted_tools: Annotated[tuple[ToolName, ...], merge_unique_tools]
    tool_failures: Annotated[tuple[ToolFailure, ...], merge_failures]
    step_count: int
    planning_calls: int
    external_tool_calls: int
    synthesis_calls: int
    repair_calls: int
    draft_available: bool
    quality_passed: bool | None
    deadline_exceeded: bool
    status: TerminalStatus

    # Graph orchestration fields. Credentials and clients belong in runtime context.
    next_action: NextAction | None
    decision_reason: str | None
    allowed_tools: tuple[ToolName, ...]
    selected_tool: ToolName | None
    tool_authorised: bool
    draft: dict[str, Any] | None
    quality: dict[str, Any] | None
    terminal_reason: str | None
    events: Annotated[tuple[ResearchEvent, ...], merge_events]


def initial_research_state(
    *,
    run_id: str,
    user_id: str,
    question: str,
    film_query: str,
    film_id: str | None = None,
    evidence: tuple[EvidenceRef, ...] = (),
    existing_evidence_checked: bool = False,
    evidence_sufficient: bool = False,
) -> ResearchGraphState:
    """Create a complete graph input with no credentials or infrastructure objects."""

    return {
        "run_id": run_id,
        "user_id": user_id,
        "question": question,
        "film_query": film_query,
        "film_id": film_id,
        "film_candidates": (),
        "existing_evidence_checked": existing_evidence_checked,
        "evidence": evidence,
        "evidence_sufficient": evidence_sufficient,
        "attempted_tools": (),
        "tool_failures": (),
        "step_count": 0,
        "planning_calls": 0,
        "external_tool_calls": 0,
        "synthesis_calls": 0,
        "repair_calls": 0,
        "draft_available": False,
        "quality_passed": None,
        "deadline_exceeded": False,
        "status": TerminalStatus.RUNNING,
        "next_action": None,
        "decision_reason": None,
        "allowed_tools": (),
        "selected_tool": None,
        "tool_authorised": False,
        "draft": None,
        "quality": None,
        "terminal_reason": None,
        "events": (),
    }
