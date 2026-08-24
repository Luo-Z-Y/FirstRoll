from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import evaluate_local_agent as evaluator


def safe_agent_case(case_id: str, *, initial_status: str = "passed") -> dict[str, Any]:
    external_calls = 1 if initial_status != "passed" else 0
    attempted = ["fetch_guardian_reviews"] if external_calls else []
    return {
        "case_id": case_id,
        "status": "passed",
        "identity_match": True,
        "quality": {"valid_citations": True},
        "packet_quality": {"instruction_safety": {"containment_boundary": True}},
        "initial_packet_quality": {"status": initial_status},
        "initial_packet_fingerprint": f"{case_id}-packet",
        "packet_fingerprint": f"{case_id}-packet",
        "graph_counts": {
            "planning_calls": external_calls,
            "external_tool_calls": external_calls,
        },
        "attempted_tools": attempted,
    }


def test_completed_no_go_decision_cannot_authorise_a_rerun() -> None:
    completed = json.loads(
        (ROOT / "evals" / "agent_go_no_go.json").read_text(encoding="utf-8")
    )
    approved = dict(completed)
    approved["status"] = "approved_bounded_local_comparison"

    assert evaluator.comparison_authorised(completed) is False
    assert evaluator.comparison_authorised(approved) is True


def test_only_the_complete_frozen_suite_can_be_acceptance_ready() -> None:
    fingerprint = evaluator.json_fingerprint(ROOT / "evals" / "agent_cases.json")

    assert evaluator.full_suite_selected(
        suite_id="firstroll-agent-comparison-v1",
        suite_fingerprint=fingerprint,
        case_count=5,
        subset_requested=False,
        expected_case_count=5,
    )
    assert not evaluator.full_suite_selected(
        suite_id="firstroll-agent-comparison-v1",
        suite_fingerprint=fingerprint,
        case_count=1,
        subset_requested=True,
        expected_case_count=5,
    )
    assert not evaluator.full_suite_selected(
        suite_id="changed-suite",
        suite_fingerprint=fingerprint,
        case_count=5,
        subset_requested=False,
        expected_case_count=5,
    )


def test_candidate_target_evaluation_separates_local_human_and_cutover_gates() -> None:
    decision = json.loads((ROOT / "evals" / "agent_go_no_go.json").read_text(encoding="utf-8"))
    fixed = {
        "latency_seconds": {"p50_end_to_end": 55.0, "p95_end_to_end": 62.0},
        "total_tokens": 40_000,
    }
    agent = {
        "mean_quality_score": 98.0,
        "quality_gate_pass_rate": 1.0,
        "latency_seconds": {"p50_end_to_end": 60.0, "p95_end_to_end": 70.0},
        "total_tokens": 46_000,
    }
    cases = [safe_agent_case(f"case-{index}") for index in range(4)] + [
        safe_agent_case("case-5", initial_status="limited")
    ]

    results = evaluator.evaluate_candidate_targets(decision, fixed, agent, cases)
    statuses = {item["target_id"]: item["status"] for item in results}

    assert all(statuses[target] == "pending_human_review" for target in evaluator.HUMAN_TARGETS)
    assert statuses["visible_response_p95_ms"] == "deferred_no_product_route"
    assert all(
        status == "passed"
        for target, status in statuses.items()
        if target not in evaluator.HUMAN_TARGETS | evaluator.DEFERRED_CUTOVER_TARGETS
    )


def test_fixed_control_must_complete_before_candidate_can_be_compared() -> None:
    assert evaluator.fixed_control_checks({"case_count": 5, "successful_cases": 5})[0][
        "status"
    ] == "passed"
    assert evaluator.fixed_control_checks({"case_count": 5, "successful_cases": 4})[0][
        "status"
    ] == "failed"


def test_policy_checks_require_selective_non_repeating_acquisition() -> None:
    decision = json.loads((ROOT / "evals" / "agent_go_no_go.json").read_text(encoding="utf-8"))
    cases = [safe_agent_case(f"case-{index}") for index in range(4)] + [
        safe_agent_case("case-5", initial_status="limited")
    ]

    checks = evaluator.policy_checks(cases, decision)

    assert all(item["status"] == "passed" for item in checks)

    cases[0]["graph_counts"]["external_tool_calls"] = 1
    cases[0]["packet_fingerprint"] = "mutated"
    failed = {item["check_id"]: item for item in evaluator.policy_checks(cases, decision)}
    assert failed["sufficient_packet_external_calls"]["status"] == "failed"
    assert failed["sufficient_packet_mutations"]["status"] == "failed"


def test_safe_study_score_removes_generated_lens_text() -> None:
    study = {
        "quality": {
            "status": "passed",
            "score": 0.8,
            "sections": [
                {
                    "section": 1,
                    "lens": "PRIVATE_GENERATED_LENS",
                    "score": 0.8,
                    "issues": ["generic_language"],
                }
            ],
        },
        "sections": [],
    }

    score = evaluator.safe_study_score(study, identity_ok=True)

    assert score["quality_gate_failed_sections"] == [
        {"section": 1, "score": 0.8, "issues": ["generic_language"]}
    ]
    assert "PRIVATE_GENERATED_LENS" not in str(score)


def test_report_guard_rejects_source_or_prompt_fields() -> None:
    evaluator.assert_safe_report({"summary": {"quality": 98.0}})

    with pytest.raises(ValueError, match="Unsafe report key"):
        evaluator.assert_safe_report({"cases": [{"packet": {"content": "private"}}]})
    with pytest.raises(ValueError, match="Unsafe report key"):
        evaluator.assert_safe_report({"model_calls": [{"messages": []}]})
    with pytest.raises(ValueError, match="Unsafe report key"):
        evaluator.assert_safe_report({"quality": {"lens": "generated response"}})


def test_private_packet_snapshot_is_restricted_and_mode_hardened(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    target = tmp_path / ".firstroll" / "evaluations" / "agent-packets.json"

    evaluator.write_private_packets(target, {"schema_version": 1, "cases": []})

    assert json.loads(target.read_text(encoding="utf-8"))["cases"] == []
    assert os.stat(target).st_mode & 0o777 == 0o600
    assert os.stat(target.parent).st_mode & 0o777 == 0o700
    with pytest.raises(ValueError, match="must stay under .firstroll"):
        evaluator.write_private_packets(tmp_path / "evals" / "unsafe.json", {})


def test_recording_transport_counts_failed_attempt_without_error_detail(monkeypatch) -> None:
    def fail(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        raise RuntimeError("PRIVATE_PROVIDER_ERROR")

    monkeypatch.setattr(evaluator.DeepSeekStudyService, "_request_json", staticmethod(fail))
    recorder = evaluator.SafeRecordingTransport()

    with pytest.raises(RuntimeError):
        recorder("https://api.deepseek.com/chat/completions", {}, "PRIVATE_KEY")

    assert len(recorder.calls) == 1
    assert recorder.calls[0] | {"latency_seconds": 0.0} == {
        "endpoint": "completions",
        "status": "failed",
        "latency_seconds": 0.0,
        "model": None,
        "usage": {},
    }
    assert recorder.calls[0]["latency_seconds"] >= 0
    assert "PRIVATE" not in str(recorder.calls)
