from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, TypedDict


class ToolName(StrEnum):
    RESOLVE_FILM_IDENTITY = "resolve_film_identity"
    LOAD_EXISTING_EVIDENCE = "load_existing_evidence"
    RETRIEVE_THEORY_PASSAGES = "retrieve_theory_passages"
    SEARCH_CACHED_CRITICISM = "search_cached_criticism"
    FETCH_GUARDIAN_REVIEWS = "fetch_guardian_reviews"
    FETCH_DOUBAN_REVIEWS = "fetch_douban_reviews"
    FETCH_LETTERBOXD_REVIEWS = "fetch_letterboxd_reviews"
    SEARCH_YOUTUBE_RESOURCES = "search_youtube_resources"


PERMITTED_TOOLS = frozenset(ToolName)
EXTERNAL_TOOLS = frozenset(
    {
        ToolName.FETCH_GUARDIAN_REVIEWS,
        ToolName.FETCH_DOUBAN_REVIEWS,
        ToolName.FETCH_LETTERBOXD_REVIEWS,
        ToolName.SEARCH_YOUTUBE_RESOURCES,
    }
)


class ActionOrigin(StrEnum):
    DETERMINISTIC_ROUTER = "deterministic_router"
    MODEL_PLANNER = "model_planner"
    RETRIEVED_EVIDENCE = "retrieved_evidence"


class NextAction(StrEnum):
    RESOLVE_FILM = "resolve_film"
    ASK_USER = "ask_user"
    LOAD_EXISTING_EVIDENCE = "load_existing_evidence"
    CHOOSE_RESEARCH_TOOL = "choose_research_tool"
    SYNTHESISE = "synthesise"
    REPAIR = "repair"
    COMPLETE = "complete"
    RETURN_INSUFFICIENT_EVIDENCE = "return_insufficient_evidence"
    FAIL_SAFE = "fail_safe"
    STOP = "stop"


class TerminalStatus(StrEnum):
    RUNNING = "running"
    NEEDS_USER = "needs_user"
    COMPLETE = "complete"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BUDGET_EXHAUSTED = "budget_exhausted"
    FAILED_SAFE = "failed_safe"


class EvidenceKind(StrEnum):
    FILM_RECORD = "film_record"
    THEORY_FRAMEWORK = "theory_framework"
    CRITIC_REPORTED = "critic_reported"
    CREATOR_STATED = "creator_stated"
    VIDEO_CONTEXT = "video_context"


