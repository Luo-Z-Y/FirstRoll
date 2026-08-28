from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import os
from pathlib import Path
import re
from threading import RLock
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from app.backend.autonomous_study import StudyClaimAudit, weak_claim_paths
from app.backend.evidence import EvidencePacket
from app.backend.research_agent_contract import ResearchBudgets, TerminalStatus
from app.backend.research_graph import (
    ResearchGraphContext,
    ResearchGraphState,
    build_research_graph,
    initial_research_state,
)
from app.backend.study_observability import StudyTrace
from app.backend.study_service import DeepSeekStudyService, StudyGenerationError


class AutonomousRunPhase(StrEnum):
    RESEARCH = "research"
    AUDIT = "audit"
    EDIT = "edit"
    REAUDIT = "reaudit"
    COACH = "coach"
    COMPLETE = "complete"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BUDGET_EXHAUSTED = "budget_exhausted"
    FAILED_SAFE = "failed_safe"
    CANCELLED = "cancelled"


TERMINAL_PHASES = frozenset(
    {
        AutonomousRunPhase.COMPLETE,
        AutonomousRunPhase.INSUFFICIENT_EVIDENCE,
        AutonomousRunPhase.BUDGET_EXHAUSTED,
        AutonomousRunPhase.FAILED_SAFE,
        AutonomousRunPhase.CANCELLED,
    }
)


