from __future__ import annotations

import json
import logging
from uuid import uuid4

from fastapi.testclient import TestClient

from app.backend import main
from app.backend.auth import SupabaseAuthVerifier
from app.backend.evidence import EvidencePacket
from app.backend.quota import DeepStudyQuota, QuotaIdentity
from app.backend.research_stream import (
    PUBLIC_PROGRESS_KINDS,
    ResearchProgressStream,
    StudyRunStore,
)
from app.backend.study_service import StudyGenerationError


PRIVATE_PASSAGE = "PRIVATE_BOOK_PASSAGE_MUST_NOT_ENTER_PROGRESS"
PRIVATE_PROMPT = "PRIVATE_USER_PROMPT_MUST_NOT_RETURN"
PRIVATE_KEY = "personal-deepseek-key-12345"


def parse_progress_frames(body: str) -> list[dict]:
    frames = []
    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        if "event: progress" not in lines:
            continue
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        frames.append(json.loads(data))
    return frames


def configured_client(monkeypatch, *, fail_generation: bool = False) -> tuple[TestClient, dict]:
    first_user = str(uuid4())
    second_user = str(uuid4())

    def auth_transport(_url, _key, token):
        user_id = second_user if token == "other-token" else first_user
        return {"id": user_id, "email": "viewer@example.com", "role": "authenticated"}

    verifier = SupabaseAuthVerifier(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=auth_transport,
    )
    film = {"id": "Q1", "title": "Test Film", "year": 2026, "directors": ["Director"]}
    reading = {
        "method": "test",
        "candidate_count": 1,
        "passages": [
            {
                "title": "Private film book",
                "page": 12,
                "excerpt": PRIVATE_PASSAGE,
                "language": "en",
            }
        ],
    }
    packet = EvidencePacket.from_retrieval(film, reading, PRIVATE_PROMPT)
    captured = {"first_user": first_user, "second_user": second_user}

    class FakeStudyService:
        def generate(self, *args, api_key=None, **kwargs):
            captured["api_key"] = api_key
            if fail_generation:
                raise StudyGenerationError(f"provider failure included {PRIVATE_KEY}")
            return {
                "title": "A safe streamed study",
                "central_argument": "A bounded public article.",
                "sections": [{"lens": "Framing"}],
                "quality": {"status": "passed", "score": 1.0},
                "sources": [{"id": "S1", "excerpt": PRIVATE_PASSAGE}],
                "evidence_packet": packet.model_dump(),
                "hidden_reasoning": "PRIVATE_CHAIN_OF_THOUGHT_MUST_NOT_ENTER_PROGRESS",
            }

    class FakeQuotaClient:
        def reserve(self, identity: QuotaIdentity):
            captured["quota_identity"] = identity
            return DeepStudyQuota(
                allowed=True,
                reason="available",
                user_limit=3,
                user_used=1,
                user_remaining=2,
                global_limit=30,
                global_used=1,
                global_remaining=29,
                reset_at="2099-01-01T00:00:00Z",
            )

    def prepare(film_id, selected_film, question, *, public_mode, trace=None):
        captured["film_id"] = film_id
        captured["question"] = question
        captured["public_mode"] = public_mode
        captured["trace"] = trace
        return {
            "film": selected_film,
            "claims": [],
            "reading": reading,
            "packet": packet,
            "trace": trace,
        }

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setattr(main, "auth_verifier", verifier)
    monkeypatch.setattr(main, "hosted_deep_study_boundary_enabled", lambda: True)
    monkeypatch.setattr(main, "hosted_deep_study_enabled", lambda: True)
    monkeypatch.setattr(main, "study_run_store", StudyRunStore())
    monkeypatch.setattr(main, "study_service", FakeStudyService())
    monkeypatch.setattr(main, "quota_client", FakeQuotaClient())
    monkeypatch.setattr(main, "prepare_film_study", prepare)
    monkeypatch.setattr(main.discovery_service, "detail", lambda _film_id: {"film": film})
    return TestClient(main.app), captured


