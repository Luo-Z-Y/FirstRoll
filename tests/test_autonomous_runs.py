from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from app.backend.autonomous_runs import (
    AutonomousRunPhase,
    DurableAutonomousRunEngine,
    LocalAutonomousRunStore,
    PhaseCallResult,
    ResearchPhaseResult,
)
from app.backend.autonomous_study import audited_claim_paths, path_source_ids
from tools.evaluate_agent_repair import synthetic_packet, valid_candidate


RUN_ID = "run-autonomous-001"
OWNER_ID = "local-owner"


def audit(*, weak_path: str | None = None) -> dict[str, Any]:
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
                    if path == weak_path
                    else "directly_supported"
                    if field in {"critic_reports", "theory_explains"}
                    else "reasonable_interpretation"
                ),
                "source_ids": [source_id],
                "support_note": (
                    "The evidence supports this bounded classification without changing the "
                    "claim's visible epistemic status."
                ),
            }
        )
    return {"items": items}


def call(value: dict[str, Any], *, tokens: int = 100) -> PhaseCallResult:
    return PhaseCallResult(
        value=value,
        safe_metrics={"counts": {"model_calls": 1, "total_tokens": tokens}},
    )


class Executor:
    def __init__(self, audits: list[dict[str, Any]]) -> None:
        self.audits = audits
        self.calls: list[str] = []

    def research(self, checkpoint):
        self.calls.append("research")
        return ResearchPhaseResult(
            status="complete",
            terminal_reason="Research complete.",
            study=valid_candidate(),
            packet=synthetic_packet(),
            safe_metrics={"counts": {"model_calls": 1, "total_tokens": 500}},
        )

    def audit(self, study, packet):
        self.calls.append("audit")
        return call(self.audits.pop(0))

    def edit(self, study, paths, packet):
        self.calls.append("edit")
        assert 1 <= len(paths) <= 4
        return call(valid_candidate(), tokens=50)

    def coach(self, study, claim_audit, packet):
        self.calls.append("coach")
        return call({"exercises": [{"private": "PRIVATE_COACH_TEXT"}]}, tokens=75)


def create(store: LocalAutonomousRunStore) -> None:
    store.create(
        store.new_checkpoint(
            run_id=RUN_ID,
            owner_id=OWNER_ID,
            question="How does framing organise uncertainty?",
            film_query="Example Film",
            film_id="example:2024",
        )
    )


def test_private_run_store_is_mode_hardened_and_owner_scoped(tmp_path: Path) -> None:
    directory = tmp_path / "autonomous-runs"
    store = LocalAutonomousRunStore(directory)
    create(store)

    loaded = store.load(RUN_ID, OWNER_ID)
    files = list(directory.glob("*.json"))

    assert loaded.phase is AutonomousRunPhase.RESEARCH
    assert len(files) == 1
    assert RUN_ID not in files[0].name
    assert os.stat(directory).st_mode & 0o777 == 0o700
    assert os.stat(files[0]).st_mode & 0o777 == 0o600
    with pytest.raises(PermissionError, match="not available"):
        store.load(RUN_ID, "another-owner")
    with pytest.raises(FileExistsError):
        create(store)
    os.chmod(files[0], 0o644)
    with pytest.raises(RuntimeError, match="unsafe file permissions"):
        store.load(RUN_ID, OWNER_ID)