class AutonomousRunCheckpoint(BaseModel):
    """Private resumable state; never suitable for telemetry or a Git report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    run_id: str = Field(min_length=8, max_length=128)
    owner_id: str = Field(min_length=3, max_length=200)
    question: str = Field(min_length=1, max_length=4000)
    film_query: str = Field(min_length=1, max_length=500)
    film_id: str | None = Field(default=None, max_length=300)
    phase: AutonomousRunPhase = AutonomousRunPhase.RESEARCH
    terminal_reason: str | None = Field(default=None, max_length=500)
    cancellation_requested: bool = False
    in_flight_phase: AutonomousRunPhase | None = None
    created_at: str
    updated_at: str
    packet: dict[str, Any] | None = None
    study: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    coach: dict[str, Any] | None = None
    audit_calls: int = Field(default=0, ge=0, le=2)
    editor_calls: int = Field(default=0, ge=0, le=1)
    coach_calls: int = Field(default=0, ge=0, le=1)
    finisher_model_calls: int = Field(default=0, ge=0, le=4)
    action_metrics: list[dict[str, Any]] = Field(default_factory=list, max_length=12)


@dataclass(frozen=True)
class ResearchPhaseResult:
    status: str
    terminal_reason: str
    study: dict[str, Any] | None = None
    packet: EvidencePacket | None = None
    safe_metrics: dict[str, Any] | None = None


@dataclass(frozen=True)
class PhaseCallResult:
    value: dict[str, Any]
    safe_metrics: dict[str, Any]


class AutonomousPhaseExecutor(Protocol):
    def research(self, checkpoint: AutonomousRunCheckpoint) -> ResearchPhaseResult: ...

    def audit(
        self,
        study: dict[str, Any],
        packet: EvidencePacket,
    ) -> PhaseCallResult: ...

    def edit(
        self,
        study: dict[str, Any],
        paths: tuple[str, ...],
        packet: EvidencePacket,
    ) -> PhaseCallResult: ...

    def coach(
        self,
        study: dict[str, Any],
        audit: dict[str, Any],
        packet: EvidencePacket,
    ) -> PhaseCallResult: ...


class LocalAutonomousRunStore:
    """Atomic mode-hardened storage for one owner's private local Agent checkpoints."""

    def __init__(
        self,
        directory: Path | None = None,
        *,
        root: Path | None = None,
    ) -> None:
        project_root = root or Path(__file__).resolve().parents[2]
        self.directory = directory or project_root / ".firstroll" / "autonomous-runs"
        self._project_root = project_root if root is not None or directory is None else None
        self._lock = RLock()

    @staticmethod
    def new_checkpoint(
        *,
        run_id: str,
        owner_id: str,
        question: str,
        film_query: str,
        film_id: str | None = None,
    ) -> AutonomousRunCheckpoint:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", run_id):
            raise ValueError("The autonomous run ID is invalid.")
        now = datetime.now(timezone.utc).isoformat()
        return AutonomousRunCheckpoint(
            run_id=run_id,
            owner_id=owner_id,
            question=question,
            film_query=film_query,
            film_id=film_id,
            created_at=now,
            updated_at=now,
        )

    def create(self, checkpoint: AutonomousRunCheckpoint) -> None:
        with self._lock:
            self._prepare_directory()
            path = self._path(checkpoint.run_id)
            if path.exists():
                raise FileExistsError("The autonomous run already exists.")
            self._write(path, checkpoint, exclusive=True)

    def load(self, run_id: str, owner_id: str) -> AutonomousRunCheckpoint:
        with self._lock:
            self._validate_existing_directory()
            path = self._path(run_id)
            try:
                if path.is_symlink() or os.stat(path).st_mode & 0o077:
                    raise RuntimeError("The autonomous run checkpoint has unsafe file permissions.")
                checkpoint = cast(
                    AutonomousRunCheckpoint,
                    AutonomousRunCheckpoint.model_validate_json(path.read_text(encoding="utf-8")),
                )
            except FileNotFoundError as exc:
                raise FileNotFoundError("The autonomous run does not exist.") from exc
            except RuntimeError:
                raise
            except (OSError, ValueError) as exc:
                raise RuntimeError("The autonomous run checkpoint is invalid.") from exc
            if checkpoint.run_id != run_id or checkpoint.owner_id != owner_id:
                raise PermissionError("The autonomous run is not available to this owner.")
            return checkpoint

    def save(self, checkpoint: AutonomousRunCheckpoint) -> None:
        with self._lock:
            existing = self.load(checkpoint.run_id, checkpoint.owner_id)
            if existing.created_at != checkpoint.created_at:
                raise ValueError("The autonomous run creation identity cannot change.")
            checkpoint.updated_at = datetime.now(timezone.utc).isoformat()
            self._write(self._path(checkpoint.run_id), checkpoint, exclusive=False)

    def request_cancel(self, run_id: str, owner_id: str) -> AutonomousRunCheckpoint:
        checkpoint = self.load(run_id, owner_id)
        if checkpoint.phase not in TERMINAL_PHASES:
            checkpoint.cancellation_requested = True
            self.save(checkpoint)
        return checkpoint

    def _prepare_directory(self) -> None:
        if self.directory.is_symlink():
            raise ValueError("Autonomous run checkpoints must not use a symlink directory.")
        if self._project_root is not None:
            try:
                relative = self.directory.resolve().relative_to(self._project_root.resolve())
            except ValueError as exc:
                raise ValueError("Autonomous run checkpoints must stay under .firstroll.") from exc
            if not relative.parts or relative.parts[0] != ".firstroll":
                raise ValueError("Autonomous run checkpoints must stay under .firstroll.")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)

    def _validate_existing_directory(self) -> None:
        if (
            self.directory.is_symlink()
            or not self.directory.is_dir()
            or os.stat(self.directory).st_mode & 0o077
        ):
            raise RuntimeError("The autonomous run directory has unsafe permissions.")
        if self._project_root is not None:
            try:
                relative = self.directory.resolve().relative_to(self._project_root.resolve())
            except ValueError as exc:
                raise RuntimeError("The autonomous run directory escaped .firstroll.") from exc
            if not relative.parts or relative.parts[0] != ".firstroll":
                raise RuntimeError("The autonomous run directory escaped .firstroll.")

    def _path(self, run_id: str) -> Path:
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    @staticmethod
    def _write(
        path: Path,
        checkpoint: AutonomousRunCheckpoint,
        *,
        exclusive: bool,
    ) -> None:
        payload = checkpoint.model_dump_json(indent=2) + "\n"
        if exclusive:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                path.unlink(missing_ok=True)
                raise
            os.chmod(path, 0o600)
            return
        temporary = path.with_suffix(".tmp")
        temporary.unlink(missing_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)


