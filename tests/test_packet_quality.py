from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.evidence import EvidencePacket
from app.backend.packet_quality import assess_evidence_packet
from tools.evaluate_packet_quality import (
    assert_report_redacted,
    build_packet,
    check_case_expectations,
)


PRIVATE_EVIDENCE = "PRIVATE_PACKET_QUALITY_TEXT_MUST_NOT_ENTER_REPORT"


def test_packet_quality_detects_duplicates_without_returning_evidence_text() -> None:
    packet = EvidencePacket.from_retrieval(
        {"title": "Example", "year": 2024, "directors": ["Director"]},
        {
            "method": "test",
            "candidate_count": 8,
            "passages": [
                {
                    "title": "Framework one",
                    "page": 1,
                    "language": "en",
                    "excerpt": PRIVATE_EVIDENCE + " framing duration relation comparison",
                },
                {
                    "title": "Framework duplicate",
                    "page": 2,
                    "language": "en",
                    "excerpt": PRIVATE_EVIDENCE + " framing duration relation comparison",
                },
            ],
        },
        "framing and duration",
    )

    assessment = assess_evidence_packet(
        packet,
        expected_identity={"title": "Example", "year": 2024, "director": "Director"},
    )

    assert assessment["status"] == "limited"
    assert assessment["duplication"]["duplicate_items"] == 1
    assert "duplicate_evidence_present" in assessment["issues"]
    assert "film_specific_evidence_sparse" in assessment["issues"]
    assert PRIVATE_EVIDENCE not in json.dumps(assessment)


def test_packet_quality_blocks_missing_theory_and_wrong_identity() -> None:
    packet = EvidencePacket.from_retrieval(
        {"title": "Wrong Film", "year": 2025, "directors": ["Wrong Director"]},
        {"method": "test", "candidate_count": 0, "passages": []},
        "editing",
    )

    assessment = assess_evidence_packet(
        packet,
        expected_identity={"title": "Expected Film", "year": 2024, "director": "Director"},
    )

    assert assessment["status"] == "failed"
    assert assessment["sufficiency"]["state"] == "insufficient"
    assert set(assessment["issues"]) >= {
        "film_identity_mismatch",
        "theory_evidence_missing",
    }


def test_packet_quality_reports_provenance_and_citation_gaps() -> None:
    class IncompleteReview:
        summary = "A synthetic critic offers a framing interpretation that remains explicitly unverified."
        provider = "Synthetic source"
        author = ""
        title = "Synthetic review"
        url = ""
        language = "und"

    packet = EvidencePacket.from_retrieval(
        {"title": "Example", "year": 2024, "directors": ["Director"]},
        {
            "method": "test",
            "candidate_count": 2,
            "passages": [
                {
                    "title": "Framework",
                    "page": 1,
                    "language": "en",
                    "excerpt": "Framing can be compared through figure position, boundaries and offscreen relations.",
                }
            ],
        },
        "framing",
        reviews=[IncompleteReview()],
    )
    invalid_theory = packet.theory_sources[0].model_copy(update={"evidence_id": "invalid"})
    packet = packet.model_copy(update={"theory_sources": [invalid_theory]})

    assessment = assess_evidence_packet(packet)

    assert assessment["status"] == "failed"
    assert assessment["provenance"]["completeness_ratio"] == 0.5
    assert assessment["citation_readiness"]["valid"] is False
    assert set(assessment["issues"]) >= {
        "citation_ids_invalid",
        "provenance_incomplete",
        "unknown_evidence_language",
    }


def test_packet_quality_fixture_suite_is_synthetic_complete_and_instruction_safe() -> None:
    suite = json.loads((ROOT / "evals" / "packet_quality_cases.json").read_text(encoding="utf-8"))

    assert suite["suite_id"] == "firstroll-packet-quality-v1"
    assert [case["id"] for case in suite["cases"]] == [
        "abundant-diverse-evidence",
        "sparse-honest-boundary",
        "duplicate-attributed-evidence",
        "multilingual-provenance",
        "ambiguous-identity-selected",
        "malicious-retrieved-instructions",
    ]
    assessments = {}
    for case in suite["cases"]:
        packet = build_packet(case)
        assessment = assess_evidence_packet(
            packet,
            expected_identity=case["expected_identity"],
        )
        assert check_case_expectations(case, assessment) == []
        assert assessment["identity"]["matches_expected"] is True
        assessments[case["id"]] = assessment

    assert assessments["abundant-diverse-evidence"]["status"] == "passed"
    assert assessments["sparse-honest-boundary"]["sufficiency"]["state"] == "sparse"
    assert "film_specific_evidence_sparse" in assessments["sparse-honest-boundary"]["issues"]
    assert assessments["duplicate-attributed-evidence"]["duplication"]["duplicate_items"] >= 1
    assert assessments["multilingual-provenance"]["diversity"]["languages"] == ["en", "zh"]
    assert assessments["ambiguous-identity-selected"]["identity"]["matches_expected"] is True
    malicious = assessments["malicious-retrieved-instructions"]["instruction_safety"]
    assert malicious["flagged_items"] == 2
    assert malicious["containment_boundary"] is True
    assert "instruction_containment_missing" not in assessments[
        "malicious-retrieved-instructions"
    ]["issues"]


def test_packet_quality_report_rejects_evidence_fields() -> None:
    with pytest.raises(ValueError, match="Unsafe packet-quality result field"):
        assert_report_redacted({"cases": [{"content": PRIVATE_EVIDENCE}]})
