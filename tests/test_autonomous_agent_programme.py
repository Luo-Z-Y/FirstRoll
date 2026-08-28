from __future__ import annotations

import json
from pathlib import Path

from app.backend.agent_evidence import MIN_RECOVERED_INDEPENDENT_ORIGINS
from app.backend.research_agent_contract import EXTERNAL_TOOLS


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "evals" / "autonomous_agent_programme.json"


def programme() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_autonomous_programme_keeps_paid_and_production_boundaries_closed() -> None:
    value = programme()

    assert value["status"] == "all_causal_harnesses_implemented_awaiting_gated_budgets"
    assert value["owner_mandate"]["implementation_authorised"] is True
    assert value["owner_mandate"]["provider_adapter_changes_authorised"] is True
    assert value["owner_mandate"]["paid_model_or_provider_calls_authorised"] is False
    assert value["owner_mandate"]["hosted_route_authorised"] is False
    assert value["owner_mandate"]["production_cutover_authorised"] is False
    assert value["boundaries"]["fixed_production_workflow_unchanged"] is True
    assert value["boundaries"]["clip_analysis"] == "deferred_until_text_agent_accepted"


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


def test_autonomous_experiments_are_sequential_and_unfunded() -> None:
    value = programme()
    experiments = {item["id"]: item for item in value["experiments"]}

    assert experiments["A01"]["status"] == "harness_implemented_awaiting_budget"
    assert experiments["A01"]["lanes"] == [
        "fixed_no_acquisition",
        "deterministic_gap_router",
        "model_gap_planner",
    ]
    assert experiments["A02"]["status"] == "harness_implemented_awaiting_budget"
    assert experiments["A03"]["status"] == "harness_implemented_blocked_by_A01"
    assert experiments["A03"]["proposed_budget"] == {
        "generation_repetitions_per_lane": 10,
        "expected_minimum_synthesis_calls": 20,
        "maximum_synthesis_calls": 60,
        "planner_calls": 0,
        "provider_calls": 0,
    }
    assert experiments["A03"]["private_human_review_repetitions"] == [1, 5, 10]
    assert all(item["paid_budget_confirmation"] is None for item in experiments.values())
    assert (ROOT / "docs" / "AUTONOMOUS_AGENT_PROGRAMME.md").is_file()
