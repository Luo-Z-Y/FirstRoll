from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.evidence import EvidencePacket
from tools.benchmark_evidence_packet import (
    assert_report_redacted,
    latency_summary,
    packet_metric_summary,
    percentile,
    safe_packet_metrics,
    stage_summary,
)


PRIVATE_PASSAGE = "PRIVATE_PACKET_PASSAGE_MUST_NOT_ENTER_BENCHMARK"
PRIVATE_QUESTION = "PRIVATE_PACKET_QUESTION_MUST_NOT_ENTER_BENCHMARK"


def observability(duration_ms: float) -> dict:
    return {
        "schema_version": 1,
        "status": "completed",
        "stages": [
            {
                "name": "packet_assembly",
                "status": "completed",
                "duration_ms": duration_ms,
                "attempts": 1,
                "failures": 0,
            }
        ],
        "counts": {"theory_sources": 1},
    }


def test_packet_metrics_expose_only_aggregate_shape() -> None:
    packet = EvidencePacket.from_retrieval(
        {"title": "Private example", "year": 2026},
        {
            "method": "hybrid_rrf",
            "candidate_count": 12,
            "passages": [
                {
                    "title": "Private book",
                    "page": 12,
                    "excerpt": PRIVATE_PASSAGE,
                    "language": "en",
                }
            ],
        },
        PRIVATE_QUESTION,
    )

    metrics = safe_packet_metrics(packet)

    assert metrics["theory_candidates"] == 12
    assert metrics["theory_sources"] == 1
    assert metrics["theory_unselected"] == 11
    assert metrics["attributed_candidates"] == 0
    assert metrics["attributed_omitted"] == 0
    assert metrics["theory_characters"] == len(PRIVATE_PASSAGE)
    assert metrics["packet_json_characters"] > len(PRIVATE_PASSAGE)
    serialised = json.dumps(metrics)
    assert PRIVATE_PASSAGE not in serialised
    assert PRIVATE_QUESTION not in serialised
    assert "Private book" not in serialised


def test_packet_benchmark_summaries_use_recorded_samples_only() -> None:
    samples = [
        {
            "status": "completed",
            "packet_prepare_ms": 10.0,
            "packet_metrics": {"theory_sources": 4, "packet_json_characters": 1000},
            "observability": observability(2.0),
        },
        {
            "status": "completed",
            "packet_prepare_ms": 20.0,
            "packet_metrics": {"theory_sources": 6, "packet_json_characters": 2000},
            "observability": observability(4.0),
        },
        {"status": "failed", "failure_stage": "semantic_retrieval"},
    ]

    latency = latency_summary(samples)
    stages = stage_summary(samples)
    packet = packet_metric_summary(samples)

    assert latency == {
        "attempted": 3,
        "completed": 2,
        "failed": 1,
        "mean_ms": 15.0,
        "p50_ms": 15.0,
        "p95_ms": 19.5,
        "minimum_ms": 10.0,
        "maximum_ms": 20.0,
    }
    assert stages["packet_assembly"]["p50_ms"] == 3.0
    assert stages["packet_assembly"]["status_counts"] == {"completed": 2}
    assert packet["theory_sources"] == {"minimum": 4, "median": 5.0, "maximum": 6}
    assert percentile([10, 20], 0.95) == 19.5


def test_packet_report_rejects_questions_and_evidence_fields() -> None:
    specs = [{"redaction_values": [PRIVATE_QUESTION]}]

    with pytest.raises(ValueError, match="question"):
        assert_report_redacted({"question": "not allowed"}, specs)
    with pytest.raises(ValueError, match="film query"):
        assert_report_redacted({"safe": PRIVATE_QUESTION}, specs)
