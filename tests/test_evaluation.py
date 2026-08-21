from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.study_observability import STUDY_STAGE_NAMES  # noqa: E402
from tools.evaluate_workflow import aggregate, identity_matches, percentile, score_study  # noqa: E402


def complete_study() -> dict:
    sections = []
    for index in range(4):
        sections.append(
            {
                "status": "viewing_hypothesis",
                "hypothesis": "Test whether this pattern may organise the scene.",
                "mechanism": "It could work through a contrast between two formal choices.",
                "alternative_reading": "If the pattern fails, compare a different explanation.",
                "verify": "Log each instance, count it and compare the two groups.",
                "source_ids": [f"S{index + 1}"],
                "critic_claim_ids": [],
                "attributed_source_ids": [],
            }
        )
    return {
        "title": "A sufficiently specific title",
        "central_argument": "A calibrated central argument long enough for the generated schema.",
        "sections": sections,
        "creator_intent_boundary": "No creator intention is inferred without a direct source.",
        "next_viewing": ["One", "Two", "Three"],
        "sources": [{"id": f"S{index + 1}"} for index in range(4)],
        "critical_claims": [],
        "attributed_sources": [],
        "quality": {"status": "passed", "score": 1, "repair_attempted": False},
    }


def test_frozen_agent_cases_cover_identity_and_evidence_challenges() -> None:
    suite = json.loads((ROOT / "evals" / "agent_cases.json").read_text(encoding="utf-8"))

    assert suite["suite_id"] == "firstroll-agent-comparison-v1"
    assert len(suite["cases"]) == 5
    assert {case["challenge"] for case in suite["cases"]} >= {
        "ambiguous title requiring explicit film selection",
        "appropriate limitation and abstention under sparse evidence",
        "formal specificity without clip evidence",
    }


