from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, cast

import pytest

from app.backend.criticism import ReviewSource
from app.backend.evidence import EvidencePacket
from app.backend.local_research_agent import (
    AcquiredSources,
    LocalAttributedSourceAcquirer,
    LocalResearchGraphServices,
)
from app.backend.research_agent_contract import (
    EvidenceGap,
    ResearchBudgets,
    TerminalStatus,
    ToolName,
    ToolPlan,
)
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
    domain = re.sub(r"[^a-z0-9]+", "-", provider.casefold()).strip("-")
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
        url=f"https://{domain}.example/{source_id}",
        language="en",
    )


def scholarly_review(source_id: str = "R2") -> ReviewSource:
    return review(source_id, "Crossref scholarship").model_copy(
        update={
            "summary": (
                "A scholarly abstract connects editing rhythm to spatial uncertainty and compares "
                "how recurring cuts redistribute attention across the frame."
            )
        }
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
                ToolName.FETCH_CROSSREF_RESEARCH,
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
    repair_calls: int = 0

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

    def generate_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.generation_calls += 1
        trace = kwargs["trace"]
        trace.increment_count("model_calls")
        trace.increment_count("total_tokens", 100)
        trace.finish("completed")
        return {
            "title": "A bounded study",
            "sections": [{"section": 1}],
            "quality": {"status": "passed", "score": 1.0},
            "observability": trace.snapshot(),
        }

    def repair_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.repair_calls += 1
        return self.generate_once(*args, **kwargs)


def services(
    *,
    existing_reviews: list[ReviewSource],
    acquirer: RecordingAcquirer,
    study: RecordingStudyService,
    planner_mode: str = "model",
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
        planner_mode=cast(Any, planner_mode),
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
        crossref=cast(Any, passive),
        youtube=cast(Any, passive),
        bilibili=cast(Any, passive),
    )

    acquired = acquirer.acquire(ToolName.FETCH_LETTERBOXD_REVIEWS, FILM)

    assert official.calls == 0
    assert public.calls == 1
    assert acquired.provider == "Letterboxd public web"
    assert len(acquired.reviews) == 1


def test_crossref_tool_reuses_the_bounded_scholarship_adapter() -> None:
    class Adapter:
        def __init__(self, provider: str) -> None:
            self.provider = provider
            self.calls = 0

        def status(self) -> dict[str, Any]:
            return {
                "provider": self.provider,
                "state": "ready",
                "configured": True,
                "official": True,
            }

        def fetch_reviews(self, film: dict[str, Any]):
            self.calls += 1
            return "provider-id", film["title"], [scholarly_review()]

    crossref = Adapter("Crossref scholarship")
    passive = Adapter("Passive provider")
    acquirer = LocalAttributedSourceAcquirer(
        douban=cast(Any, passive),
        guardian=cast(Any, passive),
        letterboxd=cast(Any, passive),
        letterboxd_web=cast(Any, passive),
        crossref=cast(Any, crossref),
        youtube=cast(Any, passive),
        bilibili=cast(Any, passive),
    )

    acquired = acquirer.acquire(ToolName.FETCH_CROSSREF_RESEARCH, FILM)

    assert crossref.calls == 1
    assert acquired.provider == "Crossref scholarship"
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


def test_frozen_packet_synthesis_does_not_repeat_packet_preparation() -> None:
    prepare_calls = 0
    frozen = packet([review()])

    def prepare(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal prepare_calls
        prepare_calls += 1
        raise AssertionError("Frozen synthesis must not repeat packet preparation.")

    adapter = LocalResearchGraphServices(
        detail=lambda film_id: {"film": FILM},
        prepare=prepare,
        acquirer=cast(Any, RecordingAcquirer()),
        study_service=cast(Any, RecordingStudyService()),
        packet_override=frozen,
    )

    result = run_agent(adapter)

    assert result["status"] is TerminalStatus.COMPLETE
    assert prepare_calls == 0
    assert (
        adapter.safe_metrics("local-agent-test")["initial_packet_fingerprint"]
        == (adapter.safe_metrics("local-agent-test")["packet_fingerprint"])
    )


def test_agent_owns_two_repairs_and_can_pass_on_the_final_attempt() -> None:
    class RetryStudyService(RecordingStudyService):
        def __init__(self) -> None:
            super().__init__()
            self.outcomes = ["insufficient_evidence", "insufficient_evidence", "passed"]

        def _attempt(self, trace: StudyTrace) -> dict[str, Any]:
            status = self.outcomes.pop(0)
            trace.increment_count("model_calls")
            trace.increment_count("total_tokens", 100)
            trace.finish("completed")
            return {
                "title": "A bounded study",
                "sections": [{"section": 1}],
                "quality": {"status": status, "score": 1.0 if status == "passed" else 0.6},
                "observability": trace.snapshot(),
            }

        def generate_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.generation_calls += 1
            return self._attempt(kwargs["trace"])

        def repair_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.repair_calls += 1
            return self._attempt(kwargs["trace"])

    acquirer = RecordingAcquirer()
    study = RetryStudyService()
    adapter = services(existing_reviews=[review()], acquirer=acquirer, study=study)

    result = run_agent(adapter)
    metrics = adapter.safe_metrics("local-agent-test")

    assert result["status"] is TerminalStatus.COMPLETE
    assert result["repair_calls"] == 2
    assert study.generation_calls == 1
    assert study.repair_calls == 2
    assert [item["kind"] for item in metrics["study_attempts"]] == [
        "initial",
        "repair",
        "repair",
    ]
    assert metrics["repair_attempts"] == 2
    assert metrics["study_observability"]["counts"]["model_calls"] == 3
    assert metrics["study_observability"]["counts"]["repair_attempts"] == 2


def test_agent_uses_structural_patch_instead_of_full_regeneration() -> None:
    class StructuralRepairService(RecordingStudyService):
        def __init__(self) -> None:
            super().__init__()
            self.structural_repair_calls = 0

        def generate_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.generation_calls += 1
            trace = kwargs["trace"]
            trace.increment_count("model_calls")
            trace.increment_count("total_tokens", 100)
            trace.finish("failed")
            raise StudyGenerationError(
                "synthetic invalid citation",
                category="citation_validation",
                repair_candidate={"private_draft": "PRIVATE_GENERATED_PROSE"},
                repair_paths=("sections.0.source_ids",),
            )

        def repair_invalid_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.structural_repair_calls += 1
            assert args[0] == {"private_draft": "PRIVATE_GENERATED_PROSE"}
            assert args[1] == ("sections.0.source_ids",)
            trace = kwargs["trace"]
            trace.increment_count("model_calls")
            trace.increment_count("total_tokens", 25)
            trace.increment_count("structural_repair_attempts")
            trace.finish("completed")
            return {
                "title": "A bounded study",
                "sections": [{"section": 1}],
                "quality": {"status": "passed", "score": 1.0},
                "observability": trace.snapshot(),
            }

        def repair_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("A parseable invalid response must use structural repair.")

    study = StructuralRepairService()
    adapter = services(
        existing_reviews=[review()],
        acquirer=RecordingAcquirer(),
        study=study,
    )

    result = run_agent(adapter)
    metrics = adapter.safe_metrics("local-agent-test")

    assert result["status"] is TerminalStatus.COMPLETE
    assert result["repair_calls"] == 1
    assert study.generation_calls == 1
    assert study.structural_repair_calls == 1
    assert [attempt["strategy"] for attempt in metrics["study_attempts"]] == [
        "initial_generation",
        "targeted_structural_repair",
    ]
    assert metrics["study_attempts"][0]["failure_category"] == "citation_validation"
    assert all(attempt["duration_seconds"] >= 0 for attempt in metrics["study_attempts"])
    assert metrics["study_observability"]["counts"]["model_calls"] == 2
    assert metrics["study_observability"]["counts"]["total_tokens"] == 125
    assert metrics["study_observability"]["counts"]["structural_repair_attempts"] == 1
    assert "PRIVATE_GENERATED_PROSE" not in str(metrics)


def test_agent_stops_insufficient_after_two_failed_repairs() -> None:
    class FailingStudyService(RecordingStudyService):
        def _attempt(self, trace: StudyTrace) -> dict[str, Any]:
            trace.increment_count("model_calls")
            trace.finish("completed")
            return {
                "title": "Still weak",
                "sections": [{"section": 1}],
                "quality": {"status": "insufficient_evidence", "score": 0.6},
                "observability": trace.snapshot(),
            }

        def generate_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.generation_calls += 1
            return self._attempt(kwargs["trace"])

        def repair_once(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.repair_calls += 1
            return self._attempt(kwargs["trace"])

    study = FailingStudyService()
    adapter = services(
        existing_reviews=[review()],
        acquirer=RecordingAcquirer(),
        study=study,
    )

    result = run_agent(adapter)

    assert result["status"] is TerminalStatus.INSUFFICIENT_EVIDENCE
    assert result["repair_calls"] == 2
    assert study.generation_calls == 1
    assert study.repair_calls == 2


def test_sparse_packet_acquires_independent_sources_then_synthesises() -> None:
    private_review = review().model_copy(
        update={"summary": review().summary + " PRIVATE_REVIEW_TEXT"}
    )
    research_review = scholarly_review()
    acquirer = RecordingAcquirer(
        outcomes=[
            AcquiredSources(
                provider="Guardian",
                reviews=(private_review,),
            ),
            AcquiredSources(
                provider="Crossref scholarship",
                reviews=(research_review,),
            ),
        ]
    )
    study = RecordingStudyService(
        plans=[ToolName.FETCH_GUARDIAN_REVIEWS, ToolName.FETCH_CROSSREF_RESEARCH]
    )
    adapter = services(existing_reviews=[], acquirer=acquirer, study=study)

    result = run_agent(adapter)
    metrics = adapter.safe_metrics("local-agent-test")

    assert result["status"] is TerminalStatus.COMPLETE
    assert result["external_tool_calls"] == 2
    assert result["planning_calls"] == 2
    assert acquirer.calls == [
        ToolName.FETCH_GUARDIAN_REVIEWS,
        ToolName.FETCH_CROSSREF_RESEARCH,
    ]
    assert metrics["acquired_reviews"] == 2
    assert metrics["acquired_videos"] == 0
    assert metrics["initial_packet_quality"]["status"] == "limited"
    assert metrics["packet_quality"]["status"] == "passed"
    assert metrics["packet_fingerprint"] != metrics["initial_packet_fingerprint"]
    assert len(adapter.private_packet("local-agent-test").attributed_sources) == 2
    assert metrics["agent_evidence"]["agent_status"] == "sufficient"
    assert metrics["agent_evidence"]["agent_diversity"]["independent_film_origins"] == 2
    assert [(item["tool"], item["status"]) for item in metrics["tool_attempts"]] == [
        ("fetch_guardian_reviews", "completed"),
        ("fetch_crossref_research", "completed"),
    ]
    assert metrics["tool_attempts"][0]["duration_seconds"] >= 0
    assert metrics["planner_total_tokens"] == 44
    assert len(metrics["planner_latency_seconds"]) == 2
    assert metrics["planner_latency_seconds"][0] >= 0
    assert metrics["study_observability"]["counts"]["total_tokens"] == 144
    assert "PRIVATE_REVIEW_TEXT" not in str(metrics)


def test_deterministic_gap_router_is_a_no_model_planner_baseline() -> None:
    acquirer = RecordingAcquirer(
        outcomes=[
            AcquiredSources(provider="Guardian", reviews=(review(),)),
            AcquiredSources(
                provider="Crossref scholarship",
                reviews=(scholarly_review(),),
            ),
        ]
    )
    study = RecordingStudyService()
    adapter = services(
        existing_reviews=[],
        acquirer=acquirer,
        study=study,
        planner_mode="deterministic",
    )

    result = run_agent(adapter)
    metrics = adapter.safe_metrics("local-agent-test")

    assert result["status"] is TerminalStatus.COMPLETE
    assert acquirer.calls == [
        ToolName.FETCH_GUARDIAN_REVIEWS,
        ToolName.FETCH_CROSSREF_RESEARCH,
    ]
    assert study.planner_calls == []
    assert metrics["planner_calls"] == 0
    assert metrics["planning_turns"] == 2
    assert metrics["planning_decisions"] == [
        {
            "strategy": "deterministic_gap_router",
            "tool": "fetch_guardian_reviews",
            "target_gap": "film_specific_evidence",
        },
        {
            "strategy": "deterministic_gap_router",
            "tool": "fetch_crossref_research",
            "target_gap": "independent_origins",
        },
    ]
    assert metrics["study_observability"]["counts"]["model_calls"] == 1


def test_no_addressable_provider_stops_insufficient_without_external_call() -> None:
    class UnavailableAcquirer(RecordingAcquirer):
        def status(self) -> dict[str, dict[str, Any]]:
            return {
                tool.value: {"provider": tool.value, "state": "unavailable"}
                for tool in (
                    ToolName.FETCH_GUARDIAN_REVIEWS,
                    ToolName.FETCH_DOUBAN_REVIEWS,
                    ToolName.FETCH_LETTERBOXD_REVIEWS,
                    ToolName.FETCH_CROSSREF_RESEARCH,
                    ToolName.SEARCH_YOUTUBE_RESOURCES,
                )
            }

    acquirer = UnavailableAcquirer()
    study = RecordingStudyService()
    adapter = services(
        existing_reviews=[],
        acquirer=acquirer,
        study=study,
        planner_mode="deterministic",
    )

    result = run_agent(adapter)

    assert result["status"] is TerminalStatus.INSUFFICIENT_EVIDENCE
    assert result["planning_calls"] == 1
    assert result["external_tool_calls"] == 0
    assert acquirer.calls == []
    assert study.generation_calls == 0
    assert result["terminal_reason"] == (
        "No remaining provider can address the measured evidence gap."
    )


def test_one_successful_origin_after_provider_failure_stops_insufficient() -> None:
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

    assert result["status"] is TerminalStatus.INSUFFICIENT_EVIDENCE
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
    assert study.generation_calls == 0


def test_deepseek_planner_sends_aggregate_gap_not_evidence_text() -> None:
    captured: dict[str, Any] = {}

    class Settings:
        def effective_secret(self, connector_id: str) -> str:
            return "test-deepseek-key"

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        captured.update({"url": url, "payload": payload, "key": key})
        return {
            "model": "planner-test",
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"target_gap":"film_specific_evidence",'
                            '"tool":"fetch_guardian_reviews"}'
                        )
                    }
                }
            ],
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
    assert plan.target_gap is EvidenceGap.FILM_SPECIFIC_EVIDENCE
    assert plan.total_tokens == 34
    assert "PRIVATE_EVIDENCE_MUST_NOT_REACH_PLANNER" not in serialised
    assert "PRIVATE_PROVIDER_SECRET" not in serialised
    assert "PRIVATE_PROVIDER_NAME" not in serialised
    assert "PRIVATE_ISSUE_CODE" not in serialised
    assert "film_specific_evidence_sparse" in serialised


