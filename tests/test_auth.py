from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.backend import main
from app.backend.auth import (
    AuthConfigurationError,
    AuthenticationError,
    SupabaseAuthVerifier,
)


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
    }
    assert gated_study.status_code == 503
    assert gated_study.json()["detail"] == (
        "Deep Study is not fully configured on this deployment yet."
    )
