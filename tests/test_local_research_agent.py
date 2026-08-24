from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from app.backend.criticism import ReviewSource
from app.backend.evidence import EvidencePacket
from app.backend.local_research_agent import (
    AcquiredSources,
    LocalAttributedSourceAcquirer,
    LocalResearchGraphServices,
)
from app.backend.research_agent_contract import ResearchBudgets, TerminalStatus, ToolName, ToolPlan
from app.backend.research_graph import (
    ResearchGraphContext,
    ResearchGraphState,
    build_research_graph,
    initial_research_state,
)
from app.backend.study_observability import StudyTrace
from app.backend.study_service import DeepSeekStudyService, StudyGenerationError


FILM = {
    "title": "Example Film",
    "year": 2024,
    "credits": {"directors": ["Example Director"]},
}
FOCUS = "How do framing, eyelines and editing organise uncertainty?"
THEORY = {
    "passages": [
        {
            "title": "Framing Theory",
            "page": 12,
            "language": "en",
            "excerpt": (
                "Framing, eyelines and editing can organise uncertainty through repeatable spatial "
                "relations that a filmmaker can log and compare."
            ),
        }
    ],
    "method": "hybrid_rrf",
    "candidate_count": 10,
}


def review(source_id: str = "R1", provider: str = "Guardian") -> ReviewSource:
    return ReviewSource(
        source_id=source_id,
        provider=provider,
        review_id=f"review-{source_id}",
        title="Attributed review",
        summary=(
            "The critic reports that framing, eyelines and editing organise uncertainty and group "
            "relations, offering details that should be checked during close viewing."
        ),
        author="A Critic",
        url=f"https://example.com/{source_id}",
        language="en",
    )


def packet(reviews: list[ReviewSource]) -> EvidencePacket:
    return EvidencePacket.from_retrieval(
        FILM,
        THEORY,
        FOCUS,
        reviews=reviews,
    )


@dataclass
class RecordingAcquirer:
    outcomes: list[Any] = field(default_factory=list)
    calls: list[ToolName] = field(default_factory=list)

    def status(self) -> dict[str, dict[str, Any]]:
        return {
            tool.value: {"provider": tool.value, "state": "ready"}
            for tool in (
                ToolName.FETCH_GUARDIAN_REVIEWS,
                ToolName.FETCH_DOUBAN_REVIEWS,
                ToolName.FETCH_LETTERBOXD_REVIEWS,
                ToolName.SEARCH_YOUTUBE_RESOURCES,
            )
        }

    def acquire(self, tool: ToolName, film: dict[str, Any]) -> AcquiredSources:
        self.calls.append(tool)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return cast(AcquiredSources, outcome)


@dataclass
class RecordingStudyService:
    plans: list[ToolName] = field(default_factory=list)
    planner_calls: list[dict[str, Any]] = field(default_factory=list)
    generation_calls: int = 0

    def plan_research_tool(self, **values: Any) -> ToolPlan:
        self.planner_calls.append(values)
        selected = self.plans.pop(0)
        return ToolPlan(
            selected,
            "test-planner",
            prompt_tokens=20,
            completion_tokens=2,
            total_tokens=22,
        )

    def generate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.generation_calls += 1
        trace = kwargs["trace"]
        trace.increment_count("model_calls")
        trace.increment_count("total_tokens", 100)
        trace.finish("completed")
        return {
            "title": "A bounded study",
            "quality": {"status": "passed", "score": 1.0},
            "observability": trace.snapshot(),
        }


def services(
    *,
    existing_reviews: list[ReviewSource],
    acquirer: RecordingAcquirer,
    study: RecordingStudyService,
) -> LocalResearchGraphServices:
    def prepare(*args: Any, **kwargs: Any) -> dict[str, Any]:
        current_packet = packet(existing_reviews)
        return {
            "film": FILM,
            "claims": [],
            "reviews": list(existing_reviews),
            "videos": [],
            "reading": THEORY,
            "packet": current_packet,
            "trace": kwargs.get("trace") or StudyTrace(),
        }

    return LocalResearchGraphServices(
        detail=lambda film_id: {"film": FILM},
        prepare=prepare,
        acquirer=cast(Any, acquirer),
        study_service=cast(Any, study),
    )


