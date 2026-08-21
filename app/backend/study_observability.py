from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any, Callable, Iterator, Literal


STUDY_STAGE_NAMES = (
    "film_context",
    "criticism_cache",
    "video_cache",
    "retrieval_planning",
    "lexical_retrieval",
    "semantic_retrieval",
    "fusion_and_selection",
    "packet_assembly",
    "prompt_serialisation",
    "model_transport",
    "validation_and_repair",
    "end_to_end",
)
STUDY_COUNT_NAMES = (
    "retrieval_plan_items",
    "retrieval_candidates",
    "theory_sources",
    "critical_claims",
    "attributed_sources",
    "attributed_candidates",
    "attributed_omitted",
    "attributed_truncated",
    "prompt_characters",
    "model_calls",
    "repair_attempts",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "sections",
)
StudyStageName = Literal[
    "film_context",
    "criticism_cache",
    "video_cache",
    "retrieval_planning",
    "lexical_retrieval",
    "semantic_retrieval",
    "fusion_and_selection",
    "packet_assembly",
    "prompt_serialisation",
    "model_transport",
    "validation_and_repair",
    "end_to_end",
]


@dataclass
class _StageAggregate:
    duration_seconds: float = 0.0
    attempts: int = 0
    failures: int = 0
    active: int = 0
    skipped: bool = False


class StudyTrace:
    """Collect a bounded timing record without accepting request or evidence text."""

    schema_version = 1

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._started_at = clock()
        self._status: Literal["running", "completed", "failed"] = "running"
        self._stages = {name: _StageAggregate() for name in STUDY_STAGE_NAMES}
        self._counts: dict[str, int] = {}
        self._lock = RLock()

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @contextmanager
    def stage(self, name: StudyStageName) -> Iterator[None]:
        if name == "end_to_end":
            raise ValueError("The end-to-end stage is managed by the trace lifecycle.")
        aggregate = self._stage(name)
        with self._lock:
            if self._status != "running":
                raise RuntimeError("A completed study trace cannot accept another stage.")
            if aggregate.skipped:
                raise RuntimeError("A skipped study stage cannot be started.")
            aggregate.active += 1
        started_at = self._clock()
        try:
            yield
        except BaseException:
            self._record(name, started_at, failed=True)
            raise
        else:
            self._record(name, started_at, failed=False)

    def skip(self, name: StudyStageName) -> None:
        if name == "end_to_end":
            raise ValueError("The end-to-end stage cannot be skipped.")
        aggregate = self._stage(name)
        with self._lock:
            if aggregate.active:
                raise RuntimeError("An active study stage cannot be skipped.")
            if not aggregate.attempts:
                aggregate.skipped = True

    def set_count(self, name: str, value: int) -> None:
        self._validate_count(name, value)
        with self._lock:
            self._counts[name] = value

    def increment_count(self, name: str, value: int = 1) -> None:
        self._validate_count(name, value)
        with self._lock:
            updated = self._counts.get(name, 0) + value
            self._validate_count(name, updated)
            self._counts[name] = updated

    def record_provider_usage(self, response: dict[str, Any]) -> None:
        usage = response.get("usage") if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            return
        for count_name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage.get(count_name)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                self.increment_count(count_name, value)

    def finish(self, status: Literal["completed", "failed"]) -> None:
        finished_at = self._clock()
        with self._lock:
            if self._status != "running":
                return
            aggregate = self._stages["end_to_end"]
            aggregate.duration_seconds = max(0.0, finished_at - self._started_at)
            aggregate.attempts = 1
            aggregate.failures = int(status == "failed")
            self._status = status

    def snapshot(self) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            stages = []
            for name in STUDY_STAGE_NAMES:
                aggregate = self._stages[name]
                duration = aggregate.duration_seconds
                if name == "end_to_end" and self._status == "running":
                    duration = max(0.0, now - self._started_at)
                stages.append(
                    {
                        "name": name,
                        "status": self._stage_status(aggregate),
                        "duration_ms": round(duration * 1000, 3),
                        "attempts": aggregate.attempts,
                        "failures": aggregate.failures,
                    }
                )
            counts = {
                name: self._counts[name]
                for name in STUDY_COUNT_NAMES
                if name in self._counts
            }
            return {
                "schema_version": self.schema_version,
                "status": self._status,
                "stages": stages,
                "counts": counts,
            }

    def as_log_json(self) -> str:
        return json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"))

    def _record(self, name: StudyStageName, started_at: float, *, failed: bool) -> None:
        duration = max(0.0, self._clock() - started_at)
        aggregate = self._stage(name)
        with self._lock:
            aggregate.active = max(0, aggregate.active - 1)
            aggregate.duration_seconds += duration
            aggregate.attempts += 1
            aggregate.failures += int(failed)

    def _stage(self, name: str) -> _StageAggregate:
        try:
            return self._stages[name]
        except KeyError as exc:
            raise ValueError("Unknown study observability stage.") from exc

    @staticmethod
    def _stage_status(aggregate: _StageAggregate) -> str:
        if aggregate.active:
            return "running"
        if aggregate.skipped:
            return "skipped"
        if not aggregate.attempts:
            return "not_run"
        if not aggregate.failures:
            return "completed"
        if aggregate.failures == aggregate.attempts:
            return "failed"
        return "degraded"

    @staticmethod
    def _validate_count(name: str, value: int) -> None:
        if name not in STUDY_COUNT_NAMES:
            raise ValueError("Unknown study observability count.")
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000_000:
            raise ValueError("Study observability counts must be bounded non-negative integers.")
