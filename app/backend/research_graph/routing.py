from __future__ import annotations

from app.backend.research_agent_contract import NextAction, TerminalStatus
from app.backend.research_graph.state import ResearchGraphState


ACTION_ROUTES = {
    NextAction.RESOLVE_FILM: "resolve_film",
    NextAction.ASK_USER: "needs_user",
    NextAction.LOAD_EXISTING_EVIDENCE: "load_existing_evidence",
    NextAction.CHOOSE_RESEARCH_TOOL: "choose_tool",
    NextAction.SYNTHESISE: "synthesise",
    NextAction.REPAIR: "repair",
    NextAction.COMPLETE: "complete",
    NextAction.RETURN_INSUFFICIENT_EVIDENCE: "insufficient_evidence",
    NextAction.FAIL_SAFE: "failed_safe",
    NextAction.STOP: "stop",
}


def route_policy(state: ResearchGraphState) -> str:
    action = state.get("next_action")
    if action is None:
        return "failed_safe"
    return ACTION_ROUTES.get(action, "failed_safe")


def route_after_authorisation(state: ResearchGraphState) -> str:
    if state["status"] is not TerminalStatus.RUNNING:
        return "policy"
    return "execute_tool" if state["tool_authorised"] else "policy"
