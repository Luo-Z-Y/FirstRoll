from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import monotonic
from typing import Any, Callable, cast

from app.backend.research_agent_contract import ResearchBudgets, TerminalStatus
from app.backend.research_graph import (
    ResearchGraphContext,
    ResearchGraphState,
    build_research_graph,
    initial_research_state,
)

from app.backend.autonomous_study import StudyClaimAudit, weak_claim_paths
from app.backend.evidence import EvidencePacket
from app.backend.study_observability import StudyTrace
from app.backend.study_service import DeepSeekStudyService, StudyGenerationError


class AutonomousCompletionStatus(StrEnum):
    COMPLETE = "complete"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BUDGET_EXHAUSTED = "budget_exhausted"
    FAILED_SAFE = "failed_safe"


@dataclass(frozen=True)
class AutonomousFinisherBudgets:
    max_audit_calls: int = 2
    max_editor_calls: int = 1
    max_coach_calls: int = 1
    max_total_model_calls: int = 4
    maximum_weak_paths: int = 4

    def __post_init__(self) -> None:
        values = (
            self.max_audit_calls,
            self.max_editor_calls,
            self.max_coach_calls,
            self.max_total_model_calls,
            self.maximum_weak_paths,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values
        ):
            raise ValueError("Autonomous finisher budgets must be non-negative integers.")
        if self.max_audit_calls < 1 or self.max_total_model_calls < 1:
            raise ValueError("Autonomous finishing requires at least one audit and one model call.")


@dataclass(frozen=True)
class AutonomousStudyResult:
    status: AutonomousCompletionStatus
    study: dict[str, Any]
    audit: dict[str, Any] | None
    coach: dict[str, Any] | None
    terminal_reason: str
    safe_metrics: dict[str, Any]


@dataclass(frozen=True)
class AutonomousResearchResult:
    status: str
    study: dict[str, Any] | None
    audit: dict[str, Any] | None
    coach: dict[str, Any] | None
    terminal_reason: str
    safe_metrics: dict[str, Any]


class LocalAutonomousResearchAgent:
    """Run bounded research synthesis and autonomous finishing without an HTTP route."""

    def __init__(
        self,
        services: Any,
        finisher: AutonomousStudyFinisher,
        research_budgets: ResearchBudgets = ResearchBudgets(),
        graph_factory: Callable[[], Any] = build_research_graph,
    ) -> None:
        self.services = services
        self.finisher = finisher
        self.research_budgets = research_budgets
        self.graph_factory = graph_factory

    def run(
        self,
        *,
        run_id: str,
        user_id: str,
        question: str,
        film_query: str,
        film_id: str | None = None,
    ) -> AutonomousResearchResult:
        state = initial_research_state(
            run_id=run_id,
            user_id=user_id,
            question=question,
            film_query=film_query,
            film_id=film_id,
        )
        final = cast(
            ResearchGraphState,
            self.graph_factory().invoke(
                state,
                context=ResearchGraphContext(
                    services=self.services,
                    budgets=self.research_budgets,
                    mode="full",
                ),
                config={"recursion_limit": 64},
            ),
        )
        research_metrics = self.services.safe_metrics(run_id)
        if final["status"] is not TerminalStatus.COMPLETE:
            return AutonomousResearchResult(
                status=final["status"].value,
                study=None,
                audit=None,
                coach=None,
                terminal_reason=str(final.get("terminal_reason") or "Research stopped safely."),
                safe_metrics={
                    "research": research_metrics,
                    "finisher": None,
                },
            )
        draft = final.get("draft")
        if not isinstance(draft, dict):
            return AutonomousResearchResult(
                status=AutonomousCompletionStatus.FAILED_SAFE.value,
                study=None,
                audit=None,
                coach=None,
                terminal_reason="Research completed without a private structured study.",
                safe_metrics={
                    "research": research_metrics,
                    "finisher": None,
                },
            )
        packet = self.services.private_packet(run_id)
        finished = self.finisher.run(draft, packet)
        return AutonomousResearchResult(
            status=finished.status.value,
            study=finished.study,
            audit=finished.audit,
            coach=finished.coach,
            terminal_reason=finished.terminal_reason,
            safe_metrics={
                "research": research_metrics,
                "finisher": finished.safe_metrics,
            },
        )


