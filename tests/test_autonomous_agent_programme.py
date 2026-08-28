from __future__ import annotations

import json
from pathlib import Path

from app.backend.agent_evidence import MIN_RECOVERED_INDEPENDENT_ORIGINS
from app.backend.research_agent_contract import EXTERNAL_TOOLS


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "evals" / "autonomous_agent_programme.json"


def programme() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_autonomous_programme_opens_only_the_exact_local_paid_gate() -> None:
    value = programme()

    assert value["status"] == "a02_structural_repair_ablation_approved"
    assert value["owner_mandate"]["implementation_authorised"] is True
    assert value["owner_mandate"]["provider_adapter_changes_authorised"] is True
    assert value["owner_mandate"]["paid_model_or_provider_calls_authorised"] is True
    assert value["owner_mandate"]["hosted_route_authorised"] is False
    assert value["owner_mandate"]["production_cutover_authorised"] is False
    assert value["boundaries"]["fixed_production_workflow_unchanged"] is True
    assert value["boundaries"]["clip_analysis"] == "deferred_until_text_agent_accepted"


def test_A01_machine_failure_is_complete_and_human_review_stays_closed() -> None:
    result = json.loads(
        (ROOT / "evals" / "results" / "autonomous-agent-acquisition-2026-08-28.json").read_text(
            encoding="utf-8"
        )
    )
    failed = [item["target_id"] for item in result["targets"] if item["status"] == "failed"]

    assert result["source_revision"] == "497be3c1c9225bbe77b3a5792b45188ae3879861"
    assert result["source_pool"]["physical_provider_calls"] == 4
    assert sum(item["model_planner_calls"] for item in result["lanes"]) == 3
    assert failed == ["deterministic_lane_completed", "model_lane_completed"]
    assert result["summary"]["machine_targets_passed"] is False
    assert result["summary"]["private_packet_snapshot_written"] is False
    assert result["summary"]["human_review_ready"] is False


def test_autonomous_programme_matches_the_independent_origin_and_provider_contract() -> None:
    value = programme()
    tools = {item["tool"] for item in value["provider_allow_list"]}

    assert value["foundation"]["minimum_recovered_independent_origins"] == (
        MIN_RECOVERED_INDEPENDENT_ORIGINS
    )
    assert tools == {tool.value for tool in EXTERNAL_TOOLS}
    assert value["foundation"]["tool_gap_capability_pair_validated"] is True
    assert value["foundation"]["no_addressable_tool_outcome"] == (
        "insufficient_evidence_without_provider_call"
    )
    assert value["foundation"]["deterministic_baseline_available"] is True
    assert value["foundation"]["crossref_agent_provider_available"] is True
    assert value["solid_definition"]["value_against_deterministic_baseline_required"] is True
    assert value["solid_definition"]["minimum_comparable_observations_per_critical_strategy"] == 20
    assert value["autonomous_finisher"] == {
        "claim_paths_audited_exactly_once": True,
        "claim_labels": [
            "directly_supported",
            "reasonable_interpretation",
            "unsupported",
            "stronger_than_evidence",
        ],
        "interpretive_claims_cannot_be_directly_supported": True,
        "maximum_initial_and_reaudit_calls": 2,
        "maximum_targeted_editor_calls": 1,
        "maximum_editor_paths": 4,
        "reaudit_required_after_edit": True,
        "maximum_filmmaker_coach_calls": 1,
        "coach_actions": ["log", "compare", "count", "track", "mark", "inspect"],
        "maximum_total_model_calls": 4,
        "http_route_registered": False,
        "provider_validation": "not_authorised",
    }
    assert value["durable_local_engine"] == {
        "checkpoint_directory": ".firstroll/autonomous-runs",
        "directory_mode": "0700",
        "checkpoint_mode": "0600",
        "owner_match_required": True,
        "atomic_phase_writes": True,
        "cancellation_checked_between_phases": True,
        "interrupted_in_flight_paid_phase_replayed_automatically": False,
        "resumable_phases": ["research", "audit", "edit", "reaudit", "coach"],
        "hosted_or_multi_instance_ready": False,
    }