class LocalAutonomousPhaseExecutor:
    """Real local graph and DeepSeek capabilities used by the durable phase engine."""

    def __init__(
        self,
        services: Any,
        study_service: DeepSeekStudyService,
        research_budgets: ResearchBudgets = ResearchBudgets(),
    ) -> None:
        self.services = services
        self.study_service = study_service
        self.research_budgets = research_budgets

    def research(self, checkpoint: AutonomousRunCheckpoint) -> ResearchPhaseResult:
        state = initial_research_state(
            run_id=checkpoint.run_id,
            user_id=checkpoint.owner_id,
            question=checkpoint.question,
            film_query=checkpoint.film_query,
            film_id=checkpoint.film_id,
        )
        final = cast(
            ResearchGraphState,
            build_research_graph().invoke(
                state,
                context=ResearchGraphContext(
                    services=self.services,
                    budgets=self.research_budgets,
                    mode="full",
                ),
                config={"recursion_limit": 64},
            ),
        )
        metrics = self.services.safe_metrics(checkpoint.run_id)
        if final["status"] is not TerminalStatus.COMPLETE:
            return ResearchPhaseResult(
                status=final["status"].value,
                terminal_reason=str(final.get("terminal_reason") or "Research stopped safely."),
                safe_metrics=metrics,
            )
        draft = final.get("draft")
        if not isinstance(draft, dict):
            return ResearchPhaseResult(
                status=AutonomousRunPhase.FAILED_SAFE.value,
                terminal_reason="Research completed without a structured private study.",
                safe_metrics=metrics,
            )
        return ResearchPhaseResult(
            status=AutonomousRunPhase.COMPLETE.value,
            terminal_reason="Research synthesis completed.",
            study=draft,
            packet=self.services.private_packet(checkpoint.run_id),
            safe_metrics=metrics,
        )

    def audit(
        self,
        study: dict[str, Any],
        packet: EvidencePacket,
    ) -> PhaseCallResult:
        trace = StudyTrace()
        value = self.study_service.audit_claims_once(
            study,
            evidence_packet=packet,
            trace=trace,
        )
        return PhaseCallResult(value=value, safe_metrics=trace.snapshot())

    def edit(
        self,
        study: dict[str, Any],
        paths: tuple[str, ...],
        packet: EvidencePacket,
    ) -> PhaseCallResult:
        trace = StudyTrace()
        value = self.study_service.repair_audited_once(
            study,
            paths,
            evidence_packet=packet,
            trace=trace,
        )
        return PhaseCallResult(value=value, safe_metrics=trace.snapshot())

    def coach(
        self,
        study: dict[str, Any],
        audit: dict[str, Any],
        packet: EvidencePacket,
    ) -> PhaseCallResult:
        trace = StudyTrace()
        value = self.study_service.coach_filmmaker_once(
            study,
            audit,
            evidence_packet=packet,
            trace=trace,
        )
        return PhaseCallResult(value=value, safe_metrics=trace.snapshot())