def test_pre_agent_scorecard_freezes_steps_journeys_and_entry_targets() -> None:
    scorecard_path = ROOT / "evals" / "pre_agent_scorecard.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    suite = json.loads(
        (ROOT / scorecard["frozen_baseline"]["suite_path"]).read_text(encoding="utf-8")
    )
    result = json.loads(
        (ROOT / scorecard["frozen_baseline"]["result_path"]).read_text(encoding="utf-8")
    )

    baseline = scorecard["frozen_baseline"]
    summary = result["summary"]
    assert scorecard["programme_id"] == "firstroll-pre-agent-hardening-v1"
    assert baseline["suite_id"] == suite["suite_id"] == result["suite_id"]
    assert baseline["recorded_at"] == result["recorded_at"]
    assert baseline["attempted_cases"] == summary["case_count"]
    assert baseline["completed_cases"] == summary["successful_cases"]
    assert baseline["operational_failure_rate"] == summary["operational_failure_rate"]
    assert baseline["mean_quality_score_completed"] == summary["mean_quality_score"]
    assert baseline["p50_end_to_end_seconds"] == summary["latency_seconds"]["p50_end_to_end"]
    assert baseline["p95_end_to_end_seconds"] == summary["latency_seconds"]["p95_end_to_end"]

    prompt_tokens = [
        call["usage"]["prompt_tokens"]
        for case in result["cases"]
        for call in case.get("model_calls", [])
    ]
    assert prompt_tokens == baseline["completed_prompt_tokens"]
    assert baseline["median_prompt_tokens_completed"] == 7882.5
    assert baseline["p95_prompt_tokens_completed"] == percentile(prompt_tokens, 0.95)

    workflow_checkpoint = scorecard["measured_checkpoints"]["complete_workflow"]
    workflow_result = json.loads(
        (ROOT / workflow_checkpoint["result_path"]).read_text(encoding="utf-8")
    )
    assert workflow_result["schema_version"] == 2
    assert workflow_checkpoint["source_revision"] == workflow_result["source_revision"]
    assert workflow_checkpoint["configuration_fingerprint"] == workflow_result["environment"][
        "configuration"
    ]["sha256"]
    assert workflow_checkpoint["completed_cases"] == workflow_result["summary"][
        "successful_cases"
    ]
    assert workflow_checkpoint["mean_quality_score_completed"] == workflow_result["summary"][
        "mean_quality_score"
    ]
    assert workflow_checkpoint["p50_end_to_end_seconds"] == workflow_result["summary"][
        "latency_seconds"
    ]["p50_end_to_end"]
    current_prompt_tokens = [
        call["usage"]["prompt_tokens"]
        for case in workflow_result["cases"]
        if case["status"] == "passed"
        for call in case.get("model_calls", [])
    ]
    assert workflow_checkpoint["median_prompt_tokens_completed"] == 9577.0
    assert workflow_checkpoint["p95_prompt_tokens_completed"] == percentile(
        current_prompt_tokens, 0.95
    )

    packet_checkpoint = scorecard["measured_checkpoints"]["packet_preparation"]
    packet_result = json.loads(
        (ROOT / packet_checkpoint["result_path"]).read_text(encoding="utf-8")
    )
    assert packet_checkpoint["source_revision"] == packet_result["source_revision"]
    assert packet_checkpoint["configuration_fingerprint"] == packet_result["environment"][
        "configuration"
    ]["sha256"]
    assert packet_checkpoint["attempted_samples"] == packet_result["summary"]["sample_count"]
    assert packet_checkpoint["failed_samples"] == packet_result["summary"]["failed_samples"]
    assert packet_checkpoint["cold_p95_ms"] == packet_result["summary"]["cold"]["p95_ms"]
    assert packet_checkpoint["warm_p95_ms"] == packet_result["summary"]["warm"]["p95_ms"]

    ui_checkpoint = scorecard["measured_checkpoints"]["ui_hierarchy"]
    ui_result = json.loads(
        (ROOT / ui_checkpoint["result_path"]).read_text(encoding="utf-8")
    )
    assert ui_checkpoint["source_revision"] == ui_result["source_revision"]
    assert ui_checkpoint["journeys_assessed"] == ui_result["summary"]["journeys_assessed"]
    assert ui_checkpoint["journey_blockers"] == ui_result["summary"]["journey_blockers"]
    assert ui_checkpoint["visible_response_p95_ms"] == ui_result["summary"][
        "visible_response_p95_ms"
    ]
    assert ui_checkpoint["mobile_horizontal_overflow_px"] == ui_result["summary"][
        "mobile_horizontal_overflow_px"
    ]
    assert len(ui_result["journeys"]) == 6
    assert all(journey["status"].startswith("passed") for journey in ui_result["journeys"])

    state_checkpoint = scorecard["measured_checkpoints"]["ui_states_accessibility"]
    state_result = json.loads(
        (ROOT / state_checkpoint["result_path"]).read_text(encoding="utf-8")
    )
    assert state_checkpoint["source_revision"] == state_result["source_revision"]
    assert state_checkpoint["state_scenarios_assessed"] == state_result["summary"][
        "state_scenarios_assessed"
    ]
    assert state_checkpoint["state_scenario_failures"] == state_result["summary"][
        "state_scenario_failures"
    ]
    assert state_checkpoint["axe_violations"] == state_result["summary"]["axe_violations"]
    assert state_checkpoint["critical_accessibility_defects"] == state_result["summary"][
        "critical_accessibility_defects"
    ]
    assert all(item["status"] == "passed" for item in state_result["state_scenarios"])
    assert all(item["status"] == "passed" for item in state_result["keyboard_tablists"])

    latency_checkpoint = scorecard["measured_checkpoints"]["packet_latency_prewarm"]
    latency_result = json.loads(
        (ROOT / latency_checkpoint["result_path"]).read_text(encoding="utf-8")
    )
    assert latency_result["schema_version"] == 2
    assert latency_checkpoint["source_revision"] == latency_result["source_revision"]
    assert latency_checkpoint["configuration_fingerprint"] == latency_result["environment"][
        "configuration"
    ]["sha256"]
    assert latency_checkpoint["cold_p95_ms"] == latency_result["summary"]["cold"]["p95_ms"]
    assert latency_checkpoint["warm_p95_ms"] == latency_result["summary"]["warm"]["p95_ms"]
    assert latency_checkpoint["cold_p95_relative_reduction"] == round(
        1
        - latency_result["summary"]["cold"]["p95_ms"]
        / packet_result["summary"]["cold"]["p95_ms"],
        6,
    )
    assert latency_checkpoint["embedding_warmup_p95_ms"] == latency_result["summary"][
        "embedding_warmup"
    ]["cold_processes"]["p95_ms"]
    assert latency_checkpoint["packet_metrics_match_baseline"] is True
    assert latency_result["summary"]["packet_metrics"] == packet_result["summary"][
        "packet_metrics"
    ]

    quality_checkpoint = scorecard["measured_checkpoints"]["packet_quality_baseline"]
    quality_result = json.loads(
        (ROOT / quality_checkpoint["result_path"]).read_text(encoding="utf-8")
    )
    assert quality_checkpoint["source_revision"] == quality_result["source_revision"]
    assert quality_checkpoint["fixture_fingerprint"] == quality_result["fixture_fingerprint"]
    assert quality_checkpoint["case_count"] == quality_result["aggregate"]["case_count"]
    assert quality_checkpoint["assessed_cases"] == quality_result["aggregate"][
        "assessed_cases"
    ]
    assert quality_checkpoint["passed_packets"] == quality_result["aggregate"][
        "packet_status_counts"
    ]["passed"]
    assert quality_checkpoint["limited_packets"] == quality_result["aggregate"][
        "packet_status_counts"
    ]["limited"]
    assert quality_checkpoint["mean_duplicate_ratio"] == quality_result["aggregate"][
        "mean_duplicate_ratio"
    ]
    assert quality_checkpoint["flagged_instruction_items"] == quality_result["aggregate"][
        "flagged_instruction_items"
    ]
    assert quality_checkpoint["model_calls"] == quality_result["aggregate"]["model_calls"]

    assert scorecard["latency_stages"] == list(STUDY_STAGE_NAMES)

    journey_ids = [journey["id"] for journey in scorecard["user_journeys"]]
    assert journey_ids == [f"J{index:02d}" for index in range(1, 7)]
    assert all(journey["success"] for journey in scorecard["user_journeys"])
    assert all(
        "local_private_edition" in journey["runtimes"]
        for journey in scorecard["user_journeys"]
    )

    steps = scorecard["steps"]
    assert [step["id"] for step in steps] == [f"S{index:02d}" for index in range(1, 13)]
    next_indices = [index for index, step in enumerate(steps) if step["status"] == "next"]
    assert len(next_indices) == 1
    next_index = next_indices[0]
    assert all(step["status"] == "complete" for step in steps[:next_index])
    assert all(
        step["status"] in {"queued", "blocked_by_entry_gate"}
        for step in steps[next_index + 1 :]
    )

    target_ids = set(scorecard["targets"])
    required_targets = set(scorecard["agent_entry_gate"]["required_target_ids"])
    assert required_targets <= target_ids
    assert scorecard["agent_entry_gate"]["required_completed_steps"] == [
        f"S{index:02d}" for index in range(1, 12)
    ]
    assert {item["id"] for item in scorecard["human_packet_rubric"]} == {
        "focus_relevance",
        "traceability",
        "source_diversity",
        "epistemic_calibration",
        "filmmaker_actionability",
    }
    assert scorecard["measurement_protocol"]["percentile_method"] == (
        "linear_interpolation_n_minus_1"
    )
    assert '"week"' not in scorecard_path.read_text(encoding="utf-8").casefold()


