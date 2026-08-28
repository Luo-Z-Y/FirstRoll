import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.backend.autonomous_study import audited_claim_paths
from app.backend.settings import LocalSettingsStore
from app.backend.criticism import ReviewSource
from app.backend.evidence import EvidencePacket
from app.backend.study_observability import StudyTrace
from app.backend.study_service import (
    DeepSeekStudyService,
    MAX_CLAIM_AUDIT_COMPLETION_TOKENS,
    MAX_FILMMAKER_COACH_COMPLETION_TOKENS,
    StudyGenerationError,
    StudyQualityGate,
)


def film_record() -> dict[str, Any]:
    return {
        "title": "Example Film",
        "year": 2024,
        "overview": "Two neighbours discover a conflict in their shared building.",
        "directors": ["Example Director"],
        "credits": {"directors": ["Example Director"], "cinematographers": []},
        "source": {"name": "Wikidata", "licence": "CC0"},
        "overview_source": {"name": "Wikipedia", "licence": "CC BY-SA"},
    }


def local_passages() -> list[dict[str, Any]]:
    return [
        {
            "concept": "Narrative",
            "title": "Film Form Handbook",
            "page": 42,
            "excerpt": "Narration may restrict what viewers know and when they know it.",
        }
    ]


def valid_response() -> dict[str, Any]:
    sections = [
        {
            "lens": lens,
            "status": "viewing_hypothesis",
            "critic_reports": None,
            "theory_explains": (
                "Restricted narration describes how a film controls the range and depth "
                "of information available to a viewer over time."
            ),
            "hypothesis": (
                "A careful viewing hypothesis could test whether restricted narration "
                "changes the viewer's understanding of the conflict across the film."
            ),
            "mechanism": (
                "By delaying or repeating access to information, a pattern could make each "
                "later disclosure revise the viewer's relation to the earlier material."
            ),
            "alternative_reading": (
                "The information pattern might instead clarify geography without changing allegiance."
            ),
            "verify": "Track and compare when the viewer and each neighbour learn new information.",
            "source_ids": ["S1"],
            "critic_claim_ids": [],
            "confidence": "low",
        }
        for lens in ("Narrative", "Space", "Editing", "Sound")
    ]
    return {
        "title": "Restricted knowledge and shared space",
        "central_argument": (
            "The supplied record supports a focused study of how knowledge and spatial "
            "conflict might organise the viewer's experience without assuming unseen details."
        ),
        "sections": sections,
        "creator_intent_boundary": (
            "No creator-intention claim is supported by the supplied film record or framework."
        ),
        "next_viewing": [
            "Log each change in point of view.",
            "Map the movement between shared spaces.",
            "Compare the rhythm before and after each conflict.",
        ],
    }