def test_deepseek_planner_rejects_gap_outside_policy_set() -> None:
    class Settings:
        def effective_secret(self, connector_id: str) -> str:
            return "test-deepseek-key"

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"target_gap":"focus_relevance","tool":"fetch_guardian_reviews"}'
                        )
                    }
                }
            ]
        }

    service = DeepSeekStudyService(cast(Any, Settings()), transport=transport)
    with pytest.raises(StudyGenerationError, match="gap outside the approved set"):
        service.plan_research_tool(
            film=FILM,
            focus=FOCUS,
            packet_summary={
                "status": "passed",
                "agent_gaps": ["independent_origins"],
            },
            allowed_tools=(ToolName.FETCH_GUARDIAN_REVIEWS,),
            provider_states={},
        )


def test_deepseek_planner_stops_before_call_when_no_tool_can_address_gap() -> None:
    class Settings:
        def effective_secret(self, connector_id: str) -> str:
            return "test-deepseek-key"

    calls = 0

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {}

    service = DeepSeekStudyService(cast(Any, Settings()), transport=transport)
    with pytest.raises(StudyGenerationError, match="No remaining research tool"):
        service.plan_research_tool(
            film=FILM,
            focus=FOCUS,
            packet_summary={
                "status": "passed",
                "agent_gaps": ["evidence_class_diversity"],
            },
            allowed_tools=(ToolName.FETCH_GUARDIAN_REVIEWS,),
            provider_states={},
        )
    assert calls == 0


def test_deepseek_planner_rejects_tool_outside_policy_set() -> None:
    class Settings:
        def effective_secret(self, connector_id: str) -> str:
            return "test-deepseek-key"

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"target_gap":"film_specific_evidence","tool":"fetch_douban_reviews"}'
                        )
                    }
                }
            ]
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
