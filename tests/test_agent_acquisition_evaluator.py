from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.backend.criticism import ReviewSource
from app.backend.evidence import EvidencePacket
from app.backend.local_research_agent import AcquiredSources
from app.backend.research_agent_contract import ToolName
from tools import evaluate_agent_acquisition as evaluator


ROOT = Path(__file__).resolve().parents[1]
PROGRAMME = ROOT / "evals" / "autonomous_agent_programme.json"


def review() -> ReviewSource:
    return ReviewSource(
        source_id="R1",
        provider="Guardian",
        review_id="review-1",
        title="Attributed review",
        summary=(
            "The critic reports a recurring framing pattern that a filmmaker can compare during "
            "close viewing of the selected film."
        ),
        author="A Critic",
        url="https://theguardian.com/film/review-1",
        language="en",
    )


def packet() -> EvidencePacket:
    return EvidencePacket.from_retrieval(
        {
            "title": "Example Film",
            "year": 2024,
            "credits": {"directors": ["Example Director"]},
        },
        {
            "passages": [
                {
                    "title": "Framing Theory",
                    "page": 2,
                    "language": "en",
                    "excerpt": (
                        "Framing creates repeatable spatial relations that can be logged and "
                        "compared without treating a hypothesis as a directly observed fact."
                    ),
                }
            ]
        },
        "How does framing organise uncertainty?",
        reviews=[review()],
    )


class Acquirer:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls = 0

    def status(self) -> dict[str, dict[str, Any]]:
        return {ToolName.FETCH_GUARDIAN_REVIEWS.value: {"state": "ready"}}

    def acquire(self, tool: ToolName, film: dict[str, Any]) -> AcquiredSources:
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def programme() -> dict[str, Any]:
    return json.loads(PROGRAMME.read_text(encoding="utf-8"))


def approved_programme() -> dict[str, Any]:
    value = programme()
    experiment = evaluator.acquisition_experiment(value)
    proposed = experiment["proposed_budget"]
    value["status"] = "a01_acquisition_ablation_approved"
    value["owner_mandate"]["paid_model_or_provider_calls_authorised"] = True
    experiment["status"] = "approved_one_run"
    experiment["paid_budget_confirmation"] = {
        "confirmed": True,
        "authorisation_consumed": False,
        "approved_maximum_model_planner_calls": proposed["maximum_model_planner_calls"],
        "approved_maximum_physical_provider_calls": proposed["maximum_physical_provider_calls"],
        "approved_maximum_external_tool_turns_per_active_lane": proposed[
            "maximum_external_tool_turns_per_active_lane"
        ],
    }
    return value


def test_current_programme_refuses_consumed_acquisition_ablation() -> None:
    assert evaluator.comparison_authorised(programme()) is False


def test_acquisition_authorisation_requires_every_exact_budget() -> None:
    approved = approved_programme()
    mismatched = approved_programme()
    evaluator.acquisition_experiment(mismatched)["paid_budget_confirmation"][
        "approved_maximum_physical_provider_calls"
    ] += 1
    consumed = approved_programme()
    evaluator.acquisition_experiment(consumed)["paid_budget_confirmation"][
        "authorisation_consumed"
    ] = True

    assert evaluator.comparison_authorised(approved) is True
    assert evaluator.comparison_authorised(mismatched) is False
    assert evaluator.comparison_authorised(consumed) is False


def test_acquisition_run_inputs_must_match_approved_paths(tmp_path: Path) -> None:
    value = programme()
    experiment = evaluator.acquisition_experiment(value)
    confirmation = experiment["paid_budget_confirmation"]
    args = evaluator.argparse.Namespace(
        programme=evaluator.DEFAULT_PROGRAMME,
        cases=evaluator.ROOT / confirmation["approved_case_suite_path"],
        reference=evaluator.ROOT / confirmation["approved_identity_reference_path"],
        output=evaluator.ROOT / confirmation["approved_report_path"],
        private_packets=evaluator.ROOT / confirmation["approved_private_packet_path"],
        run_lock=evaluator.ROOT / confirmation["approved_run_lock_path"],
    )

    evaluator.require_authorised_run_inputs(args, experiment)
    args.output = tmp_path / "unapproved.json"
    with pytest.raises(SystemExit, match="output path is not authorised"):
        evaluator.require_authorised_run_inputs(args, experiment)


