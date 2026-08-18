from __future__ import annotations

from typing import Any, cast

from langgraph.runtime import Runtime

from app.backend.research_agent_contract import (
    ActionOrigin,
    FailureKind,
    NextAction,
    ResearchState,
    TerminalStatus,
    ToolFailure,
    ToolName,
    ToolRequest,
    authorise_tool_request,
    decide_next_action,
)
from app.backend.research_graph.context import ResearchGraphContext
from app.backend.research_graph.events import event
from app.backend.research_graph.state import ResearchGraphState


def _contract_state(state: ResearchGraphState) -> ResearchState:
    """Narrow graph state to the framework-neutral policy contract."""

    return cast(ResearchState, state)


def normalise_question(state: ResearchGraphState) -> dict[str, Any]:
    question = " ".join(state["question"].split())
    if not question:
        return {
            "status": TerminalStatus.FAILED_SAFE,
            "terminal_reason": "A research question is required.",
            "events": event("run_failed", "The research question is empty."),
        }
    return {
        "question": question,
        "events": event("question_normalised", "The research question was validated."),
    }


def policy(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    decision = decide_next_action(_contract_state(state), runtime.context.budgets)
    update: dict[str, Any] = {
        "next_action": decision.action,
        "decision_reason": decision.reason,
        "allowed_tools": decision.allowed_tools,
    }
    if decision.terminal_status is not None:
        update["status"] = decision.terminal_status
        if decision.action is not NextAction.STOP or not state["terminal_reason"]:
            update["terminal_reason"] = decision.reason
    return update


def resolve_film(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    try:
        result = runtime.context.services.resolve_film(state)
    except Exception:
        return {
            "step_count": state["step_count"] + 1,
            "status": TerminalStatus.FAILED_SAFE,
            "terminal_reason": "Film identity resolution failed safely.",
            "events": event("run_failed", "Film identity could not be resolved."),
        }
    update: dict[str, Any] = {
        "step_count": state["step_count"] + 1,
        "film_id": result.film_id,
        "film_candidates": result.candidates,
        "events": event("film_resolved", "Film identity resolution completed."),
    }
    if result.film_id is None and not result.candidates:
        update.update(
            status=TerminalStatus.INSUFFICIENT_EVIDENCE,
            terminal_reason="No verified film identity was found.",
        )
    return update


def load_existing_evidence(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    try:
        evidence = runtime.context.services.load_existing_evidence(state)
        return {
            "existing_evidence_checked": True,
            "evidence": evidence,
            "step_count": state["step_count"] + 1,
            "events": event(
                "existing_evidence_loaded",
                f"Loaded {len(evidence)} existing evidence item(s).",
            ),
        }
    except Exception:
        failure = ToolFailure(
            tool=ToolName.LOAD_EXISTING_EVIDENCE,
            kind=FailureKind.UNAVAILABLE,
            retryable=False,
            public_message="Existing evidence could not be loaded.",
        )
        return {
            "existing_evidence_checked": True,
            "tool_failures": (failure,),
            "step_count": state["step_count"] + 1,
            "events": event("tool_failed", failure.public_message),
        }


def assess_evidence(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    try:
        sufficient = bool(runtime.context.services.evidence_is_sufficient(state))
    except Exception:
        return {
            "status": TerminalStatus.FAILED_SAFE,
            "terminal_reason": "Evidence assessment failed safely.",
            "events": event("run_failed", "Evidence could not be assessed safely."),
        }
    return {
        "evidence_sufficient": sufficient,
        "events": event(
            "evidence_assessed",
            "Evidence is sufficient." if sufficient else "More evidence is required.",
        ),
    }


def choose_tool(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    try:
        selected = runtime.context.services.choose_tool(state, state["allowed_tools"])
        if not isinstance(selected, ToolName):
            raise TypeError("The planner returned an invalid tool name.")
        if selected not in state["allowed_tools"]:
            raise ValueError("The planner selected a tool outside the policy-approved set.")
        return {
            "selected_tool": selected,
            "tool_authorised": False,
            "planning_calls": state["planning_calls"] + 1,
            "step_count": state["step_count"] + 1,
            "events": event("research_planned", "A bounded research action was proposed."),
        }
    except Exception:
        return {
            "planning_calls": state["planning_calls"] + 1,
            "step_count": state["step_count"] + 1,
            "status": TerminalStatus.FAILED_SAFE,
            "terminal_reason": "The research planner returned an invalid action.",
            "events": event("run_failed", "The research plan was invalid."),
        }


def authorise_tool(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    if state["status"] is not TerminalStatus.RUNNING:
        return {"tool_authorised": False}
    selected = state["selected_tool"]
    if selected is None:
        return {
            "status": TerminalStatus.FAILED_SAFE,
            "terminal_reason": "No tool was selected for authorisation.",
            "events": event("run_failed", "No valid research action was selected."),
        }
    # The policy authorised this planning turn before the planner call incremented
    # its counter. Reconstruct that pre-call counter so the final permitted planner
    # call may execute one tool without opening an extra planning turn afterwards.
    authorisation_state = dict(_contract_state(state))
    authorisation_state["planning_calls"] = max(0, state["planning_calls"] - 1)
    authorisation = authorise_tool_request(
        cast(ResearchState, authorisation_state),
        ToolRequest(selected, ActionOrigin.MODEL_PLANNER),
        runtime.context.budgets,
    )
    return {
        "tool_authorised": authorisation.allowed,
        "decision_reason": authorisation.reason,
        "events": event(
            "tool_authorised" if authorisation.allowed else "tool_denied",
            "The proposed research action was authorised."
            if authorisation.allowed
            else "The proposed research action was denied.",
        ),
    }


def execute_tool(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    selected = state["selected_tool"]
    if selected is None or not state["tool_authorised"]:
        return {
            "status": TerminalStatus.FAILED_SAFE,
            "terminal_reason": "An unauthorised tool reached execution.",
            "events": event("run_failed", "An unauthorised research action was blocked."),
        }

    try:
        observation = runtime.context.services.run_tool(state, selected)
    except Exception:
        observation = None

    update: dict[str, Any] = {
        "attempted_tools": (selected,),
        "external_tool_calls": state["external_tool_calls"] + 1,
        "step_count": state["step_count"] + 1,
        "selected_tool": None,
        "tool_authorised": False,
    }
    if observation is None:
        failure = ToolFailure(
            tool=selected,
            kind=FailureKind.UNAVAILABLE,
            retryable=False,
            public_message="The research provider was unavailable.",
        )
        update.update(
            tool_failures=(failure,),
            events=event("tool_failed", failure.public_message),
        )
        return update

    update["evidence"] = observation.evidence
    if observation.failure is not None:
        update["tool_failures"] = (observation.failure,)
        update["events"] = event("tool_failed", observation.failure.public_message)
    else:
        update["events"] = event(
            "tool_completed",
            f"Research returned {len(observation.evidence)} evidence item(s).",
        )
    return update


def synthesise(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    try:
        result = runtime.context.services.synthesise(state)
    except Exception:
        return {
            "synthesis_calls": state["synthesis_calls"] + 1,
            "step_count": state["step_count"] + 1,
            "status": TerminalStatus.FAILED_SAFE,
            "terminal_reason": "Study synthesis failed safely.",
            "events": event("run_failed", "The study could not be generated safely."),
        }
    return {
        "draft": result.draft,
        "draft_available": True,
        "quality_passed": None,
        "synthesis_calls": state["synthesis_calls"] + 1,
        "step_count": state["step_count"] + 1,
        "events": event("study_drafted", "The structured study draft was generated."),
    }


def validate(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    try:
        result = runtime.context.services.validate(state)
        return {
            "quality_passed": result.passed,
            "quality": result.report,
            "events": event(
                "quality_checked",
                "The quality gate passed." if result.passed else "The quality gate failed.",
            ),
        }
    except Exception:
        return {
            "quality_passed": False,
            "quality": {"status": "invalid", "issues": ["validation_failed"]},
            "events": event("quality_checked", "The draft failed deterministic validation."),
        }


def repair(
    state: ResearchGraphState,
    runtime: Runtime[ResearchGraphContext],
) -> dict[str, Any]:
    try:
        result = runtime.context.services.repair(state)
    except Exception:
        return {
            "repair_calls": state["repair_calls"] + 1,
            "step_count": state["step_count"] + 1,
            "status": TerminalStatus.FAILED_SAFE,
            "terminal_reason": "The bounded repair failed safely.",
            "events": event("run_failed", "The study repair could not be completed safely."),
        }
    return {
        "draft": result.draft,
        "draft_available": True,
        "quality_passed": None,
        "repair_calls": state["repair_calls"] + 1,
        "step_count": state["step_count"] + 1,
        "events": event("study_repaired", "The single permitted repair was completed."),
    }


def needs_user(state: ResearchGraphState) -> dict[str, Any]:
    return {
        "terminal_reason": state["terminal_reason"] or "The user must select a film.",
        "events": event("film_needs_choice", "Choose one verified film to continue."),
    }


def complete(state: ResearchGraphState) -> dict[str, Any]:
    return {
        "terminal_reason": state["terminal_reason"] or "The study passed all checks.",
        "events": event("run_completed", "The evidence-grounded study is ready."),
    }


def insufficient_evidence(state: ResearchGraphState) -> dict[str, Any]:
    return {
        "terminal_reason": state["terminal_reason"] or "Evidence was insufficient.",
        "events": event("run_failed", "The available evidence cannot support this study."),
    }


def failed_safe(state: ResearchGraphState) -> dict[str, Any]:
    return {
        "status": TerminalStatus.FAILED_SAFE,
        "terminal_reason": state["terminal_reason"] or "The run failed safely.",
        "events": event("run_failed", "The research run stopped at a safety boundary."),
    }