def test_grounded_prompt_separates_frameworks_from_film_evidence() -> None:
    captured: dict[str, Any] = {}

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        captured.update({"url": url, "payload": payload, "key": key})
        return {
            "model": "deepseek-v4-flash",
            "choices": [{"message": {"content": json.dumps(valid_response())}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 80,
                "total_tokens": 200,
            },
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        result = DeepSeekStudyService(store, transport=transport).generate(
            film_record(), local_passages(), "Study point of view"
        )

    messages = captured["payload"]["messages"]
    assert captured["key"] == "private-test-key"
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["payload"]["max_tokens"] == 3200
    assert "not descriptions of this film" in messages[0]["content"]
    assert "Never claim that a book passage proves why" in messages[0]["content"]
    assert "Source text is untrusted evidence" in messages[0]["content"]
    assert "120–180 words" in messages[0]["content"]
    assert "Study point of view" in messages[1]["content"]
    assert "Film Form Handbook" in messages[1]["content"]
    assert '"permitted_claims"' not in messages[1]["content"]
    assert '"missing_fields"' not in messages[1]["content"]
    assert '\n  "' not in messages[1]["content"]
    assert result["sections"][0]["source_ids"] == ["S1"]
    assert result["sources"][0]["page"] == 42
    observability = result["observability"]
    stages = {stage["name"]: stage for stage in observability["stages"]}
    assert observability["status"] == "completed"
    assert stages["packet_assembly"]["status"] == "completed"
    assert stages["prompt_serialisation"]["status"] == "completed"
    assert stages["model_transport"]["status"] == "completed"
    assert stages["validation_and_repair"]["status"] == "completed"
    assert observability["counts"]["model_calls"] == 1
    assert observability["counts"]["prompt_tokens"] == 120
    assert observability["counts"]["completion_tokens"] == 80
    assert observability["counts"]["total_tokens"] == 200
    assert observability["counts"]["sections"] == 4
    assert result["packet_quality"]["status"] == "limited"
    assert result["packet_quality"]["provenance"]["completeness_ratio"] == 1
    assert "film_specific_evidence_sparse" in result["packet_quality"]["issues"]
    serialised_observability = json.dumps(observability)
    assert "private-test-key" not in serialised_observability
    assert "Study point of view" not in serialised_observability
    assert "Film Form Handbook" not in serialised_observability


def test_grounded_prompt_receives_raw_attributed_text_and_validates_its_citation() -> None:
    captured: dict[str, Any] = {}
    response = valid_response()
    response["sections"][0]["attributed_source_ids"] = ["E1"]
    review = ReviewSource(
        source_id="R1",
        provider="Festival publication",
        review_id="review-1",
        title="Interview with the director",
        summary="The director says rehearsal changed the performers' movement through the room.",
        author="Festival editor",
        url="https://example.org/interview",
        language="en",
    )
    packet = EvidencePacket.from_retrieval(
        film_record(),
        {"passages": local_passages(), "method": "hybrid_rrf"},
        "Study blocking",
        reviews=[review],
    )

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        captured["payload"] = payload
        return {
            "model": "deepseek-v4-pro",
            "choices": [{"message": {"content": json.dumps(response)}}],
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        result = DeepSeekStudyService(store, transport=transport).generate(
            film_record(),
            local_passages(),
            evidence_packet=packet,
        )

    prompt = captured["payload"]["messages"][1]["content"]
    assert "ATTRIBUTED SOURCE TEXT" in prompt
    assert "rehearsal changed" in prompt
    assert result["sections"][0]["attributed_source_ids"] == ["E1"]
    assert result["attributed_sources"][0]["source_url"] == "https://example.org/interview"


def test_repair_attempts_are_counted_without_exposing_repair_content() -> None:
    initial = valid_response()
    initial["central_argument"] = (
        "The film uses deliberate framing to isolate every figure and structures the entire "
        "conflict through an unquestionably fixed visual hierarchy."
    )
    repaired = valid_response()
    calls = []

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        response = initial if not calls else repaired
        calls.append(response)
        return {
            "model": "deepseek-v4-pro",
            "choices": [{"message": {"content": json.dumps(response)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        result = DeepSeekStudyService(store, transport=transport).generate(
            film_record(), local_passages()
        )

    stages = {stage["name"]: stage for stage in result["observability"]["stages"]}
    counts = result["observability"]["counts"]
    assert len(calls) == 2
    assert result["quality"]["status"] == "passed"
    assert result["quality"]["repair_attempted"] is True
    assert stages["prompt_serialisation"]["attempts"] == 2
    assert stages["model_transport"]["attempts"] == 2
    assert stages["validation_and_repair"]["attempts"] == 3
    assert counts["model_calls"] == 2
    assert counts["repair_attempts"] == 1
    assert counts["prompt_tokens"] == 200
    assert counts["total_tokens"] == 300


def test_generate_once_leaves_quality_retry_to_the_agent() -> None:
    weak = valid_response()
    weak["central_argument"] = (
        "The film uses deliberate framing to isolate every figure and structures the entire "
        "conflict through an unquestionably fixed visual hierarchy."
    )
    calls = []

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        calls.append(weak)
        return {
            "model": "deepseek-v4-pro",
            "choices": [{"message": {"content": json.dumps(weak)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        result = DeepSeekStudyService(store, transport=transport).generate_once(
            film_record(), local_passages()
        )

    assert len(calls) == 1
    assert result["quality"]["status"] == "insufficient_evidence"
    assert result["quality"]["repair_attempted"] is False
    assert result["observability"]["counts"]["model_calls"] == 1
    assert result["observability"]["counts"].get("repair_attempts", 0) == 0


def test_generate_once_uses_deterministic_temperature_without_changing_fixed_default() -> None:
    payloads: list[dict[str, Any]] = []

    def transport(_: str, payload: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        assert payload is not None
        payloads.append(payload)
        return {
            "model": "deepseek-v4-pro",
            "choices": [{"message": {"content": json.dumps(valid_response())}}],
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        service = DeepSeekStudyService(store, transport=transport)
        service.generate_once(film_record(), local_passages())
        service.generate(film_record(), local_passages())

    assert [payload["temperature"] for payload in payloads] == [0, 0.2]


def test_parseable_invalid_citation_receives_a_bounded_field_patch() -> None:
    invalid = valid_response()
    invalid["sections"][0]["source_ids"] = ["S99"]
    patch = {
        "updates": [
            {
                "path": "sections.0.source_ids",
                "value": ["S1"],
            }
        ]
    }
    payloads: list[dict[str, Any]] = []

    def transport(_: str, payload: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        assert payload is not None
        payloads.append(payload)
        content = invalid if len(payloads) == 1 else patch
        return {
            "model": "deepseek-v4-pro",
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }

    packet = EvidencePacket.from_retrieval(
        film_record(),
        {"passages": local_passages(), "method": "hybrid_rrf"},
        "Study point of view",
    )
    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        service = DeepSeekStudyService(store, transport=transport)
        with pytest.raises(StudyGenerationError) as captured:
            service.generate_once(
                film_record(),
                local_passages(),
                evidence_packet=packet,
            )
        error = captured.value
        result = service.repair_invalid_once(
            error.repair_candidate or {},
            error.repair_paths,
            evidence_packet=packet,
        )

    assert error.category == "citation_validation"
    assert error.repair_paths == ("sections.0.source_ids",)
    assert payloads[0]["max_tokens"] == 3200
    assert payloads[1]["max_tokens"] == 800
    assert payloads[1]["temperature"] == 0
    assert sum(len(message["content"]) for message in payloads[1]["messages"]) < sum(
        len(message["content"]) for message in payloads[0]["messages"]
    )
    repair_request = json.loads(payloads[1]["messages"][1]["content"])
    assert repair_request["repair_paths"] == ["sections.0.source_ids"]
    assert repair_request["field_requirements"] == {
        "sections.0.source_ids": "array of 1–6 supplied S identifiers"
    }
    repair_context = repair_request["evidence_context"]
    assert set(repair_context["candidate_sections"]) == {"0"}
    assert repair_context["theory_sources"][0]["id"] == "S1"
    assert "critical_claims" not in repair_context
    assert "attributed_sources" not in repair_context
    assert result["sections"][0]["source_ids"] == ["S1"]
    assert result["sections"][1:] == error.repair_candidate["sections"][1:]
    assert result["observability"]["counts"]["model_calls"] == 1
    assert result["observability"]["counts"]["structural_repair_attempts"] == 1


def test_second_invalid_citation_remains_eligible_for_the_final_field_patch() -> None:
    invalid = valid_response()
    invalid["sections"][0]["source_ids"] = ["S99"]
    invalid["sections"][1]["source_ids"] = ["S98"]
    responses = [
        invalid,
        {"updates": [{"path": "sections.0.source_ids", "value": ["S1"]}]},
        {"updates": [{"path": "sections.1.source_ids", "value": ["S1"]}]},
    ]
    payloads: list[dict[str, Any]] = []

    def transport(_: str, payload: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        assert payload is not None
        payloads.append(payload)
        return {
            "choices": [{"message": {"content": json.dumps(responses.pop(0))}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        }

    packet = EvidencePacket.from_retrieval(
        film_record(),
        {"passages": local_passages(), "method": "hybrid_rrf"},
        "Study point of view",
    )
    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        service = DeepSeekStudyService(store, transport=transport)
        with pytest.raises(StudyGenerationError) as initial_failure:
            service.generate_once(
                film_record(),
                local_passages(),
                evidence_packet=packet,
            )
        with pytest.raises(StudyGenerationError) as first_repair_failure:
            service.repair_invalid_once(
                initial_failure.value.repair_candidate or {},
                initial_failure.value.repair_paths,
                evidence_packet=packet,
            )
        result = service.repair_invalid_once(
            first_repair_failure.value.repair_candidate or {},
            first_repair_failure.value.repair_paths,
            evidence_packet=packet,
        )

    assert initial_failure.value.repair_paths == ("sections.0.source_ids",)
    assert first_repair_failure.value.repair_paths == ("sections.1.source_ids",)
    assert [payload["max_tokens"] for payload in payloads] == [3200, 800, 800]
    assert result["sections"][0]["source_ids"] == ["S1"]
    assert result["sections"][1]["source_ids"] == ["S1"]


def test_schema_failure_exposes_only_bounded_repair_paths() -> None:
    invalid = valid_response()
    del invalid["sections"][0]["confidence"]

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": json.dumps(invalid)}}],
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        with pytest.raises(StudyGenerationError) as captured:
            DeepSeekStudyService(store, transport=transport).generate_once(
                film_record(), local_passages()
            )

    assert captured.value.category == "schema_validation"
    assert captured.value.repair_paths == ("sections.0.confidence",)
    assert captured.value.repair_candidate is not None


def test_malformed_json_has_safe_category_but_no_candidate() -> None:
    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "not-json"}}]}

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        with pytest.raises(StudyGenerationError) as captured:
            DeepSeekStudyService(store, transport=transport).generate_once(
                film_record(), local_passages()
            )

    assert captured.value.category == "malformed_json"
    assert captured.value.repair_candidate is None
    assert captured.value.repair_paths == ()


def test_structural_patch_cannot_change_an_accepted_field() -> None:
    candidate = valid_response()
    candidate["sections"][0]["source_ids"] = ["S99"]

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        patch = {"updates": [{"path": "central_argument", "value": "not allowed"}]}
        return {"choices": [{"message": {"content": json.dumps(patch)}}]}

    packet = EvidencePacket.from_retrieval(
        film_record(),
        {"passages": local_passages(), "method": "hybrid_rrf"},
        "Study point of view",
    )
    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        service = DeepSeekStudyService(store, transport=transport)
        with pytest.raises(StudyGenerationError) as captured:
            service.repair_invalid_once(
                candidate,
                ("sections.0.source_ids",),
                evidence_packet=packet,
            )

    assert captured.value.category == "structural_repair_invalid"
    assert candidate["central_argument"] == valid_response()["central_argument"]


def test_repair_once_makes_exactly_one_agent_owned_attempt() -> None:
    weak = valid_response()
    weak["central_argument"] = (
        "The film uses deliberate framing to isolate every figure and structures the entire "
        "conflict through an unquestionably fixed visual hierarchy."
    )
    repaired = valid_response()
    packet = EvidencePacket.from_retrieval(
        film_record(),
        {"passages": local_passages(), "method": "hybrid_rrf"},
        "Study point of view",
    )
    calls = []

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        calls.append(repaired)
        return {
            "model": "deepseek-v4-pro",
            "choices": [{"message": {"content": json.dumps(repaired)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        result = DeepSeekStudyService(store, transport=transport).repair_once(
            weak,
            StudyQualityGate.evaluate(weak, False),
            evidence_packet=packet,
        )

    assert len(calls) == 1
    assert result["quality"]["status"] == "passed"
    assert result["quality"]["repair_attempted"] is True
    assert result["observability"]["counts"]["model_calls"] == 1
    assert result["observability"]["counts"]["repair_attempts"] == 1


def test_invalid_initial_response_receives_one_bounded_schema_retry() -> None:
    calls = []

    def transport(_: str, payload: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        calls.append(payload)
        response = {} if len(calls) == 1 else valid_response()
        return {
            "model": "deepseek-v4-pro",
            "choices": [{"message": {"content": json.dumps(response)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        result = DeepSeekStudyService(store, transport=transport).generate(
            film_record(), local_passages()
        )

    stages = {stage["name"]: stage for stage in result["observability"]["stages"]}
    counts = result["observability"]["counts"]
    assert len(calls) == 2
    assert calls[1]["temperature"] == 0
    assert calls[1]["max_tokens"] == 3200
    assert "previous response failed" in calls[1]["messages"][-1]["content"].casefold()
    assert result["quality"]["status"] == "passed"
    assert result["quality"]["repair_attempted"] is True
    assert stages["validation_and_repair"]["status"] == "degraded"
    assert stages["validation_and_repair"]["attempts"] == 2
    assert stages["validation_and_repair"]["failures"] == 1
    assert counts["model_calls"] == 2
    assert counts["repair_attempts"] == 1
    assert counts["total_tokens"] == 300


def test_transport_failure_requires_explicit_user_retry() -> None:
    calls = 0
    trace = StudyTrace()

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise StudyGenerationError("synthetic timeout")

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        with pytest.raises(StudyGenerationError, match="synthetic timeout"):
            DeepSeekStudyService(store, transport=transport).generate(
                film_record(), local_passages(), trace=trace
            )

    assert calls == 1
    assert trace.snapshot()["counts"]["model_calls"] == 1
    assert trace.snapshot()["stages"][-1]["status"] == "failed"


def test_invalid_model_citations_are_rejected() -> None:
    response = valid_response()
    response["sections"][0]["source_ids"] = ["S99"]

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        return {"choices": [{"message": {"content": json.dumps(response)}}]}

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        service = DeepSeekStudyService(store, transport=transport)
        trace = StudyTrace()

        with pytest.raises(StudyGenerationError, match="invalid study response after one repair"):
            service.generate(film_record(), local_passages(), trace=trace)

    observability = trace.snapshot()
    stages = {stage["name"]: stage for stage in observability["stages"]}
    assert observability["status"] == "failed"
    assert stages["model_transport"]["status"] == "completed"
    assert stages["validation_and_repair"]["status"] == "failed"
    assert stages["end_to_end"]["status"] == "failed"


def test_model_cannot_label_formal_analysis_as_record_supported() -> None:
    response = valid_response()
    response["sections"][0]["status"] = "record_supported"

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        return {"choices": [{"message": {"content": json.dumps(response)}}]}

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")

        with pytest.raises(StudyGenerationError, match="invalid study response"):
            DeepSeekStudyService(store, transport=transport).generate(
                film_record(), local_passages()
            )


def autonomous_packet() -> EvidencePacket:
    return EvidencePacket.from_retrieval(
        film_record(),
        {"passages": local_passages(), "method": "synthetic"},
        "Study point of view",
    )


def autonomous_audit_response(study: dict[str, Any] | None = None) -> dict[str, Any]:
    study = study or valid_response()
    items = []
    for path in audited_claim_paths(study):
        field = path.rsplit(".", 1)[-1]
        items.append(
            {
                "path": path,
                "label": (
                    "directly_supported"
                    if field == "theory_explains"
                    else "reasonable_interpretation"
                ),
                "source_ids": ["S1"],
                "support_note": (
                    "The cited framework supports this bounded relationship while the study keeps "
                    "its interpretive or theoretical status visible."
                ),
            }
        )
    return {"items": items}


def test_claim_auditor_sends_required_paths_and_validates_exact_coverage() -> None:
    captured: dict[str, Any] = {}
    audit = autonomous_audit_response()

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        captured["payload"] = payload
        return {
            "model": "audit-test",
            "choices": [{"message": {"content": json.dumps(audit)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        result = DeepSeekStudyService(store, transport=transport).audit_claims_once(
            valid_response(),
            evidence_packet=autonomous_packet(),
        )

    assert len(result["items"]) == len(audited_claim_paths(valid_response()))
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["payload"]["temperature"] == 0
    assert captured["payload"]["max_tokens"] == MAX_CLAIM_AUDIT_COMPLETION_TOKENS
    prompt = captured["payload"]["messages"][1]["content"]
    assert "required_paths" in prompt
    assert "private-test-key" not in prompt
    assert result["observability"]["counts"]["model_calls"] == 1


def test_claim_auditor_rejects_incomplete_model_audit() -> None:
    audit = autonomous_audit_response()
    audit["items"].pop()

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        return {"choices": [{"message": {"content": json.dumps(audit)}}]}

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        with pytest.raises(StudyGenerationError) as error:
            DeepSeekStudyService(store, transport=transport).audit_claims_once(
                valid_response(),
                evidence_packet=autonomous_packet(),
            )

    assert error.value.category == "claim_audit_invalid"


def test_filmmaker_coach_uses_only_accepted_audited_paths() -> None:
    study = valid_response()
    audit = autonomous_audit_response(study)
    exercise_paths = (
        "sections.0.hypothesis",
        "sections.1.mechanism",
        "sections.2.alternative_reading",
    )
    actions = ("log", "compare", "inspect")
    coach = {
        "exercises": [
            {
                "title": f"{action.title()} the proposed pattern",
                "action": action,
                "instruction": (
                    f"{action.title()} each relevant example and its counterexample before deciding "
                    "whether the accepted viewing hypothesis remains useful."
                ),
                "study_path": path,
                "source_ids": ["S1"],
                "success_signal": (
                    "The record contains comparable instances and at least one searched-for "
                    "counterexample."
                ),
                "uncertainty_boundary": (
                    "This action tests an interpretation and does not prove intention or an unseen "
                    "whole-film fact."
                ),
            }
            for action, path in zip(actions, exercise_paths)
        ]
    }
    captured: dict[str, Any] = {}

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        captured["payload"] = payload
        return {
            "model": "coach-test",
            "choices": [{"message": {"content": json.dumps(coach)}}],
        }

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        result = DeepSeekStudyService(store, transport=transport).coach_filmmaker_once(
            study,
            audit,
            evidence_packet=autonomous_packet(),
        )

    assert len(result["exercises"]) == 3
    assert captured["payload"]["max_tokens"] == MAX_FILMMAKER_COACH_COMPLETION_TOKENS
    assert "evidence_packet" not in captured["payload"]["messages"][1]["content"]
    assert result["observability"]["counts"]["model_calls"] == 1


def test_audited_editor_rejects_unscoped_or_excessive_paths_without_a_call() -> None:
    calls = 0

    def transport(url: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {}

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        service = DeepSeekStudyService(store, transport=transport)
        with pytest.raises(StudyGenerationError) as error:
            service.repair_audited_once(
                valid_response(),
                ("sections.0.source_ids",),
                evidence_packet=autonomous_packet(),
            )

    assert error.value.category == "structural_repair_invalid"
    assert calls == 0