class DurableAutonomousRunEngine:
    """Advance one private run by atomic, cancellable and resumable phases."""

    def __init__(
        self,
        store: LocalAutonomousRunStore,
        executor: AutonomousPhaseExecutor,
    ) -> None:
        self.store = store
        self.executor = executor

    def step(self, run_id: str, owner_id: str) -> AutonomousRunCheckpoint:
        checkpoint = self.store.load(run_id, owner_id)
        if checkpoint.phase in TERMINAL_PHASES:
            return checkpoint
        if checkpoint.in_flight_phase is not None:
            self._record_action(
                checkpoint,
                strategy=checkpoint.in_flight_phase.value,
                status="failed",
                failure_category="interrupted_phase",
            )
            checkpoint.in_flight_phase = None
            self._fail(
                checkpoint,
                "An in-flight autonomous phase was interrupted; automatic paid replay was blocked.",
            )
            self.store.save(checkpoint)
            return checkpoint
        if checkpoint.cancellation_requested:
            checkpoint.phase = AutonomousRunPhase.CANCELLED
            checkpoint.terminal_reason = "The owner cancelled the autonomous run."
            self.store.save(checkpoint)
            return checkpoint
        checkpoint.in_flight_phase = checkpoint.phase
        self.store.save(checkpoint)
        try:
            if checkpoint.phase is AutonomousRunPhase.RESEARCH:
                self._research(checkpoint)
            elif checkpoint.phase in {AutonomousRunPhase.AUDIT, AutonomousRunPhase.REAUDIT}:
                self._audit(checkpoint)
            elif checkpoint.phase is AutonomousRunPhase.EDIT:
                self._edit(checkpoint)
            elif checkpoint.phase is AutonomousRunPhase.COACH:
                self._coach(checkpoint)
            else:
                self._fail(checkpoint, "The autonomous run reached an invalid phase.")
        except StudyGenerationError as exc:
            self._record_action(
                checkpoint,
                strategy=checkpoint.phase.value,
                status="failed",
                failure_category=exc.category,
            )
            self._fail(checkpoint, "The autonomous phase failed safely.")
        except Exception:
            self._record_action(
                checkpoint,
                strategy=checkpoint.phase.value,
                status="failed",
                failure_category="transport_failure",
            )
            self._fail(checkpoint, "The autonomous phase failed safely.")
        latest = self.store.load(run_id, owner_id)
        checkpoint.cancellation_requested = (
            checkpoint.cancellation_requested or latest.cancellation_requested
        )
        checkpoint.in_flight_phase = None
        self.store.save(checkpoint)
        return checkpoint

    def run_to_terminal(
        self,
        run_id: str,
        owner_id: str,
        *,
        maximum_steps: int = 6,
    ) -> AutonomousRunCheckpoint:
        checkpoint = self.store.load(run_id, owner_id)
        for _ in range(maximum_steps):
            if checkpoint.phase in TERMINAL_PHASES:
                return checkpoint
            checkpoint = self.step(run_id, owner_id)
        if checkpoint.phase not in TERMINAL_PHASES:
            checkpoint.phase = AutonomousRunPhase.BUDGET_EXHAUSTED
            checkpoint.terminal_reason = "The durable autonomous phase-step budget was exhausted."
            self.store.save(checkpoint)
        return checkpoint

    def _research(self, checkpoint: AutonomousRunCheckpoint) -> None:
        result = self.executor.research(checkpoint)
        self._record_action(
            checkpoint,
            strategy="research_graph",
            status=result.status,
            metrics=result.safe_metrics or {},
        )
        if result.status != AutonomousRunPhase.COMPLETE.value:
            checkpoint.phase = self._terminal_phase(result.status)
            checkpoint.terminal_reason = result.terminal_reason
            return
        if result.study is None or result.packet is None:
            self._fail(checkpoint, "Research returned no resumable study packet.")
            return
        checkpoint.study = result.study
        checkpoint.packet = result.packet.model_dump()
        checkpoint.phase = AutonomousRunPhase.AUDIT
        checkpoint.terminal_reason = None

    def _audit(self, checkpoint: AutonomousRunCheckpoint) -> None:
        study, packet = self._private_inputs(checkpoint)
        if checkpoint.audit_calls >= 2 or checkpoint.finisher_model_calls >= 4:
            checkpoint.phase = AutonomousRunPhase.BUDGET_EXHAUSTED
            checkpoint.terminal_reason = "The durable claim-audit budget was exhausted."
            return
        phase = checkpoint.phase
        result = self.executor.audit(study, packet)
        checkpoint.audit_calls += 1
        self._apply_call_metrics(checkpoint, result.safe_metrics)
        self._record_action(
            checkpoint,
            strategy="claim_audit" if phase is AutonomousRunPhase.AUDIT else "claim_reaudit",
            status="completed",
            metrics=result.safe_metrics,
        )
        audit = StudyClaimAudit.model_validate({"items": result.value.get("items")})
        checkpoint.audit = result.value
        weak = weak_claim_paths(audit)
        if phase is AutonomousRunPhase.REAUDIT:
            if weak:
                checkpoint.phase = AutonomousRunPhase.INSUFFICIENT_EVIDENCE
                checkpoint.terminal_reason = "Weak claims remained after the targeted edit."
            else:
                checkpoint.phase = AutonomousRunPhase.COACH
            return
        if len(weak) > 4:
            checkpoint.phase = AutonomousRunPhase.INSUFFICIENT_EVIDENCE
            checkpoint.terminal_reason = "Too many weak claims require editing."
        elif weak:
            checkpoint.phase = AutonomousRunPhase.EDIT
        else:
            checkpoint.phase = AutonomousRunPhase.COACH

    def _edit(self, checkpoint: AutonomousRunCheckpoint) -> None:
        study, packet = self._private_inputs(checkpoint)
        audit = StudyClaimAudit.model_validate({"items": (checkpoint.audit or {}).get("items")})
        paths = weak_claim_paths(audit)
        if (
            checkpoint.editor_calls >= 1
            or checkpoint.finisher_model_calls >= 4
            or not paths
            or len(paths) > 4
        ):
            checkpoint.phase = AutonomousRunPhase.BUDGET_EXHAUSTED
            checkpoint.terminal_reason = "The durable targeted-editor budget was exhausted."
            return
        result = self.executor.edit(study, paths, packet)
        checkpoint.editor_calls += 1
        self._apply_call_metrics(checkpoint, result.safe_metrics)
        self._record_action(
            checkpoint,
            strategy="targeted_claim_editor",
            status="completed",
            metrics=result.safe_metrics,
        )
        checkpoint.study = result.value
        checkpoint.phase = AutonomousRunPhase.REAUDIT

    def _coach(self, checkpoint: AutonomousRunCheckpoint) -> None:
        study, packet = self._private_inputs(checkpoint)
        if (
            checkpoint.coach_calls >= 1
            or checkpoint.finisher_model_calls >= 4
            or checkpoint.audit is None
        ):
            checkpoint.phase = AutonomousRunPhase.BUDGET_EXHAUSTED
            checkpoint.terminal_reason = "The durable filmmaker-coach budget was exhausted."
            return
        result = self.executor.coach(study, checkpoint.audit, packet)
        checkpoint.coach_calls += 1
        self._apply_call_metrics(checkpoint, result.safe_metrics)
        self._record_action(
            checkpoint,
            strategy="filmmaker_coach",
            status="completed",
            metrics=result.safe_metrics,
        )
        checkpoint.coach = result.value
        checkpoint.phase = AutonomousRunPhase.COMPLETE
        checkpoint.terminal_reason = (
            "Research, claim audit and filmmaker coaching completed within budget."
        )

    @staticmethod
    def _private_inputs(
        checkpoint: AutonomousRunCheckpoint,
    ) -> tuple[dict[str, Any], EvidencePacket]:
        if checkpoint.study is None or checkpoint.packet is None:
            raise RuntimeError("The autonomous checkpoint lacks its private study packet.")
        return checkpoint.study, EvidencePacket.model_validate(checkpoint.packet)

    @staticmethod
    def _apply_call_metrics(
        checkpoint: AutonomousRunCheckpoint,
        metrics: dict[str, Any],
    ) -> None:
        model_calls = int(metrics.get("counts", {}).get("model_calls", 0))
        checkpoint.finisher_model_calls += model_calls
        if checkpoint.finisher_model_calls > 4:
            raise RuntimeError("The autonomous finisher exceeded its total model-call budget.")

    @staticmethod
    def _record_action(
        checkpoint: AutonomousRunCheckpoint,
        *,
        strategy: str,
        status: str,
        metrics: dict[str, Any] | None = None,
        failure_category: str | None = None,
    ) -> None:
        metrics = metrics or {}
        counts = metrics.get("counts") if isinstance(metrics, dict) else None
        item = {
            "strategy": strategy,
            "status": status,
            "model_calls": int(counts.get("model_calls", 0)) if isinstance(counts, dict) else 0,
            "total_tokens": int(counts.get("total_tokens", 0)) if isinstance(counts, dict) else 0,
        }
        if failure_category is not None:
            item["failure_category"] = failure_category
        checkpoint.action_metrics.append(item)

    @staticmethod
    def _terminal_phase(status: str) -> AutonomousRunPhase:
        mapping = {
            TerminalStatus.INSUFFICIENT_EVIDENCE.value: AutonomousRunPhase.INSUFFICIENT_EVIDENCE,
            TerminalStatus.BUDGET_EXHAUSTED.value: AutonomousRunPhase.BUDGET_EXHAUSTED,
            TerminalStatus.FAILED_SAFE.value: AutonomousRunPhase.FAILED_SAFE,
        }
        return mapping.get(status, AutonomousRunPhase.FAILED_SAFE)

    @staticmethod
    def _fail(checkpoint: AutonomousRunCheckpoint, reason: str) -> None:
        checkpoint.phase = AutonomousRunPhase.FAILED_SAFE
        checkpoint.terminal_reason = reason
