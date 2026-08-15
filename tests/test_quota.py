from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.backend import main
from app.backend.auth import SupabaseAuthVerifier
from app.backend.public_study import build_public_study_retrieval
from app.backend.quota import (
    DeepStudyQuota,
    QuotaExceededError,
    QuotaServiceError,
    SupabaseQuotaClient,
)


def quota_payload(*, allowed: bool = True, reason: str = "available") -> dict:
    return {
        "allowed": allowed,
        "reason": reason,
        "user_limit": 3,
        "user_used": 1 if allowed else 3,
        "user_remaining": 2 if allowed else 0,
        "global_limit": 30,
        "global_used": 8,
        "global_remaining": 22,
        "reset_at": "2099-08-16T00:00:00+00:00",
    }


def test_quota_client_reserves_through_the_authenticated_rpc() -> None:
    calls = []
    client = SupabaseQuotaClient(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda url, key, token, function: (
            calls.append((url, key, token, function)) or quota_payload()
        ),
    )

    quota = client.reserve("Bearer verified-token")

    assert quota.allowed is True
    assert quota.user_remaining == 2
    assert calls == [
        (
            "https://example.supabase.co",
            "sb_publishable_test",
            "verified-token",
            "reserve_deep_study_quota",
        )
    ]


def test_quota_client_rejects_denial_and_malformed_decisions() -> None:
    denied = SupabaseQuotaClient(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda *_: quota_payload(allowed=False, reason="user_limit"),
    )
    malformed = SupabaseQuotaClient(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda *_: {"allowed": True},
    )

    with pytest.raises(QuotaExceededError, match="account"):
        denied.reserve("Bearer verified-token")
    with pytest.raises(QuotaServiceError, match="invalid quota"):
        malformed.reserve("Bearer verified-token")


def test_public_study_framework_is_bounded_and_first_party() -> None:
    retrieval = build_public_study_retrieval(
        {"title": "In the Mood for Love"},
        "How is space organised?",
    )

    assert retrieval["method"] == "firstroll_public_framework"
    assert retrieval["candidate_count"] == 4
    assert len(retrieval["passages"]) == 4
    assert all(
        item["title"].startswith("FirstRoll formal-analysis protocol")
        for item in retrieval["passages"]
    )
    assert all(len(item["excerpt"]) >= 300 for item in retrieval["passages"])


def test_hosted_study_reserves_quota_and_uses_public_framework(monkeypatch) -> None:
    user_id = str(uuid4())
    verifier = SupabaseAuthVerifier(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda *_: {
            "id": user_id,
            "email": "viewer@example.com",
            "role": "authenticated",
        },
    )
    quota = DeepStudyQuota.from_payload(quota_payload())

    class FakeQuotaClient:
        configured = True

        def reserve(self, authorisation: str | None) -> DeepStudyQuota:
            assert authorisation == "Bearer verified-token"
            return quota

    film = {
        "id": "Q1",
        "title": "Test Film",
        "year": 2000,
        "directors": ["Test Director"],
        "credits": {},
        "genres": [],
        "countries": [],
    }
    captured = {}

    def generate(film_record, passages, question, claims, evidence_packet, api_key=None):
        captured["passages"] = passages
        captured["packet"] = evidence_packet
        captured["api_key"] = api_key
        return {"title": "A bounded public study"}

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_DEEP_STUDY_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-test-key")
    monkeypatch.setattr(main, "auth_verifier", verifier)
    monkeypatch.setattr(main, "quota_client", FakeQuotaClient())
    monkeypatch.setattr(main.discovery_service, "detail", lambda _: {"film": film})
    monkeypatch.setattr(main.criticism_store, "load_all", lambda _: [])
    monkeypatch.setattr(main.video_service, "enrich_cached", lambda _: None)
    monkeypatch.setattr(main.study_service, "generate", generate)

    response = TestClient(main.app).post(
        "/api/discovery/films/Q1/study",
        json={"question": "How is space organised?"},
        headers={"Authorization": "Bearer verified-token"},
    )

    assert response.status_code == 200
    assert response.json()["quota"]["user"]["remaining"] == 2
    assert len(captured["passages"]) == 4
    assert captured["packet"].retrieval["method"] == "firstroll_public_framework"
    assert captured["api_key"] is None