class FailureKind(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_CREDENTIALS = "invalid_credentials"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    kind: EvidenceKind
    provider: str
    locator: str
    content: str
    relevant: bool = True
    instruction_trusted: Literal[False] = field(default=False, init=False)

    def __post_init__(self) -> None:
        cleaned = self.content.strip()
        if not self.evidence_id.strip() or not self.provider.strip():
            raise ValueError("Evidence must have a stable ID and provider.")
        if not cleaned:
            raise ValueError("Evidence content cannot be empty.")
        if len(cleaned) > 6_000:
            raise ValueError("One evidence item cannot exceed 6,000 characters.")
        object.__setattr__(self, "content", cleaned)


@dataclass(frozen=True)
class ToolFailure:
    tool: ToolName
    kind: FailureKind
    retryable: bool
    public_message: str


@dataclass(frozen=True)
class ToolRequest:
    tool: ToolName
    origin: ActionOrigin


@dataclass(frozen=True)
class ToolPlan:
    tool: ToolName
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        for value in (self.prompt_tokens, self.completion_tokens, self.total_tokens):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("Planner token counts must be non-negative integers.")
        if self.total_tokens < self.prompt_tokens + self.completion_tokens:
            raise ValueError("Planner total tokens cannot be lower than component counts.")


@dataclass(frozen=True)
class ResearchBudgets:
    max_graph_steps: int = 8
    max_planning_calls: int = 4
    max_external_tool_calls: int = 3
    max_calls_per_external_tool: int = 1
    max_evidence_items: int = 12
    max_evidence_characters: int = 36_000
    research_deadline_seconds: int = 45
    max_synthesis_calls: int = 1
    max_repair_calls: int = 1
    max_total_model_calls: int = 6


DEFAULT_BUDGETS = ResearchBudgets()


class ResearchState(TypedDict):
    run_id: str
    user_id: str
    question: str
    film_query: str
    film_id: str | None
    film_candidates: tuple[str, ...]
    existing_evidence_checked: bool
    evidence: tuple[EvidenceRef, ...]
    evidence_sufficient: bool
    attempted_tools: tuple[ToolName, ...]
    tool_failures: tuple[ToolFailure, ...]
    step_count: int
    planning_calls: int
    external_tool_calls: int
    synthesis_calls: int
    repair_calls: int
    draft_available: bool
    quality_passed: bool | None
    deadline_exceeded: bool
    status: TerminalStatus


@dataclass(frozen=True)
class PolicyDecision:
    action: NextAction
    reason: str
    terminal_status: TerminalStatus | None = None
    allowed_tools: tuple[ToolName, ...] = ()


@dataclass(frozen=True)
class ToolAuthorisation:
    allowed: bool
    reason: str


FORBIDDEN_STATE_KEYS = frozenset(
    {
        "api_key",
        "deepseek_api_key",
        "youtube_api_key",
        "authorization",
        "access_token",
        "cookie",
    }
)


def _remaining_external_tools(state: ResearchState) -> tuple[ToolName, ...]:
    attempted = set(state["attempted_tools"])
    return tuple(sorted(EXTERNAL_TOOLS - attempted, key=str))


def _evidence_characters(state: ResearchState) -> int:
    return sum(len(item.content) for item in state["evidence"])


def decide_next_action(
    state: ResearchState,
    budgets: ResearchBudgets = DEFAULT_BUDGETS,
) -> PolicyDecision:
    """Return the deterministic safety envelope around a future model planner."""

    unexpected_secrets = FORBIDDEN_STATE_KEYS.intersection(state)
    if unexpected_secrets:
        return PolicyDecision(
            NextAction.FAIL_SAFE,
            "Credentials or session material appeared in graph state.",
            TerminalStatus.FAILED_SAFE,
        )
    if state["status"] is not TerminalStatus.RUNNING:
        return PolicyDecision(
            NextAction.STOP,
            "The run has already reached a terminal state.",
            state["status"],
        )
    if state["deadline_exceeded"]:
        return PolicyDecision(
            NextAction.RETURN_INSUFFICIENT_EVIDENCE,
            "The research deadline was exhausted.",
            TerminalStatus.BUDGET_EXHAUSTED,
        )
    if state["step_count"] >= budgets.max_graph_steps:
        return PolicyDecision(
            NextAction.RETURN_INSUFFICIENT_EVIDENCE,
            "The graph-step budget was exhausted.",
            TerminalStatus.BUDGET_EXHAUSTED,
        )
    if len(state["evidence"]) > budgets.max_evidence_items:
        return PolicyDecision(
            NextAction.FAIL_SAFE,
            "The evidence-item limit was exceeded before synthesis.",
            TerminalStatus.FAILED_SAFE,
        )
    if _evidence_characters(state) > budgets.max_evidence_characters:
        return PolicyDecision(
            NextAction.FAIL_SAFE,
            "The evidence-character limit was exceeded before synthesis.",
            TerminalStatus.FAILED_SAFE,
        )
    if state["film_id"] is None:
        if len(state["film_candidates"]) > 1:
            return PolicyDecision(
                NextAction.ASK_USER,
                "Several films match the query; the user must choose one.",
                TerminalStatus.NEEDS_USER,
            )
        return PolicyDecision(
            NextAction.RESOLVE_FILM,
            "A verified film identity is required before research.",
        )
    if not state["existing_evidence_checked"]:
        return PolicyDecision(
            NextAction.LOAD_EXISTING_EVIDENCE,
            "Inspect existing evidence before spending an external-call budget.",
        )
    if state["draft_available"]:
        if state["quality_passed"] is True:
            return PolicyDecision(
                NextAction.COMPLETE,
                "The draft passed deterministic validation and quality checks.",
                TerminalStatus.COMPLETE,
            )
        if state["repair_calls"] < budgets.max_repair_calls:
            return PolicyDecision(
                NextAction.REPAIR,
                "One bounded repair remains available.",
            )
        return PolicyDecision(
            NextAction.RETURN_INSUFFICIENT_EVIDENCE,
            "The validated draft still failed the quality gate after repair.",
            TerminalStatus.INSUFFICIENT_EVIDENCE,
        )
    if state["evidence_sufficient"]:
        if state["synthesis_calls"] >= budgets.max_synthesis_calls:
            return PolicyDecision(
                NextAction.FAIL_SAFE,
                "The synthesis-call budget was already consumed without a draft.",
                TerminalStatus.FAILED_SAFE,
            )
        return PolicyDecision(
            NextAction.SYNTHESISE,
            "Existing evidence is sufficient; no external research is justified.",
        )

    remaining = _remaining_external_tools(state)
    if (
        state["external_tool_calls"] >= budgets.max_external_tool_calls
        or state["planning_calls"] >= budgets.max_planning_calls
        or not remaining
    ):
        return PolicyDecision(
            NextAction.RETURN_INSUFFICIENT_EVIDENCE,
            "No useful evidence was found within the bounded research budget.",
            TerminalStatus.INSUFFICIENT_EVIDENCE,
        )
    return PolicyDecision(
        NextAction.CHOOSE_RESEARCH_TOOL,
        "A planner may choose one remaining allow-listed research tool.",
        allowed_tools=remaining,
    )


def authorise_tool_request(
    state: ResearchState,
    request: ToolRequest,
    budgets: ResearchBudgets = DEFAULT_BUDGETS,
) -> ToolAuthorisation:
    """Validate a proposed tool call independently of the proposing model."""

    if request.origin is ActionOrigin.RETRIEVED_EVIDENCE:
        return ToolAuthorisation(False, "Retrieved evidence can never authorise a tool call.")
    if request.tool not in PERMITTED_TOOLS:
        return ToolAuthorisation(False, "The requested tool is not allow-listed.")
    policy = decide_next_action(state, budgets)
    if policy.terminal_status is not None:
        return ToolAuthorisation(False, "A terminal or paused run cannot call another tool.")
    if request.tool in EXTERNAL_TOOLS:
        if policy.action is not NextAction.CHOOSE_RESEARCH_TOOL:
            return ToolAuthorisation(False, "An external call is unnecessary in the current state.")
        if request.tool not in policy.allowed_tools:
            return ToolAuthorisation(False, "This provider has already been attempted.")
        if state["external_tool_calls"] >= budgets.max_external_tool_calls:
            return ToolAuthorisation(False, "The external-call budget is exhausted.")
    return ToolAuthorisation(True, "The tool call is within the deterministic safety envelope.")