def run_agent(adapter: LocalResearchGraphServices) -> ResearchGraphState:
    graph = build_research_graph()
    state = initial_research_state(
        run_id="local-agent-test",
        user_id="local-owner",
        question=FOCUS,
        film_query="Example Film (2024)",
        film_id="example:2024",
    )
    return cast(
        ResearchGraphState,
        graph.invoke(
            state,
            context=ResearchGraphContext(
                services=adapter,
                budgets=ResearchBudgets(
                    max_graph_steps=8,
                    max_planning_calls=2,
                    max_external_tool_calls=2,
                ),
            ),
            config={"recursion_limit": 64},
        ),
    )


def test_letterboxd_tool_uses_public_adapter_when_official_credentials_are_absent() -> None:
    class Adapter:
        def __init__(self, provider: str, *, configured: bool = False) -> None:
            self.provider = provider
            self.configured = configured
            self.calls = 0

        def status(self) -> dict[str, Any]:
            return {
                "provider": self.provider,
                "state": "ready" if self.configured else "credentials_required",
                "configured": self.configured,
            }

        def fetch_reviews(self, film: dict[str, Any]):
            self.calls += 1
            return "provider-id", film["title"], [review(provider=self.provider)]

    class PublicAdapter(Adapter):
        def status(self) -> dict[str, Any]:
            return {"provider": self.provider, "state": "ready", "configured": True}

    official = Adapter("Letterboxd API")
    public = PublicAdapter("Letterboxd public web")
    passive = PublicAdapter("Passive provider")
    acquirer = LocalAttributedSourceAcquirer(
        douban=cast(Any, passive),
        guardian=cast(Any, passive),
        letterboxd=cast(Any, official),
        letterboxd_web=cast(Any, public),
        youtube=cast(Any, passive),
        bilibili=cast(Any, passive),
    )

    acquired = acquirer.acquire(ToolName.FETCH_LETTERBOXD_REVIEWS, FILM)

    assert official.calls == 0
    assert public.calls == 1
    assert acquired.provider == "Letterboxd public web"
    assert len(acquired.reviews) == 1


def test_sufficient_existing_packet_skips_planner_and_external_tools() -> None:
    acquirer = RecordingAcquirer()
    study = RecordingStudyService()
    adapter = services(existing_reviews=[review()], acquirer=acquirer, study=study)

    result = run_agent(adapter)

    assert result["status"] is TerminalStatus.COMPLETE
    assert result["external_tool_calls"] == 0
    assert result["planning_calls"] == 0
    assert acquirer.calls == []
    assert study.planner_calls == []
    assert study.generation_calls == 1


def test_sparse_packet_acquires_one_source_then_uses_unchanged_synthesis() -> None:
    private_review = review().model_copy(
        update={"summary": review().summary + " PRIVATE_REVIEW_TEXT"}
    )
    acquirer = RecordingAcquirer(
        outcomes=[
            AcquiredSources(
                provider="Guardian",
                reviews=(private_review,),
            )
        ]
    )
    study = RecordingStudyService(plans=[ToolName.FETCH_GUARDIAN_REVIEWS])
    adapter = services(existing_reviews=[], acquirer=acquirer, study=study)

    result = run_agent(adapter)
    metrics = adapter.safe_metrics("local-agent-test")

    assert result["status"] is TerminalStatus.COMPLETE
    assert result["external_tool_calls"] == 1
    assert result["planning_calls"] == 1
    assert acquirer.calls == [ToolName.FETCH_GUARDIAN_REVIEWS]
    assert metrics["acquired_reviews"] == 1
    assert metrics["acquired_videos"] == 0
    assert metrics["initial_packet_quality"]["status"] == "limited"
    assert metrics["packet_quality"]["status"] == "passed"
    assert metrics["packet_fingerprint"] != metrics["initial_packet_fingerprint"]
    assert len(adapter.private_packet("local-agent-test").attributed_sources) == 1
    assert [
        (item["tool"], item["status"]) for item in metrics["tool_attempts"]
    ] == [("fetch_guardian_reviews", "completed")]
    assert metrics["tool_attempts"][0]["duration_seconds"] >= 0
    assert metrics["planner_total_tokens"] == 22
    assert len(metrics["planner_latency_seconds"]) == 1
    assert metrics["planner_latency_seconds"][0] >= 0
    assert metrics["study_observability"]["counts"]["total_tokens"] == 122
    assert "PRIVATE_REVIEW_TEXT" not in str(metrics)