def test_authenticated_sse_progress_is_ordered_and_contains_no_private_material(
    monkeypatch,
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="firstroll.study_observability")
    client, captured = configured_client(monkeypatch)
    headers = {
        "Authorization": "Bearer valid-token",
        "X-FirstRoll-DeepSeek-Key": PRIVATE_KEY,
    }

    response = client.post(
        "/api/discovery/films/Q1/study/stream",
        json={"question": PRIVATE_PROMPT},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store, no-transform"
    assert response.headers["vary"] == "Authorization, X-FirstRoll-DeepSeek-Key"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-accel-buffering"] == "no"
    run_id = response.headers["x-firstroll-run-id"]
    events = parse_progress_frames(response.text)
    assert [item["sequence"] for item in events] == list(range(1, len(events) + 1))
    assert [item["kind"] for item in events] == [
        "film_resolving",
        "existing_evidence_loading",
        "evidence_assessed",
        "study_drafting",
        "quality_checked",
        "run_completed",
    ]
    assert all(item["kind"] in PUBLIC_PROGRESS_KINDS for item in events)
    assert all(item["run_id"] == run_id for item in events)
    assert all(
        set(item) <= {"run_id", "kind", "sequence", "message", "elapsed_ms", "counts"}
        for item in events
    )
    assert PRIVATE_KEY not in response.text
    assert PRIVATE_PROMPT not in response.text
    assert PRIVATE_PASSAGE not in response.text
    assert "PRIVATE_CHAIN_OF_THOUGHT" not in response.text
    assert captured["api_key"] == PRIVATE_KEY
    assert "study_observability=" in caplog.text
    assert PRIVATE_KEY not in caplog.text
    assert PRIVATE_PROMPT not in caplog.text
    assert PRIVATE_PASSAGE not in caplog.text
    assert "PRIVATE_CHAIN_OF_THOUGHT" not in caplog.text

    result = client.get(
        f"/api/research/runs/{run_id}",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["vary"] == "Authorization"
    assert result.headers["x-content-type-options"] == "nosniff"
    assert result.json()["study"]["sources"][0]["excerpt"] == PRIVATE_PASSAGE


def test_sse_requires_authentication_and_result_ownership(monkeypatch) -> None:
    client, _captured = configured_client(monkeypatch)
    missing = client.post(
        "/api/discovery/films/Q1/study/stream",
        json={"question": "Framing"},
    )
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"

    streamed = client.post(
        "/api/discovery/films/Q1/study/stream",
        json={"question": "Framing"},
        headers={"Authorization": "Bearer valid-token"},
    )
    run_id = streamed.headers["x-firstroll-run-id"]
    denied = client.get(
        f"/api/research/runs/{run_id}",
        headers={"Authorization": "Bearer other-token"},
    )
    assert denied.status_code == 404
    assert denied.json()["detail"] == "Unknown research run."


def test_sse_redacts_provider_exception_details(monkeypatch) -> None:
    client, _captured = configured_client(monkeypatch, fail_generation=True)
    response = client.post(
        "/api/discovery/films/Q1/study/stream",
        json={"question": PRIVATE_PROMPT},
        headers={
            "Authorization": "Bearer valid-token",
            "X-FirstRoll-DeepSeek-Key": PRIVATE_KEY,
        },
    )

    events = parse_progress_frames(response.text)
    assert events[-1] == {
        "run_id": response.headers["x-firstroll-run-id"],
        "kind": "run_failed",
        "sequence": 5,
        "message": "DeepSeek could not produce a valid study for this run.",
        "elapsed_ms": events[-1]["elapsed_ms"],
    }
    assert PRIVATE_KEY not in response.text
    assert PRIVATE_PROMPT not in response.text


def test_progress_contract_rejects_arbitrary_fields() -> None:
    progress = ResearchProgressStream("run-1")

    try:
        progress.frame("raw_model_delta")
    except ValueError as exc:
        assert "Unknown public research event kind" in str(exc)
    else:
        raise AssertionError("An unknown event kind entered the public stream.")

    try:
        progress.frame("tool_completed", counts={"prompt_tokens": 10})
    except ValueError as exc:
        assert "Unknown public research event count" in str(exc)
    else:
        raise AssertionError("An unknown event count entered the public stream.")

    try:
        progress.frame("run_failed", message_variant=PRIVATE_PROMPT)
    except ValueError as exc:
        assert "Unknown public research event message" in str(exc)
    else:
        raise AssertionError("Arbitrary prompt text entered the public message channel.")
