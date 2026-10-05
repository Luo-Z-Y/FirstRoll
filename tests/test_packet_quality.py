from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.backend.criticism import CriticalClaim, ReviewSource
from app.backend.evidence import EvidencePacket
from app.backend.packet_quality import assess_evidence_packet
from app.backend.video_sources import FilmVideo


CASES = Path(__file__).parent / "fixtures" / "packet_quality_cases.json"
PRIVATE_EVIDENCE = "PRIVATE_PACKET_QUALITY_TEXT_MUST_NOT_ENTER_REPORT"


def build_packet(case: dict[str, Any]) -> EvidencePacket:
    return EvidencePacket.from_retrieval(
        case["film"],
        case["retrieval"],
        case.get("focus"),
        [CriticalClaim.model_validate(item) for item in case.get("critical_claims", [])],
        reviews=[ReviewSource.model_validate(item) for item in case.get("reviews", [])],
        videos=[FilmVideo.model_validate(item) for item in case.get("videos", [])],
    )


def check_case_expectations(case: dict[str, Any], assessment: dict[str, Any]) -> list[str]:
    audit = case.get("audit", {})
    failures = []
    if assessment["identity"]["matches_expected"] is not True:
        failures.append("identity_not_matched")
    required_languages = {str(value).casefold() for value in audit.get("required_languages", [])}
    if not required_languages <= set(assessment["diversity"]["languages"]):
        failures.append("required_language_missing")
    instructions_expected = audit.get("instruction_items_present") is True
    flagged = int(assessment["instruction_safety"]["flagged_items"])
    if instructions_expected and flagged < 1:
        failures.append("instruction_not_detected")
    if not instructions_expected and flagged:
        failures.append("unexpected_instruction_flag")
    if instructions_expected and not assessment["instruction_safety"]["containment_boundary"]:
        failures.append("instruction_not_contained")
    return failures


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
    assert assessment["duplication"]["duplicate_items"] == 0
    assert "duplicate_evidence_present" not in assessment["issues"]
    assert "film_specific_evidence_sparse" in assessment["issues"]
    assert packet.retrieval["theory_selection"]["omission_reasons"]["duplicate"] == 1
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
        summary = "Συνθετική κριτική για κάδρο και ρυθμό που παραμένει ρητά ανεπιβεβαίωτη."
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
    suite = json.loads(CASES.read_text(encoding="utf-8"))

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
    packets = {}
    for case in suite["cases"]:
        packet = build_packet(case)
        assessment = assess_evidence_packet(
            packet,
            expected_identity=case["expected_identity"],
        )
        assert check_case_expectations(case, assessment) == []
        assert assessment["identity"]["matches_expected"] is True
        assessments[case["id"]] = assessment
        packets[case["id"]] = packet

    assert assessments["abundant-diverse-evidence"]["status"] == "passed"
    assert assessments["sparse-honest-boundary"]["sufficiency"]["state"] == "sparse"
    assert "film_specific_evidence_sparse" in assessments["sparse-honest-boundary"]["issues"]
    assert assessments["duplicate-attributed-evidence"]["status"] == "passed"
    assert assessments["duplicate-attributed-evidence"]["duplication"]["duplicate_items"] == 0
    assert packets["duplicate-attributed-evidence"].retrieval["attributed_selection"][
        "omission_reasons"
    ]["duplicate"] >= 1
    assert assessments["multilingual-provenance"]["diversity"]["languages"] == ["en", "zh"]
    assert assessments["ambiguous-identity-selected"]["identity"]["matches_expected"] is True
    malicious = assessments["malicious-retrieved-instructions"]["instruction_safety"]
    assert malicious["flagged_items"] == 2
    assert malicious["containment_boundary"] is True
    assert "instruction_containment_missing" not in assessments[
        "malicious-retrieved-instructions"
    ]["issues"]