def test_run_store_rejects_private_directory_symlink_outside_project(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    outside = tmp_path / "outside"
    worktree.mkdir()
    outside.mkdir()
    (worktree / ".firstroll").symlink_to(outside, target_is_directory=True)
    store = LocalAutonomousRunStore(
        worktree / ".firstroll" / "autonomous-runs",
        root=worktree,
    )

    with pytest.raises(ValueError, match="must stay under .firstroll"):
        create(store)

    assert not (outside / "autonomous-runs").exists()


def test_durable_run_completes_and_persists_each_phase(tmp_path: Path) -> None:
    store = LocalAutonomousRunStore(tmp_path / "runs")
    create(store)
    executor = Executor([audit()])
    engine = DurableAutonomousRunEngine(store, executor)

    result = engine.run_to_terminal(RUN_ID, OWNER_ID)
    reloaded = store.load(RUN_ID, OWNER_ID)

    assert result.phase is AutonomousRunPhase.COMPLETE
    assert reloaded.phase is AutonomousRunPhase.COMPLETE
    assert executor.calls == ["research", "audit", "coach"]
    assert reloaded.study is not None
    assert reloaded.audit is not None
    assert reloaded.coach is not None
    assert reloaded.finisher_model_calls == 2
    assert "PRIVATE_COACH_TEXT" not in str(reloaded.action_metrics)


def test_durable_run_resumes_after_research_and_reaudits_edit(tmp_path: Path) -> None:
    store = LocalAutonomousRunStore(tmp_path / "runs")
    create(store)
    weak = "sections.1.mechanism"
    first_executor = Executor([audit(weak_path=weak), audit()])
    first_engine = DurableAutonomousRunEngine(store, first_executor)

    checkpoint = first_engine.step(RUN_ID, OWNER_ID)
    assert checkpoint.phase is AutonomousRunPhase.AUDIT

    resumed_engine = DurableAutonomousRunEngine(store, first_executor)
    result = resumed_engine.run_to_terminal(RUN_ID, OWNER_ID)

    assert result.phase is AutonomousRunPhase.COMPLETE
    assert first_executor.calls == ["research", "audit", "edit", "audit", "coach"]
    assert result.audit_calls == 2
    assert result.editor_calls == 1
    assert result.coach_calls == 1
    assert result.finisher_model_calls == 4


def test_owner_cancellation_stops_before_next_paid_phase(tmp_path: Path) -> None:
    store = LocalAutonomousRunStore(tmp_path / "runs")
    create(store)
    executor = Executor([audit()])
    engine = DurableAutonomousRunEngine(store, executor)

    store.request_cancel(RUN_ID, OWNER_ID)
    result = engine.step(RUN_ID, OWNER_ID)

    assert result.phase is AutonomousRunPhase.CANCELLED
    assert executor.calls == []


def test_cancellation_requested_during_phase_is_not_overwritten(tmp_path: Path) -> None:
    store = LocalAutonomousRunStore(tmp_path / "runs")
    create(store)

    class CancellingExecutor(Executor):
        def research(self, checkpoint):
            result = super().research(checkpoint)
            store.request_cancel(checkpoint.run_id, checkpoint.owner_id)
            return result

    executor = CancellingExecutor([audit()])
    engine = DurableAutonomousRunEngine(store, executor)

    after_research = engine.step(RUN_ID, OWNER_ID)
    cancelled = engine.step(RUN_ID, OWNER_ID)

    assert after_research.cancellation_requested is True
    assert after_research.phase is AutonomousRunPhase.AUDIT
    assert cancelled.phase is AutonomousRunPhase.CANCELLED
    assert executor.calls == ["research"]


def test_interrupted_in_flight_phase_is_not_replayed(tmp_path: Path) -> None:
    store = LocalAutonomousRunStore(tmp_path / "runs")
    create(store)
    checkpoint = store.load(RUN_ID, OWNER_ID)
    checkpoint.phase = AutonomousRunPhase.AUDIT
    checkpoint.in_flight_phase = AutonomousRunPhase.AUDIT
    checkpoint.study = valid_candidate()
    checkpoint.packet = synthetic_packet().model_dump()
    store.save(checkpoint)
    executor = Executor([audit()])

    result = DurableAutonomousRunEngine(store, executor).step(RUN_ID, OWNER_ID)

    assert result.phase is AutonomousRunPhase.FAILED_SAFE
    assert executor.calls == []
    assert result.action_metrics[-1]["failure_category"] == "interrupted_phase"
    assert "automatic paid replay was blocked" in str(result.terminal_reason)