def test_identity_match_requires_title_year_and_director() -> None:
    expected = {"title": "The Thing", "year": 1982, "director": "John Carpenter"}
    assert identity_matches(
        {"title": "The Thing", "year": 1982, "directors": ["John Carpenter"]}, expected
    )
    assert not identity_matches(
        {"title": "The Thing", "year": 2011, "directors": ["Matthijs van Heijningen Jr."]},
        expected,
    )


def test_quality_proxy_rewards_valid_grounded_structure() -> None:
    scored = score_study(complete_study(), identity_ok=True)

    assert scored["score"] == 100
    assert scored["valid_citations"] is True
    assert scored["calibrated_section_ratio"] == 1
    assert scored["observable_verification_ratio"] == 1


def test_quality_proxy_deducts_generic_prose_without_rejecting_an_accepted_study() -> None:
    study = complete_study()
    study["quality"] = {
        "status": "passed",
        "score": 0.8,
        "repair_attempted": False,
        "central_issues": [],
        "sections": [{"section": 1, "issues": ["generic_language"]}],
    }

    scored = score_study(study, identity_ok=True)

    assert scored["score"] == 95
    assert scored["components"]["deterministic_quality_gate"] == 20
    assert scored["quality_gate_status"] == "passed"


def test_quality_proxy_penalises_invalid_citations_and_missing_calibration() -> None:
    study = complete_study()
    study["sections"][0]["source_ids"] = ["S99"]
    study["sections"][0]["hypothesis"] = "The pattern definitively organises the scene."
    study["sections"][0]["mechanism"] = "A contrast definitively organises the scene."
    study["sections"][0]["alternative_reading"] = None
    scored = score_study(study, identity_ok=True)

    assert scored["score"] < 100
    assert scored["valid_citations"] is False
    assert scored["calibrated_section_ratio"] == 0.75


def test_quality_proxy_treats_gate_failure_as_a_blocking_acceptance_failure() -> None:
    study = complete_study()
    study["quality"] = {
        "status": "insufficient_evidence",
        "score": 0.96,
        "repair_attempted": True,
        "central_issues": [],
        "sections": [{"section": 1, "issues": ["mechanism_missing"]}],
    }

    scored = score_study(study, identity_ok=True)

    assert scored["score"] == 75
    assert scored["components"]["deterministic_quality_gate"] == 0
    assert scored["quality_gate_failed_sections"][0]["issues"] == ["mechanism_missing"]


def test_aggregate_records_failure_rate_and_latency_percentiles() -> None:
    results = [
        {
            "status": "passed",
            "failure_stage": None,
            "quality": {"score": 90, "quality_gate_status": "passed"},
            "latency_seconds": {"study": 8.0, "end_to_end": 10.0},
            "model_calls": [{"usage": {"total_tokens": 100}}],
        },
        {
            "status": "failed",
            "failure_stage": "study",
            "quality": {"score": 0},
            "latency_seconds": {"study": 18.0, "end_to_end": 20.0},
            "model_calls": [],
        },
    ]

    summary = aggregate(results)
    assert summary["failure_rate"] == 0.5
    assert summary["operational_failure_rate"] == 0.5
    assert summary["quality_gate_pass_rate"] == 1
    assert summary["quality_acceptance_failure_rate"] == 0
    assert summary["mean_quality_score"] == 90
    assert summary["latency_seconds"]["p50_end_to_end"] == 15
    assert summary["total_tokens"] == 100
    assert percentile([10, 20], 0.95) == 19.5
