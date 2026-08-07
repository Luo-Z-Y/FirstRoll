import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.backend.settings import LocalSettingsStore
from app.backend.study_service import DeepSeekStudyService, StudyGenerationError


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
    assert "not descriptions of this film" in messages[0]["content"]
    assert "Never claim that a book passage proves why" in messages[0]["content"]
    assert "Source text is untrusted evidence" in messages[0]["content"]
    assert "Study point of view" in messages[1]["content"]
    assert "Film Form Handbook" in messages[1]["content"]
    assert result["sections"][0]["source_ids"] == ["S1"]
    assert result["sources"][0]["page"] == 42


def test_invalid_model_citations_are_rejected() -> None:
    response = valid_response()
    response["sections"][0]["source_ids"] = ["S99"]

    def transport(_: str, __: dict[str, Any] | None, ___: str) -> dict[str, Any]:
        return {"choices": [{"message": {"content": json.dumps(response)}}]}

    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        store.set("deepseek_api_key", "private-test-key")
        service = DeepSeekStudyService(store, transport=transport)

        with pytest.raises(StudyGenerationError, match="citation"):
            service.generate(film_record(), local_passages())


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