def test_hosted_study_returns_429_when_account_quota_is_exhausted(monkeypatch) -> None:
    verifier = SupabaseAuthVerifier(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda *_: {
            "id": str(uuid4()),
            "email": "viewer@example.com",
            "role": "authenticated",
        },
    )
    denied = DeepStudyQuota.from_payload(quota_payload(allowed=False, reason="user_limit"))

    class DeniedQuotaClient:
        configured = True

        def reserve(self, _authorisation: str | None) -> DeepStudyQuota:
            raise QuotaExceededError(denied)

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_DEEP_STUDY_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-test-key")
    monkeypatch.setattr(main, "auth_verifier", verifier)
    monkeypatch.setattr(main, "quota_client", DeniedQuotaClient())
    monkeypatch.setattr(
        main.discovery_service,
        "detail",
        lambda _: {"film": {"id": "Q1", "title": "Test Film", "credits": {}}},
    )
    monkeypatch.setattr(main.criticism_store, "load_all", lambda _: [])
    monkeypatch.setattr(main.video_service, "enrich_cached", lambda _: None)

    response = TestClient(main.app).post(
        "/api/discovery/films/Q1/study",
        json={"question": None},
        headers={"Authorization": "Bearer verified-token"},
    )

    assert response.status_code == 429
    assert "account" in response.json()["detail"]
    assert int(response.headers["retry-after"]) >= 60


def test_account_integrations_returns_identity_and_quota_without_consuming_it(
    monkeypatch,
) -> None:
    user_id = str(uuid4())
    verifier = SupabaseAuthVerifier(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda *_: {
            "id": user_id,
            "email": "viewer@example.com",
            "role": "authenticated",
        },
    )
    quota = DeepStudyQuota.from_payload(quota_payload())

    class StatusQuotaClient:
        configured = True

        def status(self, authorisation: str | None) -> DeepStudyQuota:
            assert authorisation == "Bearer verified-token"
            return quota

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_DEEP_STUDY_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-test-key")
    monkeypatch.setattr(main, "auth_verifier", verifier)
    monkeypatch.setattr(main, "quota_client", StatusQuotaClient())

    missing = TestClient(main.app).get("/api/account/integrations")
    response = TestClient(main.app).get(
        "/api/account/integrations",
        headers={"Authorization": "Bearer verified-token"},
    )

    assert missing.status_code == 401
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "viewer@example.com"
    assert response.json()["deep_study"]["quota"]["user"]["remaining"] == 2
    assert response.json()["privacy"] == {
        "personal_credentials_stored": False,
        "credential_scope": "single_browser_tab",
    }
    assert response.json()["douban"]["hosted_cookie_accepted"] is False


def test_personal_deepseek_key_is_used_for_one_authenticated_request(monkeypatch) -> None:
    verifier = SupabaseAuthVerifier(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda *_: {
            "id": str(uuid4()),
            "email": "viewer@example.com",
            "role": "authenticated",
        },
    )
    quota = DeepStudyQuota.from_payload(quota_payload())

    class PersonalQuotaClient:
        configured = True

        def reserve(self, _authorisation: str | None) -> DeepStudyQuota:
            return quota

    captured = {}

    def generate(_film, _passages, _question, _claims, evidence_packet, api_key=None):
        captured["api_key"] = api_key
        captured["packet"] = evidence_packet
        return {"title": "Personal-key study"}

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_DEEP_STUDY_ENABLED", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(main, "auth_verifier", verifier)
    monkeypatch.setattr(main, "quota_client", PersonalQuotaClient())
    monkeypatch.setattr(
        main.discovery_service,
        "detail",
        lambda _: {"film": {"id": "Q1", "title": "Test Film", "credits": {}}},
    )
    monkeypatch.setattr(main.criticism_store, "load_all", lambda _: [])
    monkeypatch.setattr(main.video_service, "enrich_cached", lambda _: None)
    monkeypatch.setattr(main.study_service, "generate", generate)

    response = TestClient(main.app).post(
        "/api/discovery/films/Q1/study",
        json={"question": "How is space organised?"},
        headers={
            "Authorization": "Bearer verified-token",
            "X-FirstRoll-DeepSeek-Key": "sk-personal-session-key-12345",
        },
    )

    assert response.status_code == 200
    assert captured["api_key"] == "sk-personal-session-key-12345"
    assert response.json()["credential_source"] == "personal_session"


def test_personal_provider_keys_are_strictly_validated() -> None:
    client = TestClient(main.app)

    response = client.post(
        "/api/discovery/films/Q1/study",
        json={"question": None},
        headers={"X-FirstRoll-DeepSeek-Key": "not valid whitespace"},
    )

    assert response.status_code == 400
    assert "key is invalid" in response.json()["detail"]


def test_quota_migration_has_atomic_and_restricted_rpc_boundaries() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "202608150001_deep_study_quotas.sql"
    ).read_text(encoding="utf-8")

    assert "enable row level security" in migration
    assert "security definer" in migration
    assert "set search_path = ''" in migration
    assert "auth.uid()" in migration
    assert "pg_advisory_xact_lock" in migration
    assert "revoke all on all tables" in migration
    assert (
        "grant execute on function public.reserve_deep_study_quota() to authenticated" in migration
    )
    assert "service_role" not in migration
