from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.backend.research_graph.context import ResearchGraphContext
from app.backend.research_graph.nodes import (
    assess_evidence,
    authorise_tool,
    choose_tool,
    complete,
    execute_tool,
    failed_safe,
    insufficient_evidence,
    load_existing_evidence,
    needs_user,
    normalise_question,
    policy,
    repair,
    resolve_film,
    synthesise,
    validate,
)
from app.backend.research_graph.routing import route_after_authorisation, route_policy
from app.backend.research_graph.state import ResearchGraphState


def build_research_graph(*, checkpointer: Any = None) -> Any:
    """Compile FirstRoll's bounded research Agent.

    Authentication, ownership checks, quota reservation and credentials deliberately
    remain outside the graph and must be enforced by the invoking application.
    """

    builder = StateGraph(ResearchGraphState, context_schema=ResearchGraphContext)
    builder.add_node("normalise_question", normalise_question)
    builder.add_node("policy", policy)
    builder.add_node("resolve_film", resolve_film)
    builder.add_node("load_existing_evidence", load_existing_evidence)
    builder.add_node("assess_evidence", assess_evidence)
    builder.add_node("choose_tool", choose_tool)
    builder.add_node("authorise_tool", authorise_tool)
    builder.add_node("execute_tool", execute_tool)
    builder.add_node("synthesise", synthesise)
    builder.add_node("validate", validate)
    builder.add_node("repair", repair)
    builder.add_node("needs_user", needs_user)
    builder.add_node("complete", complete)
    builder.add_node("insufficient_evidence", insufficient_evidence)
    builder.add_node("failed_safe", failed_safe)

    builder.add_edge(START, "normalise_question")
    builder.add_edge("normalise_question", "policy")
    builder.add_conditional_edges(
        "policy",
        route_policy,
        {
            "resolve_film": "resolve_film",
            "needs_user": "needs_user",
            "load_existing_evidence": "load_existing_evidence",
            "choose_tool": "choose_tool",
            "synthesise": "synthesise",
            "repair": "repair",
            "complete": "complete",
            "insufficient_evidence": "insufficient_evidence",
            "failed_safe": "failed_safe",
            "stop": END,
        },
    )
    builder.add_edge("resolve_film", "policy")
    builder.add_edge("load_existing_evidence", "assess_evidence")
    builder.add_edge("assess_evidence", "policy")
    builder.add_edge("choose_tool", "authorise_tool")
    builder.add_conditional_edges(
        "authorise_tool",
        route_after_authorisation,
        {"execute_tool": "execute_tool", "policy": "policy"},
    )
    builder.add_edge("execute_tool", "assess_evidence")
    builder.add_edge("synthesise", "validate")
    builder.add_edge("validate", "policy")
    builder.add_edge("repair", "validate")
    builder.add_edge("needs_user", END)
    builder.add_edge("complete", END)
    builder.add_edge("insufficient_evidence", END)
    builder.add_edge("failed_safe", END)
    return builder.compile(checkpointer=checkpointer, name="firstroll_research_agent")
