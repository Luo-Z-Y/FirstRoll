from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.backend.autonomous_agent import (
    AutonomousCompletionStatus,
    AutonomousFinisherBudgets,
    AutonomousStudyFinisher,
    AutonomousStudyResult,
    LocalAutonomousResearchAgent,
)
from app.backend.autonomous_study import audited_claim_paths, path_source_ids
from app.backend.research_agent_contract import TerminalStatus
from app.backend.study_service import StudyGenerationError
from tools.evaluate_agent_repair import synthetic_packet, valid_candidate


def audit(*, weak_paths: set[str] | None = None) -> dict[str, Any]:
    weak_paths = weak_paths or set()
    study = valid_candidate()
    items = []
    for path in audited_claim_paths(study):
        field = path.rsplit(".", 1)[-1]
        allowed_ids = path_source_ids(study, path)
        source_id = (
            sorted(source for source in allowed_ids if source.startswith("E"))[0]
            if field == "critic_reports"
            else sorted(source for source in allowed_ids if source.startswith("S"))[0]
            if field == "theory_explains"
            else sorted(allowed_ids)[0]
        )
        items.append(
            {
                "path": path,
                "label": (
                    "unsupported"
                    if path in weak_paths
                    else "directly_supported"
                    if field in {"critic_reports", "theory_explains"}
                    else "reasonable_interpretation"
                ),
                "source_ids": [source_id],
                "support_note": (
                    "The selected evidence supports this bounded classification without changing "
                    "the study's stated epistemic status."
                ),
            }
        )
    return {"items": items}


@dataclass
class Service:
    audits: list[Any]
    repaired: dict[str, Any] = field(default_factory=valid_candidate)
    coach: Any = field(default_factory=lambda: {"exercises": [{"safe": "private-runtime-only"}]})
    calls: list[str] = field(default_factory=list)

    @staticmethod
    def record(trace, *, tokens: int = 100) -> None:
        trace.increment_count("model_calls")
        trace.increment_count("total_tokens", tokens)
        trace.finish("completed")

    def audit_claims_once(self, study, *, evidence_packet, trace):
        self.calls.append("audit")
        outcome = self.audits.pop(0)
        self.record(trace)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def repair_audited_once(self, study, paths, *, evidence_packet, trace):
        self.calls.append("editor")
        self.record(trace, tokens=50)
        if isinstance(self.repaired, Exception):
            raise self.repaired
        return self.repaired

    def coach_filmmaker_once(self, study, claim_audit, *, evidence_packet, trace):
        self.calls.append("coach")
        self.record(trace, tokens=75)
        if isinstance(self.coach, Exception):
            raise self.coach
        return self.coach


def test_finisher_skips_editor_when_claim_audit_passes() -> None:
    service = Service(audits=[audit()])

    result = AutonomousStudyFinisher(service).run(valid_candidate(), synthetic_packet())

    assert result.status is AutonomousCompletionStatus.COMPLETE
    assert service.calls == ["audit", "coach"]
    assert result.coach is not None
    assert result.safe_metrics["counts"] == {
        "audit_calls": 1,
        "editor_calls": 0,
        "coach_calls": 1,
        "model_calls": 2,
        "total_tokens": 175,
    }


def test_finisher_edits_only_weak_path_then_requires_reaudit() -> None:
    weak = "sections.1.mechanism"
    service = Service(audits=[audit(weak_paths={weak}), audit()])

    result = AutonomousStudyFinisher(service).run(valid_candidate(), synthetic_packet())

    assert result.status is AutonomousCompletionStatus.COMPLETE
    assert service.calls == ["audit", "editor", "audit", "coach"]
    assert result.safe_metrics["counts"]["model_calls"] == 4
    assert [item["strategy"] for item in result.safe_metrics["attempts"]] == [
        "claim_audit",
        "targeted_claim_editor",
        "claim_reaudit",
        "filmmaker_coach",
    ]


def test_finisher_stops_when_too_many_claims_need_editing() -> None:
    weak = set(audited_claim_paths(valid_candidate())[:5])
    service = Service(audits=[audit(weak_paths=weak)])

    result = AutonomousStudyFinisher(service).run(valid_candidate(), synthetic_packet())

    assert result.status is AutonomousCompletionStatus.INSUFFICIENT_EVIDENCE
    assert service.calls == ["audit"]
    assert result.coach is None


