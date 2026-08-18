from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from threading import RLock
from time import monotonic
from typing import Any


PUBLIC_PROGRESS_KINDS = frozenset(
    {
        "film_resolving",
        "film_needs_choice",
        "existing_evidence_loading",
        "research_planning",
        "tool_started",
        "tool_completed",
        "tool_failed",
        "evidence_assessed",
        "study_drafting",
        "quality_checked",
        "study_repairing",
        "run_completed",
        "run_failed",
    }
)
PUBLIC_COUNT_KEYS = frozenset(
    {
        "theory_sources",
        "critical_claims",
        "attributed_sources",
        "sections",
    }
)
MAX_PUBLIC_MESSAGE_CHARACTERS = 180
PUBLIC_PROGRESS_MESSAGES = {
    "film_resolving": {"default": "Confirming the selected film record…"},
    "film_needs_choice": {"default": "Choose one verified film to continue."},
    "existing_evidence_loading": {
        "default": "Loading the available attributed and analytical evidence…"
    },
    "research_planning": {"default": "Planning a bounded research action…"},
    "tool_started": {"default": "Retrieving one permitted public source…"},
    "tool_completed": {"default": "The permitted source retrieval completed."},
    "tool_failed": {"default": "A permitted source was unavailable."},
    "evidence_assessed": {"default": "The evidence boundary is ready for synthesis."},
    "study_drafting": {"default": "Drafting the evidence-grounded study…"},
    "quality_checked": {
        "passed": "The study passed the deterministic quality checks.",
        "limited": "The study completed with explicit evidence limitations.",
    },
    "study_repairing": {"default": "Applying the single permitted study repair…"},
    "run_completed": {"default": "The study is ready."},
    "run_failed": {
        "disconnected": "The browser disconnected from this run.",
        "film_missing": "The selected film record is no longer available.",
        "quota_exhausted": "The Deep Study allowance is exhausted for now.",
        "quota_unavailable": "The Deep Study allowance could not be verified.",
        "invalid_study": "DeepSeek could not produce a valid study for this run.",
        "safe_stop": "The study run stopped safely.",
    },
}
PUBLIC_PROGRESS_MESSAGE_VALUES = frozenset(
    message
    for variants in PUBLIC_PROGRESS_MESSAGES.values()
    for message in variants.values()
)


def public_progress_message(kind: str, variant: str = "default") -> str:
    try:
        return PUBLIC_PROGRESS_MESSAGES[kind][variant]
    except KeyError as exc:
        raise ValueError("Unknown public research event message.") from exc


@dataclass
class ResearchProgressStream:
    """Serialise only the bounded public progress contract as SSE frames."""

    run_id: str
    _started_at: float = field(default_factory=monotonic)
    _sequence: int = 0

    def frame(
        self,
        kind: str,
        *,
        message_variant: str = "default",
        counts: dict[str, int] | None = None,
    ) -> str:
        if kind not in PUBLIC_PROGRESS_KINDS:
            raise ValueError("Unknown public research event kind.")
        safe_message = public_progress_message(kind, message_variant)
        safe_counts: dict[str, int] = {}
        for key, value in (counts or {}).items():
            if key not in PUBLIC_COUNT_KEYS:
                raise ValueError("Unknown public research event count.")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("Public research event counts must be non-negative integers.")
            safe_counts[key] = value
        self._sequence += 1
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "kind": kind,
            "sequence": self._sequence,
            "message": safe_message,
            "elapsed_ms": max(0, round((monotonic() - self._started_at) * 1000)),
        }
        if safe_counts:
            payload["counts"] = safe_counts
        return f"event: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@dataclass(frozen=True)
class StoredStudyRun:
    owner_id: str
    created_at: float
    status: str = "running"
    result: dict[str, Any] | None = None
    public_error: str | None = None


class StudyRunStore:
    """Hold authenticated study results briefly without placing them in the SSE stream."""

    def __init__(self, *, ttl_seconds: int = 600, max_items: int = 50) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._items: dict[str, StoredStudyRun] = {}
        self._lock = RLock()

    def create(self, run_id: str, owner_id: str) -> None:
        with self._lock:
            self._purge_locked()
            while len(self._items) >= self.max_items:
                oldest = min(self._items, key=lambda key: self._items[key].created_at)
                self._items.pop(oldest, None)
            self._items[run_id] = StoredStudyRun(owner_id=owner_id, created_at=monotonic())

    def complete(self, run_id: str, owner_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            current = self._owned_locked(run_id, owner_id)
            self._items[run_id] = replace(current, status="complete", result=result)

    def fail(self, run_id: str, owner_id: str, public_error: str) -> None:
        if public_error not in PUBLIC_PROGRESS_MESSAGE_VALUES:
            raise ValueError("Unknown public research failure message.")
        with self._lock:
            current = self._owned_locked(run_id, owner_id)
            if current.status == "complete":
                return
            self._items[run_id] = replace(
                current,
                status="failed",
                public_error=public_error,
            )

    def read(self, run_id: str, owner_id: str) -> StoredStudyRun:
        with self._lock:
            self._purge_locked()
            return self._owned_locked(run_id, owner_id)

    def _owned_locked(self, run_id: str, owner_id: str) -> StoredStudyRun:
        item = self._items.get(run_id)
        if item is None or item.owner_id != owner_id:
            raise KeyError(run_id)
        return item

    def _purge_locked(self) -> None:
        expired_before = monotonic() - self.ttl_seconds
        expired = [
            run_id for run_id, item in self._items.items() if item.created_at < expired_before
        ]
        for run_id in expired:
            self._items.pop(run_id, None)
