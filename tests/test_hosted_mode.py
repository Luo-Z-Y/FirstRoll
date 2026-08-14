from fastapi.testclient import TestClient

from app.backend import main


def test_public_mode_keeps_health_and_discovery_status_available(monkeypatch) -> None:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    client = TestClient(main.app)

    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.get("/api/discovery/status")

    assert response.status_code == 200
    assert response.json()["features"] == {
        "public_mode": True,
        "video_analysis": False,
        "deep_study": False,
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


def test_local_mode_retains_video_analysis_feature(monkeypatch) -> None:
    monkeypatch.delenv("FIRSTROLL_PUBLIC_MODE", raising=False)
    monkeypatch.delenv("FIRSTROLL_VIDEO_ANALYSIS_ENABLED", raising=False)

    assert main.public_mode_enabled() is False
    assert main.video_analysis_enabled() is True
