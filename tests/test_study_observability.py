from __future__ import annotations

import json

import pytest

from app.backend.study_observability import STUDY_STAGE_NAMES, StudyTrace


class ManualClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_study_trace_records_completed_skipped_failed_and_recovered_stages() -> None:
    clock = ManualClock()
    trace = StudyTrace(clock=clock)

    with trace.stage("film_context"):
        clock.advance(0.012)
    trace.skip("lexical_retrieval")
    try:
        with trace.stage("semantic_retrieval"):
            clock.advance(0.007)
            raise RuntimeError("private provider exception")
    except RuntimeError:
        pass
    with trace.stage("semantic_retrieval"):
        clock.advance(0.003)
    trace.set_count("theory_sources", 4)
    trace.increment_count("model_calls")
    trace.record_provider_usage(
        {
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
            }
        }
    )
    clock.advance(0.002)
    trace.finish("completed")

    snapshot = trace.snapshot()
    stages = {stage["name"]: stage for stage in snapshot["stages"]}
    assert snapshot["status"] == "completed"
    assert [stage["name"] for stage in snapshot["stages"]] == list(STUDY_STAGE_NAMES)
    assert stages["film_context"] == {
        "name": "film_context",
        "status": "completed",
        "duration_ms": 12.0,
        "attempts": 1,
        "failures": 0,
    }
    assert stages["lexical_retrieval"]["status"] == "skipped"
    assert stages["semantic_retrieval"]["status"] == "degraded"
    assert stages["semantic_retrieval"]["duration_ms"] == 10.0
    assert stages["semantic_retrieval"]["attempts"] == 2
    assert stages["semantic_retrieval"]["failures"] == 1
    assert stages["end_to_end"]["status"] == "completed"
    assert stages["end_to_end"]["duration_ms"] == 24.0
    assert snapshot["counts"] == {
        "theory_sources": 4,
        "model_calls": 1,
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
    }
    assert "private provider exception" not in json.dumps(snapshot)


def test_study_trace_rejects_unbounded_names_values_and_payload_text() -> None:
    trace = StudyTrace()

    with pytest.raises(ValueError, match="Unknown study observability stage"):
        with trace.stage("private_prompt"):  # type: ignore[arg-type]
            pass
    with pytest.raises(ValueError, match="Unknown study observability count"):
        trace.set_count("private_passage", 1)
    with pytest.raises(ValueError, match="bounded non-negative"):
        trace.set_count("model_calls", -1)
    with pytest.raises(ValueError, match="bounded non-negative"):
        trace.set_count("model_calls", True)

    snapshot = trace.snapshot()
    assert set(snapshot) == {"schema_version", "status", "stages", "counts"}
    assert set(snapshot["counts"]) <= {
        "retrieval_plan_items",
        "retrieval_candidates",
        "theory_sources",
        "theory_candidates",
        "theory_omitted",
        "critical_claims",
        "critical_candidates",
        "critical_omitted",
        "attributed_sources",
        "attributed_candidates",
        "attributed_omitted",
        "attributed_truncated",
        "prompt_characters",
        "model_calls",
        "repair_attempts",
        "structural_repair_attempts",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "sections",
    }