def test_finisher_stops_when_reaudit_still_finds_weak_claim() -> None:
    weak = {"sections.1.mechanism"}
    service = Service(audits=[audit(weak_paths=weak), audit(weak_paths=weak)])

    result = AutonomousStudyFinisher(service).run(valid_candidate(), synthetic_packet())

    assert result.status is AutonomousCompletionStatus.INSUFFICIENT_EVIDENCE
    assert service.calls == ["audit", "editor", "audit"]
    assert result.coach is None


def test_finisher_stops_at_total_model_budget_before_coaching() -> None:
    service = Service(audits=[audit()])
    budgets = AutonomousFinisherBudgets(max_total_model_calls=1)

    result = AutonomousStudyFinisher(service, budgets).run(valid_candidate(), synthetic_packet())

    assert result.status is AutonomousCompletionStatus.BUDGET_EXHAUSTED
    assert service.calls == ["audit"]


def test_local_autonomous_runner_connects_research_to_private_finisher() -> None:
    class Graph:
        def invoke(self, state, *, context, config):
            return {
                **state,
                "status": TerminalStatus.COMPLETE,
                "draft": valid_candidate(),
                "terminal_reason": "Research complete.",
            }

    class ResearchServices:
        def safe_metrics(self, run_id):
            return {"run_id_hash": "safe-run"}

        def private_packet(self, run_id):
            return synthetic_packet()

    class Finisher:
        calls = 0

        def run(self, study, packet):
            self.calls += 1
            return AutonomousStudyResult(
                status=AutonomousCompletionStatus.COMPLETE,
                study=study,
                audit={"items": []},
                coach={"exercises": []},
                terminal_reason="Finished.",
                safe_metrics={"status": "complete"},
            )

    finisher = Finisher()
    runner = LocalAutonomousResearchAgent(
        ResearchServices(),
        finisher,
        graph_factory=Graph,
    )

    result = runner.run(
        run_id="private-run",
        user_id="local-owner",
        question="How does framing organise uncertainty?",
        film_query="Example Film",
        film_id="example:2024",
    )

    assert result.status == "complete"
    assert finisher.calls == 1
    assert result.coach == {"exercises": []}
    assert result.safe_metrics == {
        "research": {"run_id_hash": "safe-run"},
        "finisher": {"status": "complete"},
    }


def test_local_autonomous_runner_does_not_finish_failed_research() -> None:
    class Graph:
        def invoke(self, state, *, context, config):
            return {
                **state,
                "status": TerminalStatus.INSUFFICIENT_EVIDENCE,
                "draft": None,
                "terminal_reason": "Evidence remained insufficient.",
            }

    class ResearchServices:
        def safe_metrics(self, run_id):
            return {"status": "insufficient_evidence"}

    class Finisher:
        def run(self, study, packet):
            raise AssertionError("Failed research must not reach autonomous finishing.")

    runner = LocalAutonomousResearchAgent(
        ResearchServices(),
        Finisher(),
        graph_factory=Graph,
    )

    result = runner.run(
        run_id="private-run",
        user_id="local-owner",
        question="How does framing organise uncertainty?",
        film_query="Example Film",
        film_id="example:2024",
    )

    assert result.status == "insufficient_evidence"
    assert result.study is None
    assert result.safe_metrics["finisher"] is None


def test_finisher_safe_metrics_exclude_provider_exception_detail() -> None:
    service = Service(
        audits=[
            StudyGenerationError(
                "PRIVATE_AUDIT_OUTPUT",
                category="claim_audit_invalid",
            )
        ]
    )

    result = AutonomousStudyFinisher(service).run(valid_candidate(), synthetic_packet())

    assert result.status is AutonomousCompletionStatus.FAILED_SAFE
    assert result.safe_metrics["attempts"][0]["failure_category"] == "claim_audit_invalid"
    assert "PRIVATE_AUDIT_OUTPUT" not in str(result.safe_metrics)