def test_autonomous_experiments_have_exact_sequential_authorisations() -> None:
    value = programme()
    experiments = {item["id"]: item for item in value["experiments"]}

    assert experiments["A01"]["status"] == "completed_machine_failed"
    assert experiments["A01"]["lanes"] == [
        "fixed_no_acquisition",
        "deterministic_gap_router",
        "model_gap_planner",
    ]
    assert experiments["A02"]["status"] == "approved_one_run"
    assert experiments["A03"]["status"] == "blocked_by_A01_machine_failure"
    assert experiments["A03"]["proposed_budget"] == {
        "generation_repetitions_per_lane": 10,
        "expected_minimum_synthesis_calls": 20,
        "maximum_synthesis_calls": 60,
        "planner_calls": 0,
        "provider_calls": 0,
    }
    assert experiments["A03"]["private_human_review_repetitions"] == [1, 5, 10]
    assert experiments["A01"]["paid_budget_confirmation"] == {
        "confirmed": True,
        "recorded_at": "2026-08-28T15:36:51Z",
        "decided_by": "repository_owner",
        "approved_maximum_model_planner_calls": 3,
        "approved_maximum_physical_provider_calls": 5,
        "approved_maximum_external_tool_turns_per_active_lane": 3,
        "approved_case_suite_path": "evals/agent_cases.json",
        "approved_identity_reference_path": ("evals/results/baseline-reliability-2026-08-21.json"),
        "approved_report_path": "evals/results/autonomous-agent-acquisition-2026-08-28.json",
        "approved_private_packet_path": (
            ".firstroll/evaluations/autonomous-agent-acquisition-packets-2026-08-28.json"
        ),
        "approved_run_lock_path": (
            ".firstroll/evaluations/autonomous-agent-acquisition-2026-08-28.lock"
        ),
        "authorisation_consumed": True,
    }
    assert experiments["A01"]["preflight_history"] == [
        {
            "recorded_at": "2026-08-28T15:47:53Z",
            "source_revision": "c32e2e58e1ca10143dfe2de689aec26f254f2cbe",
            "status": "failed_before_lock",
            "failure_category": "canonical_film_identity_not_bound",
            "model_planner_calls": 0,
            "physical_provider_calls": 0,
            "authorisation_consumed": False,
        }
    ]
    assert experiments["A01"]["machine_result"] == {
        "result_path": "evals/results/autonomous-agent-acquisition-2026-08-28.json",
        "source_revision": "497be3c1c9225bbe77b3a5792b45188ae3879861",
        "outcome": "machine_failed_no_human_review",
        "model_planner_calls": 3,
        "physical_provider_calls": 4,
        "logical_provider_calls": 6,
        "deterministic_external_tool_turns": 3,
        "model_external_tool_turns": 3,
        "failed_targets": [
            "deterministic_lane_completed",
            "model_lane_completed",
        ],
        "private_packet_snapshot_written": False,
        "human_review_performed": False,
    }
    assert experiments["A02"]["paid_budget_confirmation"] == {
        "confirmed": True,
        "recorded_at": "2026-08-28T15:36:51Z",
        "decided_by": "repository_owner",
        "approved_fault_scenarios": 3,
        "approved_repetitions_per_lane_per_scenario": 3,
        "approved_expected_model_calls": 18,
        "approved_maximum_model_calls": 36,
        "approved_report_path": "evals/results/autonomous-agent-repair-2026-08-28.json",
        "approved_run_lock_path": ".firstroll/evaluations/autonomous-agent-repair-2026-08-28.lock",
        "authorisation_consumed": False,
    }
    assert experiments["A03"]["paid_budget_confirmation"] is None
    assert (ROOT / "docs" / "AUTONOMOUS_AGENT_PROGRAMME.md").is_file()