def test_unavailable_provider_falls_back_once_within_candidate_budget() -> None:
    acquirer = RecordingAcquirer(
        outcomes=[
            RuntimeError("provider unavailable"),
            AcquiredSources(provider="Letterboxd", reviews=(review("R2", "Letterboxd"),)),
        ]
    )
    study = RecordingStudyService(
        plans=[
            ToolName.FETCH_GUARDIAN_REVIEWS,
            ToolName.FETCH_LETTERBOXD_REVIEWS,
        ]
    )
    adapter = services(existing_reviews=[], acquirer=acquirer, study=study)

    result = run_agent(adapter)

    assert result["status"] is TerminalStatus.COMPLETE
    assert result["external_tool_calls"] == 2
    assert result["planning_calls"] == 2
    assert acquirer.calls == [
        ToolName.FETCH_GUARDIAN_REVIEWS,
        ToolName.FETCH_LETTERBOXD_REVIEWS,
    ]
    assert len(result["tool_failures"]) == 1
    tool_attempts = adapter.safe_metrics("local-agent-test")["tool_attempts"]
    assert [(item["tool"], item["status"]) for item in tool_attempts] == [
        ("fetch_guardian_reviews", "failed"),
        ("fetch_letterboxd_reviews", "completed"),
    ]
    assert all(item["duration_seconds"] >= 0 for item in tool_attempts)
    assert study.generation_calls == 1


def test_deepseek_planner_sends_aggregate_gap_not_evidence_text() -> None:
    captured: dict[str, Any] = {}

    class Settings:
        def effective_secret(self, connector_id: str) -> str:
            return "test-deepseek-key"

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        captured.update({"url": url, "payload": payload, "key": key})
        return {
            "model": "planner-test",
            "choices": [{"message": {"content": '{"tool":"fetch_guardian_reviews"}'}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 4, "total_tokens": 34},
        }

    service = DeepSeekStudyService(cast(Any, Settings()), transport=transport)
    plan = service.plan_research_tool(
        film=FILM,
        focus=FOCUS,
        packet_summary={
            "status": "limited",
            "issues": ["film_specific_evidence_sparse", "PRIVATE_ISSUE_CODE"],
            "sufficiency": {"state": "sparse", "film_specific_sources": 0},
            "diversity": {"evidence_type_count": 1, "attributed_origin_count": 0},
            "content": "PRIVATE_EVIDENCE_MUST_NOT_REACH_PLANNER",
        },
        allowed_tools=(
            ToolName.FETCH_GUARDIAN_REVIEWS,
            ToolName.FETCH_LETTERBOXD_REVIEWS,
        ),
        provider_states={
            ToolName.FETCH_GUARDIAN_REVIEWS.value: {
                "provider": "PRIVATE_PROVIDER_NAME",
                "state": "ready",
                "secret": "PRIVATE_PROVIDER_SECRET",
            }
        },
    )

    serialised = str(captured["payload"])
    assert plan.tool is ToolName.FETCH_GUARDIAN_REVIEWS
    assert plan.total_tokens == 34
    assert "PRIVATE_EVIDENCE_MUST_NOT_REACH_PLANNER" not in serialised
    assert "PRIVATE_PROVIDER_SECRET" not in serialised
    assert "PRIVATE_PROVIDER_NAME" not in serialised
    assert "PRIVATE_ISSUE_CODE" not in serialised
    assert "film_specific_evidence_sparse" in serialised


def test_deepseek_planner_rejects_tool_outside_policy_set() -> None:
    class Settings:
        def effective_secret(self, connector_id: str) -> str:
            return "test-deepseek-key"

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": '{"tool":"fetch_douban_reviews"}'}}]
        }

    service = DeepSeekStudyService(cast(Any, Settings()), transport=transport)
    with pytest.raises(StudyGenerationError, match="outside the approved set"):
        service.plan_research_tool(
            film=FILM,
            focus=FOCUS,
            packet_summary={"status": "limited"},
            allowed_tools=(ToolName.FETCH_GUARDIAN_REVIEWS,),
            provider_states={},
        )