class AutonomousStudyFinisher:
    """Audit, selectively edit and coach after bounded research synthesis.

    Full study, audit and coaching objects are returned only to the private caller. Safe metrics contain
    strategy, status, timing, token counts and allow-listed failure categories but no prose.
    """

    def __init__(
        self,
        service: DeepSeekStudyService,
        budgets: AutonomousFinisherBudgets = AutonomousFinisherBudgets(),
    ) -> None:
        self.service = service
        self.budgets = budgets

    def run(self, study: dict[str, Any], packet: EvidencePacket) -> AutonomousStudyResult:
        current_study = study
        audit: dict[str, Any] | None = None
        coach: dict[str, Any] | None = None
        attempts: list[dict[str, Any]] = []
        counts = {
            "audit_calls": 0,
            "editor_calls": 0,
            "coach_calls": 0,
            "model_calls": 0,
            "total_tokens": 0,
        }

        audit, failure = self._call(
            "claim_audit",
            lambda trace: self.service.audit_claims_once(
                current_study,
                evidence_packet=packet,
                trace=trace,
            ),
            attempts,
            counts,
        )
        counts["audit_calls"] += 1
        if failure is not None or audit is None:
            return self._result(
                AutonomousCompletionStatus.FAILED_SAFE,
                current_study,
                None,
                None,
                "The claim audit failed safely.",
                attempts,
                counts,
            )

        try:
            parsed_audit = StudyClaimAudit.model_validate({"items": audit.get("items")})
        except ValueError:
            return self._result(
                AutonomousCompletionStatus.FAILED_SAFE,
                current_study,
                None,
                None,
                "The claim audit failed deterministic parsing.",
                attempts,
                counts,
            )
        weak_paths = weak_claim_paths(parsed_audit)
        if weak_paths:
            if len(weak_paths) > self.budgets.maximum_weak_paths:
                return self._result(
                    AutonomousCompletionStatus.INSUFFICIENT_EVIDENCE,
                    current_study,
                    audit,
                    None,
                    "Too many weak claims require revision within the bounded editor scope.",
                    attempts,
                    counts,
                )
            if not self._can_call(counts, "editor"):
                return self._result(
                    AutonomousCompletionStatus.BUDGET_EXHAUSTED,
                    current_study,
                    audit,
                    None,
                    "The targeted editor budget was exhausted.",
                    attempts,
                    counts,
                )
            repaired, failure = self._call(
                "targeted_claim_editor",
                lambda trace: self.service.repair_audited_once(
                    current_study,
                    weak_paths,
                    evidence_packet=packet,
                    trace=trace,
                ),
                attempts,
                counts,
            )
            counts["editor_calls"] += 1
            if failure is not None or repaired is None:
                return self._result(
                    AutonomousCompletionStatus.FAILED_SAFE,
                    current_study,
                    audit,
                    None,
                    "The targeted claim editor failed safely.",
                    attempts,
                    counts,
                )
            current_study = repaired
            if not self._can_call(counts, "audit"):
                return self._result(
                    AutonomousCompletionStatus.BUDGET_EXHAUSTED,
                    current_study,
                    audit,
                    None,
                    "No independent re-audit remained after editing.",
                    attempts,
                    counts,
                )
            audit, failure = self._call(
                "claim_reaudit",
                lambda trace: self.service.audit_claims_once(
                    current_study,
                    evidence_packet=packet,
                    trace=trace,
                ),
                attempts,
                counts,
            )
            counts["audit_calls"] += 1
            if failure is not None or audit is None:
                return self._result(
                    AutonomousCompletionStatus.FAILED_SAFE,
                    current_study,
                    None,
                    None,
                    "The edited study could not be re-audited safely.",
                    attempts,
                    counts,
                )
            try:
                parsed_audit = StudyClaimAudit.model_validate({"items": audit.get("items")})
            except ValueError:
                return self._result(
                    AutonomousCompletionStatus.FAILED_SAFE,
                    current_study,
                    None,
                    None,
                    "The edited claim audit failed deterministic parsing.",
                    attempts,
                    counts,
                )
            if weak_claim_paths(parsed_audit):
                return self._result(
                    AutonomousCompletionStatus.INSUFFICIENT_EVIDENCE,
                    current_study,
                    audit,
                    None,
                    "Weak claims remained after the single targeted edit.",
                    attempts,
                    counts,
                )

        if not self._can_call(counts, "coach"):
            return self._result(
                AutonomousCompletionStatus.BUDGET_EXHAUSTED,
                current_study,
                audit,
                None,
                "The filmmaker-coach budget was exhausted.",
                attempts,
                counts,
            )
        coach, failure = self._call(
            "filmmaker_coach",
            lambda trace: self.service.coach_filmmaker_once(
                current_study,
                audit or {},
                evidence_packet=packet,
                trace=trace,
            ),
            attempts,
            counts,
        )
        counts["coach_calls"] += 1
        if failure is not None or coach is None:
            return self._result(
                AutonomousCompletionStatus.FAILED_SAFE,
                current_study,
                audit,
                None,
                "The filmmaker coach failed safely.",
                attempts,
                counts,
            )
        return self._result(
            AutonomousCompletionStatus.COMPLETE,
            current_study,
            audit,
            coach,
            "The study passed claim audit and produced traceable filmmaker exercises.",
            attempts,
            counts,
        )

    def _can_call(self, counts: dict[str, int], kind: str) -> bool:
        if counts["model_calls"] >= self.budgets.max_total_model_calls:
            return False
        if kind == "audit":
            return counts["audit_calls"] < self.budgets.max_audit_calls
        if kind == "editor":
            return counts["editor_calls"] < self.budgets.max_editor_calls
        if kind == "coach":
            return counts["coach_calls"] < self.budgets.max_coach_calls
        return False

    @staticmethod
    def _call(
        strategy: str,
        operation: Callable[[StudyTrace], dict[str, Any]],
        attempts: list[dict[str, Any]],
        counts: dict[str, int],
    ) -> tuple[dict[str, Any] | None, str | None]:
        trace = StudyTrace()
        started_at = monotonic()
        result: dict[str, Any] | None = None
        failure_category: str | None = None
        try:
            result = operation(trace)
        except StudyGenerationError as exc:
            failure_category = exc.category
        except Exception:
            failure_category = "transport_failure"
        snapshot = trace.snapshot()
        model_calls = int(snapshot.get("counts", {}).get("model_calls", 0))
        total_tokens = int(snapshot.get("counts", {}).get("total_tokens", 0))
        counts["model_calls"] += model_calls
        counts["total_tokens"] += total_tokens
        attempt = {
            "strategy": strategy,
            "status": "completed" if result is not None else "failed",
            "duration_seconds": round(max(0.0, monotonic() - started_at), 3),
            "model_calls": model_calls,
            "total_tokens": total_tokens,
        }
        if failure_category is not None:
            attempt["failure_category"] = failure_category
        attempts.append(attempt)
        return result, failure_category

    @staticmethod
    def _result(
        status: AutonomousCompletionStatus,
        study: dict[str, Any],
        audit: dict[str, Any] | None,
        coach: dict[str, Any] | None,
        reason: str,
        attempts: list[dict[str, Any]],
        counts: dict[str, int],
    ) -> AutonomousStudyResult:
        return AutonomousStudyResult(
            status=status,
            study=study,
            audit=audit,
            coach=coach,
            terminal_reason=reason,
            safe_metrics={
                "status": status.value,
                "attempts": list(attempts),
                "counts": dict(counts),
            },
        )
