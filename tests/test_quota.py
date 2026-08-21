from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.backend import main
from app.backend.auth import SupabaseAuthVerifier
from app.backend.public_study import build_public_study_retrieval
from app.backend.study_observability import StudyTrace
from app.backend.quota import (
    DeepStudyQuota,
    PostgresQuotaClient,
    QuotaConfigurationError,
    QuotaIdentity,
    QuotaExceededError,
    QuotaServiceError,
    SupabaseQuotaClient,
    configured_quota_client,
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

    quota = client.reserve(
        QuotaIdentity("supabase", str(uuid4()), "Bearer verified-token")
    )

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
        denied.reserve(QuotaIdentity("supabase", str(uuid4()), "Bearer verified-token"))
    with pytest.raises(QuotaServiceError, match="invalid quota"):
        malformed.reserve(QuotaIdentity("supabase", str(uuid4()), "Bearer verified-token"))


def test_postgres_quota_uses_verified_identity_without_forwarding_the_bearer_token() -> None:
    calls = []
    client = PostgresQuotaClient(
        "postgresql://firstroll_backend:secret@database.example/firstroll?sslmode=require",
        transport=lambda url, provider, subject, reserve: (
            calls.append((url, provider, subject, reserve)) or quota_payload()
        ),
    )
    identity = QuotaIdentity(
        provider="entra",
        subject="customer-object-id",
        legacy_authorisation="Bearer must-not-cross-the-database-boundary",
    )

    quota = client.reserve(identity)

    assert quota.allowed is True
    assert calls == [
        (
            "postgresql://firstroll_backend:secret@database.example/firstroll?sslmode=require",
            "entra",
            "customer-object-id",
            True,
        )
    ]
    assert "must-not-cross" not in repr(identity)


def test_postgres_quota_rejects_invalid_identity_and_factory_is_explicit(monkeypatch) -> None:
    client = PostgresQuotaClient(
        "postgresql://firstroll_backend:secret@database.example/firstroll",
        transport=lambda *_: quota_payload(),
    )

    with pytest.raises(QuotaServiceError, match="provider is invalid"):
        client.status(QuotaIdentity("not valid", "subject"))

    monkeypatch.setenv("FIRSTROLL_QUOTA_PROVIDER", "postgres")
    monkeypatch.setenv(
        "FIRSTROLL_DATABASE_URL",
        "postgresql://firstroll_backend:secret@database.example/firstroll",
    )
    assert isinstance(configured_quota_client(), PostgresQuotaClient)

    monkeypatch.setenv("FIRSTROLL_QUOTA_PROVIDER", "unknown")
    with pytest.raises(QuotaConfigurationError, match="FIRSTROLL_QUOTA_PROVIDER"):
        configured_quota_client()


def test_entra_deep_study_requires_backend_owned_quota(monkeypatch) -> None:
    class ReadyAuth:
        configured = True

    class LegacyQuota:
        configured = True
        backend_owned = False

    class BackendQuota:
        configured = True
        backend_owned = True

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_DEEP_STUDY_ENABLED", "true")
    monkeypatch.setenv("FIRSTROLL_AUTH_PROVIDER", "entra")
    monkeypatch.setattr(main, "auth_verifier", ReadyAuth())
    monkeypatch.setattr(main, "quota_client", LegacyQuota())

    assert main.hosted_deep_study_boundary_enabled() is False

    monkeypatch.setattr(main, "quota_client", BackendQuota())

    assert main.hosted_deep_study_boundary_enabled() is True


def test_transient_result_owner_is_namespaced_by_identity_provider() -> None:
    assert main.account_owner_id(
        {"id": "same-subject", "provider": "supabase", "email": None, "role": "authenticated"}
    ) == "supabase:same-subject"
    assert main.account_owner_id(
        {"id": "same-subject", "provider": "entra", "email": None, "role": "authenticated"}
    ) == "entra:same-subject"


def test_public_study_framework_is_bounded_and_first_party() -> None:
    trace = StudyTrace()
    retrieval = build_public_study_retrieval(
        {"title": "In the Mood for Love"},
        "How is space organised?",
        trace=trace,
    )

    assert retrieval["method"] == "firstroll_public_framework"
    assert retrieval["candidate_count"] == 4
    assert len(retrieval["passages"]) == 4
    assert all(
        item["title"].startswith("FirstRoll formal-analysis protocol")
        for item in retrieval["passages"]
    )
    assert all(len(item["excerpt"]) >= 300 for item in retrieval["passages"])
    stages = {stage["name"]: stage["status"] for stage in trace.snapshot()["stages"]}
    assert stages["retrieval_planning"] == "completed"
    assert stages["lexical_retrieval"] == "skipped"
    assert stages["semantic_retrieval"] == "skipped"
    assert stages["fusion_and_selection"] == "completed"


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

        def reserve(self, identity: QuotaIdentity) -> DeepStudyQuota:
            assert identity.provider == "supabase"
            assert identity.legacy_authorisation == "Bearer verified-token"
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

    def generate(
        film_record,
        passages,
        question,
        claims,
        evidence_packet,
        api_key=None,
        trace=None,
    ):
        captured["passages"] = passages
        captured["packet"] = evidence_packet
        captured["api_key"] = api_key
        captured["trace"] = trace
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
    stages = {
        stage["name"]: stage for stage in response.json()["study"]["observability"]["stages"]
    }
    assert stages["film_context"]["status"] == "completed"
    assert stages["retrieval_planning"]["status"] == "completed"
    assert stages["lexical_retrieval"]["status"] == "skipped"
    assert stages["semantic_retrieval"]["status"] == "skipped"
    assert stages["packet_assembly"]["status"] == "completed"


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

        def reserve(self, _identity: QuotaIdentity) -> DeepStudyQuota:
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

        def status(self, identity: QuotaIdentity) -> DeepStudyQuota:
            assert identity.provider == "supabase"
            assert identity.legacy_authorisation == "Bearer verified-token"
            return quota

    class ReadyDoubanAdapter:
        @staticmethod
        def status() -> dict:
            return {"installed": True}

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_DEEP_STUDY_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-test-key")
    monkeypatch.setattr(main, "auth_verifier", verifier)
    monkeypatch.setattr(main, "quota_client", StatusQuotaClient())
    monkeypatch.setattr(main, "douban_adapter", ReadyDoubanAdapter())

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
    assert response.json()["douban"] == {
        "availability": "hosted",
        "platform_enabled": True,
        "personal_credentials_supported": False,
        "hosted_cookie_accepted": False,
        "connector_url": "https://github.com/moria97/douban-mcp",
    }


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

        def reserve(self, _identity: QuotaIdentity) -> DeepStudyQuota:
            return quota

    captured = {}

    def generate(
        _film,
        _passages,
        _question,
        _claims,
        evidence_packet,
        api_key=None,
        trace=None,
    ):
        captured["api_key"] = api_key
        captured["packet"] = evidence_packet
        captured["trace"] = trace
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


def test_identity_neutral_quota_migration_is_atomic_and_backend_only() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "database"
        / "migrations"
        / "202608200001_identity_neutral_deep_study_quotas.sql"
    ).read_text(encoding="utf-8")

    assert "identity_provider varchar(64)" in migration
    assert "subject varchar(256)" in migration
    assert "pg_advisory_xact_lock" in migration
    assert "security definer" in migration
    assert "set search_path = ''" in migration
    assert "revoke all on function" in migration
    assert "grant execute" in migration
    assert "auth.uid()" not in migration