def test_acquisition_case_loads_the_frozen_canonical_identity() -> None:
    spec = evaluator.load_case(
        evaluator.DEFAULT_CASES,
        evaluator.DEFAULT_REFERENCE,
        "the-thing-ambiguous-identity",
    )

    assert spec["film_id"] == "wikidata:Q210756"
    assert spec["expected"] == {
        "title": "The Thing",
        "year": 1982,
        "director": "John Carpenter",
    }


def test_initial_packet_rejects_identity_drift_before_preparation(monkeypatch) -> None:
    spec = evaluator.load_case(
        evaluator.DEFAULT_CASES,
        evaluator.DEFAULT_REFERENCE,
        "the-thing-ambiguous-identity",
    )
    monkeypatch.setattr(
        evaluator.main.discovery_service,
        "detail",
        lambda _film_id: {
            "film": {
                "title": "The Thing",
                "year": 2011,
                "credits": {"directors": ["Matthijs van Heijningen Jr."]},
            }
        },
    )

    with pytest.raises(RuntimeError, match="wrong canonical film identity"):
        evaluator.prepare_initial_packet(spec)


def test_frozen_source_pool_replays_one_physical_observation() -> None:
    underlying = Acquirer(AcquiredSources(provider="Guardian", reviews=(review(),)))
    pool = evaluator.FrozenSourcePool(underlying)

    first = pool.acquire(ToolName.FETCH_GUARDIAN_REVIEWS, {})
    second = pool.acquire(ToolName.FETCH_GUARDIAN_REVIEWS, {})

    assert first is second
    assert underlying.calls == 1
    assert pool.safe_metrics()["physical_provider_calls"] == 1
    assert pool.safe_metrics()["logical_provider_calls"] == 2
    assert pool.safe_metrics()["cache_hits"] == 1


def test_frozen_source_pool_replays_safe_failure_without_retry() -> None:
    underlying = Acquirer(RuntimeError("PRIVATE_PROVIDER_FAILURE"))
    pool = evaluator.FrozenSourcePool(underlying)

    with pytest.raises(RuntimeError, match="PRIVATE_PROVIDER_FAILURE"):
        pool.acquire(ToolName.FETCH_GUARDIAN_REVIEWS, {})
    with pytest.raises(RuntimeError, match="frozen provider observation"):
        pool.acquire(ToolName.FETCH_GUARDIAN_REVIEWS, {})

    assert underlying.calls == 1
    metrics = pool.safe_metrics()
    assert metrics["physical_attempts"] == [
        {
            "tool": "fetch_guardian_reviews",
            "status": "failed",
            "duration_seconds": metrics["physical_attempts"][0]["duration_seconds"],
        }
    ]
    assert "PRIVATE_PROVIDER_FAILURE" not in str(metrics)


def test_private_packet_blinding_is_stable_and_complete() -> None:
    packets = {
        "fixed_no_acquisition": packet(),
        "deterministic_gap_router": packet(),
        "model_gap_planner": packet(),
    }

    first, mapping = evaluator.blind_private_packets(
        packets,
        case_id="case-1",
        revision="abc123",
    )
    second, second_mapping = evaluator.blind_private_packets(
        packets,
        case_id="case-1",
        revision="abc123",
    )

    assert first == second
    assert mapping == second_mapping
    assert set(mapping) == {"A", "B", "C"}
    assert set(mapping.values()) == set(packets)
    assert {item["blind_id"] for item in first} == set(mapping)
    assert all("lane" not in item for item in first)


def test_acquisition_targets_require_both_active_lanes_and_shared_budget() -> None:
    lanes = [
        {
            "lane": "fixed_no_acquisition",
            "initial_packet_fingerprint": "same",
            "external_tool_calls": 0,
            "model_planner_calls": 0,
        },
        {
            "lane": "deterministic_gap_router",
            "initial_packet_fingerprint": "same",
            "status": "passed",
            "independent_origins": 2,
            "external_tool_calls": 2,
            "model_planner_calls": 0,
        },
        {
            "lane": "model_gap_planner",
            "initial_packet_fingerprint": "same",
            "status": "passed",
            "independent_origins": 2,
            "external_tool_calls": 2,
            "model_planner_calls": 2,
        },
    ]

    targets = evaluator.evaluate_targets(
        lanes,
        {
            "physical_provider_calls": 3,
            "physical_attempts": [
                {"tool": "fetch_guardian_reviews"},
                {"tool": "fetch_crossref_research"},
                {"tool": "search_youtube_resources"},
            ],
        },
        evaluator.acquisition_experiment(programme()),
    )

    assert all(item["status"] == "passed" for item in targets)
