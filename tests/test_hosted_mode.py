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


def test_public_mode_does_not_register_generated_api_documentation() -> None:
    public_app = main.create_api_application(public_mode=True)
    local_app = main.create_api_application(public_mode=False)

    assert public_app.docs_url is None
    assert public_app.redoc_url is None
    assert public_app.openapi_url is None
    assert {route.path for route in public_app.routes}.isdisjoint(
        {"/docs", "/redoc", "/openapi.json"}
    )

    assert local_app.docs_url == "/docs"
    assert local_app.redoc_url == "/redoc"
    assert local_app.openapi_url == "/openapi.json"
    assert {"/docs", "/redoc", "/openapi.json"}.issubset({route.path for route in local_app.routes})


def test_local_startup_prewarms_embeddings_without_blocking_public_mode(monkeypatch) -> None:
    class FakeIndex:
        calls = 0

        def start_embedding_warmup(self):
            self.calls += 1
            return {"state": "warming"}

    index = FakeIndex()
    monkeypatch.setattr(main, "library_index", index)
    monkeypatch.delenv("FIRSTROLL_PUBLIC_MODE", raising=False)
    monkeypatch.delenv("FIRSTROLL_PREWARM_EMBEDDINGS", raising=False)

    main.start_local_embedding_warmup()

    assert index.calls == 1

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    main.start_local_embedding_warmup()

    assert index.calls == 1


def test_local_agent_adapter_is_default_off_and_has_no_http_route(monkeypatch) -> None:
    monkeypatch.delenv("FIRSTROLL_PUBLIC_MODE", raising=False)
    monkeypatch.delenv("FIRSTROLL_LOCAL_AGENT_ENABLED", raising=False)

    assert main.local_agent_enabled() is False
    with pytest.raises(RuntimeError, match="disabled"):
        main.build_local_agent_services()
    with pytest.raises(RuntimeError, match="disabled"):
        main.build_local_autonomous_agent()
    with pytest.raises(RuntimeError, match="disabled"):
        main.build_local_autonomous_run_engine()

    monkeypatch.setenv("FIRSTROLL_LOCAL_AGENT_ENABLED", "true")
    assert main.local_agent_enabled() is True
    adapter = main.build_local_agent_services()
    assert adapter.detail == main.discovery_service.detail
    assert adapter.study_service is main.study_service
    autonomous = main.build_local_autonomous_agent()
    assert autonomous.services.study_service is main.study_service
    durable = main.build_local_autonomous_run_engine()
    assert durable.executor.study_service is main.study_service
    assert not any("agent" in getattr(route, "path", "") for route in main.app.routes)
    assert not any("agent" in path for path in main.app.openapi()["paths"])

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    assert main.local_agent_enabled() is False


def test_local_embedding_prewarm_can_be_disabled(monkeypatch) -> None:
    class FakeIndex:
        calls = 0

        def start_embedding_warmup(self):
            self.calls += 1

    index = FakeIndex()
    monkeypatch.setattr(main, "library_index", index)
    monkeypatch.delenv("FIRSTROLL_PUBLIC_MODE", raising=False)
    monkeypatch.setenv("FIRSTROLL_PREWARM_EMBEDDINGS", "false")

    main.start_local_embedding_warmup()

    assert index.calls == 0


def test_public_mode_serves_hosted_frontend_configuration(monkeypatch) -> None:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_BUILD_CHANNEL", "live")
    monkeypatch.setenv("FIRSTROLL_BUILD_NUMBER", "84")
    monkeypatch.setenv("FIRSTROLL_BUILD_COMMIT", "abc12345")
    client = TestClient(main.app)

    response = client.get("/assets/config.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "publicMode: true" in response.text
    assert "videoAnalysisEnabled: false" in response.text
    assert 'supabaseUrl: ""' in response.text
    assert 'supabasePublishableKey: ""' in response.text
    assert 'buildId: "v84"' in response.text
    assert "buildNumber: 84" in response.text
    assert 'buildChannel: "live"' in response.text
    assert 'buildCommit: "abc12345"' in response.text


def test_hosted_frontend_preview_serves_public_ui_with_next_local_build(monkeypatch) -> None:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_SERVE_HOSTED_FRONTEND", "true")
    monkeypatch.delenv("FIRSTROLL_BUILD_NUMBER", raising=False)
    monkeypatch.delenv("FIRSTROLL_BUILD_CHANNEL", raising=False)
    monkeypatch.setattr(
        main,
        "_git_value",
        lambda *args: "83" if args[:2] == ("rev-list", "--count") else "abc12345",
    )
    client = TestClient(main.app)

    page = client.get("/")
    config = client.get("/assets/config.js")

    assert page.status_code == 200
    assert "FirstRoll — Film discovery and analysis" in page.text
    assert "publicMode: true" in config.text
    assert 'buildId: "v84"' in config.text
    assert 'buildChannel: "local"' in config.text


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
