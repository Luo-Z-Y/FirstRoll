import pytest
from fastapi.testclient import TestClient

from app.backend import main
from app.backend.criticism import ReviewSource, build_bundle


def test_public_mode_keeps_health_and_discovery_status_available(monkeypatch) -> None:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    client = TestClient(main.app)

    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.get("/api/discovery/status")

    assert response.status_code == 200
    features = response.json()["features"]
    assert features == {
        "public_mode": True,
        "video_analysis": False,
        "deep_study": False,
        "authentication": {
            "provider": "Supabase Auth",
            "state": "not_configured",
            "configured": False,
        },
    }
    assert "local_library" not in response.json()


def test_public_mode_serves_hosted_frontend_configuration(monkeypatch) -> None:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    client = TestClient(main.app)

    response = client.get("/assets/config.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "publicMode: true" in response.text
    assert "videoAnalysisEnabled: false" in response.text
    assert 'supabaseUrl: ""' in response.text
    assert 'supabasePublishableKey: ""' in response.text


def test_public_mode_root_identifies_the_api(monkeypatch) -> None:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    client = TestClient(main.app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "FirstRoll API",
        "status": "ok",
        "health": "/api/health",
    }


def test_public_mode_does_not_publish_local_or_expensive_features(monkeypatch) -> None:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    client = TestClient(main.app)

    assert client.get("/api/settings").status_code == 404
    assert client.get("/api/library/status").status_code == 404
    assert (
        client.post(
            "/api/analyze",
            files={"video": ("clip.mp4", b"not-a-video", "video/mp4")},
        ).status_code
        == 503
    )
    assert (
        client.post(
            "/api/discovery/films/Q1/study",
            json={"question": "How is space organised?"},
        ).status_code
        == 503
    )


@pytest.mark.parametrize(
    ("route", "adapter_name", "provider"),
    [
        ("letterboxd-web", "letterboxd_web_adapter", "Letterboxd public web"),
        ("guardian-web", "guardian_web_adapter", "The Guardian public web"),
    ],
)
def test_public_mode_publishes_bounded_public_review_importers(
    monkeypatch,
    route: str,
    adapter_name: str,
    provider: str,
) -> None:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    review = ReviewSource(
        source_id="R1",
        provider=provider,
        review_id="review-1",
        title="A public review",
        summary="An attributed public review with enough detail to display in FirstRoll.",
        author="Film critic",
        url=(
            "https://letterboxd.com/critic/film/example/"
            if route == "letterboxd-web"
            else "https://www.theguardian.com/film/example"
        ),
        language="en",
    )
    monkeypatch.setattr(
        main.discovery_service,
        "detail",
        lambda _: {"film": {"title": "Example Film", "year": 2024}},
    )
    monkeypatch.setattr(
        getattr(main, adapter_name),
        "fetch_reviews",
        lambda _: ("provider-film", "Example Film", [review]),
    )
    monkeypatch.setattr(
        main,
        "cache_raw_criticism",
        lambda film_id, provider_id, provider_title, reviews, provider_name: build_bundle(
            film_id,
            provider_id,
            provider_title,
            reviews,
            [],
            provider=provider_name,
            claim_status="pending",
        ),
    )
    client = TestClient(main.app)

    response = client.post(f"/api/discovery/films/Q1/criticism/{route}")

    assert response.status_code == 200
    payload = response.json()["critical_research"]
    assert payload["provider"] == provider
    assert payload["reviews"][0]["author"] == "Film critic"


def test_local_mode_retains_video_analysis_feature(monkeypatch) -> None:
    monkeypatch.delenv("FIRSTROLL_PUBLIC_MODE", raising=False)
    monkeypatch.delenv("FIRSTROLL_VIDEO_ANALYSIS_ENABLED", raising=False)

    assert main.public_mode_enabled() is False
    assert main.video_analysis_enabled() is True
