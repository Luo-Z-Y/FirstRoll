from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.backend import main
from app.backend.auth import (
    AuthConfigurationError,
    AuthenticationError,
    EntraAuthVerifier,
    SupabaseAuthVerifier,
    configured_auth_verifier,
)
from app.backend.video_sources import FilmVideoBundle


def test_supabase_auth_verifier_accepts_a_verified_authenticated_user() -> None:
    user_id = str(uuid4())
    verifier = SupabaseAuthVerifier(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda url, key, token: {
            "id": user_id,
            "email": "viewer@example.com",
            "role": "authenticated",
        },
    )

    user = verifier.verify_authorisation("Bearer valid-token")

    assert user.user_id == user_id
    assert user.email == "viewer@example.com"
    assert user.role == "authenticated"
    assert user.provider == "supabase"


def test_supabase_auth_verifier_rejects_missing_or_non_user_tokens() -> None:
    verifier = SupabaseAuthVerifier(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda *_: {
            "id": str(uuid4()),
            "role": "service_role",
        },
    )

    with pytest.raises(AuthenticationError, match="Sign in"):
        verifier.verify_authorisation(None)
    with pytest.raises(AuthenticationError, match="not authorised"):
        verifier.verify_authorisation("Bearer service-token")


def test_supabase_auth_verifier_requires_complete_https_configuration() -> None:
    assert SupabaseAuthVerifier("", "").configured is False
    assert SupabaseAuthVerifier(
        "http://example.test", "sb_publishable_test"
    ).configured is False
    assert SupabaseAuthVerifier("https://example.test", "sb_secret_test").configured is False
    with pytest.raises(AuthConfigurationError):
        SupabaseAuthVerifier("", "").verify_authorisation("Bearer token")


def test_entra_auth_verifier_accepts_an_api_token_with_the_required_scope() -> None:
    user_id = str(uuid4())
    verifier = EntraAuthVerifier(
        "https://firstroll-login.ciamlogin.com/00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "access_as_user",
        transport=lambda token: {
            "oid": user_id,
            "emails": ["viewer@example.com"],
            "scp": "openid access_as_user",
        },
    )

    user = verifier.verify_authorisation("Bearer valid-entra-token")

    assert user.user_id == user_id
    assert user.email == "viewer@example.com"
    assert user.role == "authenticated"
    assert user.provider == "entra"


def test_entra_auth_verifier_rejects_missing_scope_and_incomplete_configuration() -> None:
    verifier = EntraAuthVerifier(
        "https://firstroll-login.ciamlogin.com/00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "access_as_user",
        transport=lambda token: {"sub": "customer", "scp": "openid"},
    )

    with pytest.raises(AuthenticationError, match="not authorised"):
        verifier.verify_authorisation("Bearer wrong-scope")
    assert EntraAuthVerifier("http://example.test", "not-a-uuid").configured is False


def test_auth_provider_factory_selects_exactly_one_provider(monkeypatch) -> None:
    monkeypatch.setenv("FIRSTROLL_AUTH_PROVIDER", "entra")
    monkeypatch.setenv(
        "ENTRA_AUTHORITY",
        "https://firstroll-login.ciamlogin.com/00000000-0000-0000-0000-000000000001",
    )
    monkeypatch.setenv("ENTRA_API_CLIENT_ID", "00000000-0000-0000-0000-000000000002")

    assert isinstance(configured_auth_verifier(), EntraAuthVerifier)

    monkeypatch.setenv("FIRSTROLL_AUTH_PROVIDER", "unknown")
    with pytest.raises(AuthConfigurationError, match="FIRSTROLL_AUTH_PROVIDER"):
        configured_auth_verifier()


def test_auth_me_and_public_study_require_a_verified_bearer_token(monkeypatch) -> None:
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
    monkeypatch.setattr(main, "auth_verifier", verifier)
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    client = TestClient(main.app)

    missing = client.get("/api/auth/me")
    authenticated = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer valid-token"},
    )
    gated_study = client.post(
        "/api/discovery/films/Q1/study",
        json={"question": "How is space organised?"},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert authenticated.json()["user"] == {
        "id": user_id,
        "email": "viewer@example.com",
        "role": "authenticated",
        "provider": "supabase",
    }
    assert gated_study.status_code == 503
    assert gated_study.json()["detail"] == (
        "Deep Study is not fully configured on this deployment yet."
    )


def test_personal_youtube_key_requires_authentication_and_is_request_scoped(
    monkeypatch,
) -> None:
    verifier = SupabaseAuthVerifier(
        "https://example.supabase.co",
        "sb_publishable_test",
        transport=lambda *_: {
            "id": str(uuid4()),
            "email": "viewer@example.com",
            "role": "authenticated",
        },
    )
    captured = {}

    class RequestVideoService:
        def search(self, film_id, film, youtube_api_key=None):
            captured["film_id"] = film_id
            captured["film"] = film
            captured["youtube_api_key"] = youtube_api_key
            return FilmVideoBundle(
                film_id=film_id,
                query="Test Film",
                fetched_at="2099-08-16T00:00:00+00:00",
                videos=[],
                providers=[],
                notice="Request-scoped test.",
            )

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setattr(main, "auth_verifier", verifier)
    monkeypatch.setattr(main, "video_service", RequestVideoService())
    monkeypatch.setattr(
        main.discovery_service,
        "detail",
        lambda _: {"film": {"id": "Q1", "title": "Test Film"}},
    )
    client = TestClient(main.app)
    provider_headers = {"X-FirstRoll-YouTube-Key": "personal-youtube-key-12345"}

    missing = client.post("/api/discovery/films/Q1/videos", headers=provider_headers)
    response = client.post(
        "/api/discovery/films/Q1/videos",
        headers={"Authorization": "Bearer verified-token", **provider_headers},
    )

    assert missing.status_code == 401
    assert response.status_code == 200
    assert captured["youtube_api_key"] == "personal-youtube-key-12345"
