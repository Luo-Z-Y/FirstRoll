from __future__ import annotations

import asyncio
import json
from functools import partial
from threading import Event, Thread
from types import SimpleNamespace

import httpx
import pytest


FILM_PATH = "/api/discovery/films/Q1"
CRITICISM_ADAPTERS = {
    "douban": "douban_adapter",
    "letterboxd": "letterboxd_adapter",
    "letterboxd-web": "letterboxd_web_adapter",
    "guardian-web": "guardian_web_adapter",
    "crossref": "crossref_research_adapter",
}
WATCHDOG_SECONDS = 10


@pytest.fixture
def api(monkeypatch, tmp_path):
    # Set paths before importing main: no local settings, books or models are needed.
    for name, suffix in {
        "HOME": "home",
        "FIRSTROLL_SETTINGS_PATH": "settings.json",
        "FIRSTROLL_LIBRARY_PATH": "library",
        "FIRSTROLL_LIBRARY_MANIFEST": "library.json",
        "FIRSTROLL_LIBRARY_INDEX": "library.sqlite3",
        "FIRSTROLL_DOUBAN_MCP_PATH": "uninstalled/index.js",
    }.items():
        monkeypatch.setenv(name, str(tmp_path / suffix))
    for name, value in {
        "FIRSTROLL_PUBLIC_MODE": "false",
        "FIRSTROLL_PREWARM_EMBEDDINGS": "false",
        "FIRSTROLL_EMBEDDINGS": "false",
        "FIRSTROLL_AUTH_PROVIDER": "supabase",
        "FIRSTROLL_QUOTA_PROVIDER": "supabase",
    }.items():
        monkeypatch.setenv(name, value)

    from app.backend import main

    # Empty fakes fail on unexpected service access, including caches without path env vars.
    for name in (
        "settings_store", "tmdb_discovery_service", "discovery_service",
        "library_catalogue", "library_index", "study_service", "douban_adapter",
        "guardian_web_adapter", "crossref_research_adapter", "letterboxd_adapter",
        "letterboxd_web_adapter", "criticism_store", "youtube_video_adapter",
        "bilibili_video_adapter", "video_store", "video_service", "auth_verifier",
        "quota_client", "study_run_store",
    ):
        monkeypatch.setattr(main, name, SimpleNamespace())
    monkeypatch.setattr(main, "reception_cache", {})
    return main


class BlockedCall:
    def __init__(self, function):
        self.function = function
        self.started = Event()
        self.release = Event()
        self.finished = Event()

    def __call__(self, *args, **kwargs):
        self.started.set()
        try:
            self.release.wait()
            return self.function(*args, **kwargs)
        finally:
            self.finished.set()


def block_call(monkeypatch, target, name):
    blocked = BlockedCall(getattr(target, name))
    monkeypatch.setattr(target, name, blocked)
    return blocked


async def health_while_blocked(api, blocked, method, path, *, at_health=None, **kwargs):
    """Exercise both requests on one loop; the watchdog only prevents a deadlock."""
    watchdog_fired = Event()

    def release_on_deadlock():
        if not blocked.release.wait(WATCHDOG_SECONDS):
            watchdog_fired.set()
            blocked.release.set()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api.app), base_url="http://127.0.0.1"
    ) as client:
        watchdog = Thread(target=release_on_deadlock, daemon=True)
        watchdog.start()
        request = asyncio.create_task(client.request(method, path, **kwargs))
        try:
            assert await asyncio.to_thread(blocked.started.wait, WATCHDOG_SECONDS)
            health = await asyncio.wait_for(client.get("/api/health"), WATCHDOG_SECONDS)
            assert health.status_code == 200
            assert health.json()["status"] == "ok"
            # A timeout on this loop alone would pass after the blocking call returned.
            assert not watchdog_fired.is_set(), "The ASGI loop stalled until watchdog release."
            assert not blocked.release.is_set()
            assert not blocked.finished.is_set()
            assert not request.done()
            if at_health is not None:
                at_health()
        finally:
            blocked.release.set()
            try:
                response = await asyncio.wait_for(request, WATCHDOG_SECONDS)
            finally:
                watchdog.join(WATCHDOG_SECONDS)
                assert not watchdog.is_alive()
        return response


@pytest.fixture
def discovery(api):
    calls = []
    saved = []
    film = {"id": "Q1", "title": "Test Film", "awards": ["A", "B", "C", "D"]}
    bundles = {}
    for provider in api.CRITICISM_PROVIDERS.values():
        review = api.ReviewSource(
            source_id="R1", provider=provider, review_id="review-1", title="Test review",
            summary="A synthetic attributed review.", url="https://example.invalid/review",
            language="en",
        )
        bundles[provider] = api.build_bundle(
            "Q1", "provider-film", "Test Film", [review], [],
            provider=provider, claim_status="pending",
        )

    def detail(film_id):
        assert film_id == "Q1"
        calls.append("film")
        return {"film": film}

    def fetch_reviews(provider, selected_film):
        assert selected_film is film
        calls.append("reviews")
        return "provider-film", "Test Film", bundles[provider].reviews

    async def douban_reviews(selected_film):
        return fetch_reviews("Douban", selected_film)

    def load(film_id, provider):
        assert film_id == "Q1"
        calls.append("cache_read")
        return bundles[provider]

    def save(bundle):
        calls.append("cache_save")
        saved.append(bundle)

    def structure_reviews(selected_film, reviews):
        assert selected_film is film
        assert reviews is bundles["Douban"].reviews
        calls.append("structure")
        return []

    def status(provider):
        calls.append(f"{provider}_status")
        return {"provider": provider, "installed": True}

    def score(provider, selected_film):
        assert selected_film is film
        calls.append(f"{provider}_score")
        return {"provider": provider, "normalised": 80 if provider == "douban" else 70}

    async def douban_score(selected_film):
        return score("douban", selected_film)

    api.discovery_service.detail = detail
    for slug, attribute in CRITICISM_ADAPTERS.items():
        getattr(api, attribute).fetch_reviews = partial(
            fetch_reviews, api.CRITICISM_PROVIDERS[slug]
        )
    api.douban_adapter.fetch_reviews = douban_reviews
    api.douban_adapter.status = partial(status, "douban")
    api.letterboxd_web_adapter.status = partial(status, "letterboxd")
    api.douban_adapter.fetch_score = douban_score
    api.letterboxd_web_adapter.fetch_score = partial(score, "letterboxd")
    api.criticism_store.load = load
    api.criticism_store.save = save
    api.study_service.structure_reviews = structure_reviews
    return SimpleNamespace(calls=calls, saved=saved, bundles=bundles)


DISCOVERY_REQUESTS = [
    ("GET", "reception"),
    *(("POST", f"criticism/{provider}") for provider in CRITICISM_ADAPTERS),
    ("POST", "criticism/douban/structure"),
]


@pytest.mark.parametrize(("method", "suffix"), DISCOVERY_REQUESTS)
def test_each_async_discovery_consumer_keeps_health_responsive(
    api, discovery, monkeypatch, method, suffix,
):
    blocked = block_call(monkeypatch, api.discovery_service, "detail")

    def before_film():
        assert discovery.calls == []

    response = asyncio.run(health_while_blocked(
        api, blocked, method, f"{FILM_PATH}/{suffix}", at_health=before_film,
    ))

    assert response.status_code == 200
    if suffix == "reception":
        assert response.json() == {
            "aggregate": {"score": 75.0, "scale": 100, "method": "50% Douban · 50% Letterboxd"},
            "scores": [
                {"provider": "douban", "normalised": 80},
                {"provider": "letterboxd", "normalised": 70},
            ],
            "providers": {
                "douban": {"provider": "douban", "installed": True},
                "letterboxd": {"provider": "letterboxd", "installed": True},
            },
            "awards": ["A", "B", "C"],
        }
        assert discovery.calls[:3] == ["film", "douban_status", "letterboxd_status"]
        assert sorted(discovery.calls[3:]) == ["douban_score", "letterboxd_score"]
        assert api.reception_cache["Q1"] == response.json()
    else:
        expected = ["film", "reviews", "cache_read", "cache_save"]
        if suffix.endswith("/structure"):
            expected = ["film", "cache_read", "structure", "cache_save"]
            assert discovery.saved[0].claim_status == "structured"
            assert discovery.bundles["Douban"].claim_status == "pending"
        assert discovery.calls == expected
        assert response.json() == {"critical_research": discovery.saved[0].model_dump()}


@pytest.mark.parametrize("adapter", ["douban_adapter", "letterboxd_web_adapter"])
def test_reception_status_reads_keep_health_responsive(api, discovery, monkeypatch, adapter):
    blocked = block_call(monkeypatch, getattr(api, adapter), "status")
    response = asyncio.run(health_while_blocked(api, blocked, "GET", f"{FILM_PATH}/reception"))
    assert response.status_code == 200
    assert response.json()["aggregate"]["score"] == 75.0


@pytest.mark.parametrize(("provider", "stage"), [
    (provider, stage)
    for provider in CRITICISM_ADAPTERS
    for stage in ("provider", "cache")
    if provider != "douban" or stage == "cache"
])
def test_criticism_sync_provider_and_cache_work_keeps_health_responsive(
    api, discovery, monkeypatch, provider, stage,
):
    target, name = (
        (getattr(api, CRITICISM_ADAPTERS[provider]), "fetch_reviews")
        if stage == "provider" else (api.criticism_store, "load")
    )
    blocked = block_call(monkeypatch, target, name)
    response = asyncio.run(health_while_blocked(
        api, blocked, "POST", f"{FILM_PATH}/criticism/{provider}",
    ))
    assert response.status_code == 200
    assert discovery.calls == ["film", "reviews", "cache_read", "cache_save"]
    assert response.json() == {"critical_research": discovery.saved[0].model_dump()}


@pytest.mark.parametrize("cached", [True, False])
def test_structuring_cache_read_precedes_model_without_blocking_health(
    api, discovery, monkeypatch, cached,
):
    if not cached:
        api.criticism_store.load = lambda *_args: None
    blocked = block_call(monkeypatch, api.criticism_store, "load")

    def before_cache():
        assert discovery.calls == ["film"]

    response = asyncio.run(health_while_blocked(
        api, blocked, "POST", f"{FILM_PATH}/criticism/douban/structure", at_health=before_cache,
    ))
    if cached:
        assert response.status_code == 200
        assert discovery.calls == ["film", "cache_read", "structure", "cache_save"]
        assert response.json() == {"critical_research": discovery.saved[0].model_dump()}
    else:
        assert response.status_code == 409
        assert response.json() == {
            "detail": "Fetch and cache attributed reviews before structuring them.",
        }
        assert discovery.calls == ["film"]


@pytest.fixture
def stream(api, monkeypatch):
    from app.backend.research_stream import StudyRunStore

    calls = []
    film = {"id": "Q1", "title": "Test Film"}
    packet = SimpleNamespace(theory_sources=[], critical_claims=[], attributed_sources=[])
    quota = {"allowed": True, "user": {"remaining": 2}, "global": {"remaining": 29}}
    state = SimpleNamespace(calls=calls, platform_configured=True, api_key=None, quota=quota)
    user = {"id": "viewer", "email": "viewer@example.invalid", "provider": "supabase"}

    def verify(authorisation):
        assert authorisation == "Bearer test-token"
        calls.append("auth")
        return SimpleNamespace(as_dict=lambda: user)

    boundary = api.hosted_deep_study_boundary_enabled

    def check_boundary():
        calls.append("config")
        return boundary()

    def secret_state(connector):
        assert connector == "deepseek"
        calls.append("settings")
        return SimpleNamespace(configured=state.platform_configured)

    runs = StudyRunStore()
    original_create, original_complete = runs.create, runs.complete

    def create(run_id, owner_id):
        assert owner_id == "supabase:viewer"
        calls.append("run")
        original_create(run_id, owner_id)

    def complete(run_id, owner_id, result):
        calls.append("complete")
        original_complete(run_id, owner_id, result)

    def detail(film_id):
        assert film_id == "Q1"
        calls.append("film")
        return {"film": film}

    def prepare(film_id, selected_film, question, *, public_mode, trace):
        assert (film_id, question, public_mode) == ("Q1", "Framing", True)
        assert selected_film is film
        calls.append("evidence")
        return {"packet": packet, "reading": {"passages": []}, "claims": []}

    def reserve(identity):
        assert (identity.provider, identity.subject) == ("supabase", "viewer")
        assert identity.legacy_authorisation == "Bearer test-token"
        calls.append("quota")
        return SimpleNamespace(as_dict=lambda: quota)

    def generate(selected_film, passages, question, claims, *, evidence_packet, api_key, trace):
        assert selected_film is film and evidence_packet is packet
        assert (passages, question, claims, api_key) == ([], "Framing", [], state.api_key)
        calls.append("model")
        return {"title": "Test study", "sections": [], "quality": {"status": "passed"}}

    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    monkeypatch.setenv("FIRSTROLL_DEEP_STUDY_ENABLED", "true")
    monkeypatch.setattr(api, "hosted_deep_study_boundary_enabled", check_boundary)
    monkeypatch.setattr(api, "prepare_film_study", prepare)
    monkeypatch.setattr(api, "study_run_store", runs)
    monkeypatch.setattr(runs, "create", create)
    monkeypatch.setattr(runs, "complete", complete)
    api.auth_verifier.verify_authorisation = verify
    api.auth_verifier.configured = True
    api.settings_store.secret_state = secret_state
    api.discovery_service.detail = detail
    api.quota_client.reserve = reserve
    api.quota_client.configured = True
    api.study_service.generate = generate
    return state


STREAM_STAGES = {
    "auth": ("auth_verifier", "verify_authorisation"),
    "settings": ("settings_store", "secret_state"),
    "film": ("discovery_service", "detail"),
    "evidence": (None, "prepare_film_study"),
    "quota": ("quota_client", "reserve"),
    "model": ("study_service", "generate"),
}
STREAM_ORDER = [
    "auth", "config", "config", "settings", "run", "film", "evidence", "quota", "model",
    "complete",
]


@pytest.mark.parametrize("stage", STREAM_STAGES)
def test_sse_boundaries_keep_health_responsive_and_preserve_order(api, stream, monkeypatch, stage):
    attribute, name = STREAM_STAGES[stage]
    blocked = block_call(monkeypatch, getattr(api, attribute) if attribute else api, name)

    def before_stage():
        assert stream.calls == STREAM_ORDER[:STREAM_ORDER.index(stage)]

    response = asyncio.run(health_while_blocked(
        api, blocked, "POST", f"{FILM_PATH}/study/stream", at_health=before_stage,
        json={"question": "Framing"}, headers={"Authorization": "Bearer test-token"},
    ))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert stream.calls == STREAM_ORDER
    frames = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert [frame["kind"] for frame in frames] == [
        "film_resolving", "existing_evidence_loading", "evidence_assessed", "study_drafting",
        "quality_checked", "run_completed",
    ]
    run_id = response.headers["x-firstroll-run-id"]
    assert all(frame["run_id"] == run_id for frame in frames)
    stored = api.study_run_store.read(run_id, "supabase:viewer")
    assert stored.status == "complete"
    assert set(stored.result) == {"film_id", "study", "quota", "credential_source"}
    assert stored.result["film_id"] == "Q1"
    assert stored.result["study"]["title"] == "Test study"
    assert stored.result["quota"] == stream.quota
    assert stored.result["credential_source"] == "firstroll_platform"
    for wrong_owner in ("supabase:other-viewer", "entra:viewer"):
        with pytest.raises(KeyError):
            api.study_run_store.read(run_id, wrong_owner)


@pytest.mark.parametrize(("error", "status_code"), [
    ("AuthenticationError", 401), ("AuthConfigurationError", 503),
])
def test_sse_rejected_auth_never_creates_a_run_or_spends_quota(
    api, stream, monkeypatch, error, status_code,
):
    def reject(_authorisation):
        stream.calls.append("auth")
        raise getattr(api, error)("Test authentication failure.")

    api.auth_verifier.verify_authorisation = reject
    blocked = block_call(monkeypatch, api.auth_verifier, "verify_authorisation")

    def before_verification():
        assert stream.calls == []

    response = asyncio.run(health_while_blocked(
        api, blocked, "POST", f"{FILM_PATH}/study/stream", at_health=before_verification,
        json={"question": "Framing"}, headers={"Authorization": "Bearer test-token"},
    ))
    assert response.status_code == status_code
    assert response.json() == {"detail": "Test authentication failure."}
    assert "x-firstroll-run-id" not in response.headers
    if status_code == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert stream.calls == ["auth"]


@pytest.mark.parametrize("personal_key", [False, True])
def test_sse_settings_gate_precedes_run_and_preserves_personal_key_bypass(
    api, stream, monkeypatch, personal_key,
):
    stream.platform_configured = False
    headers = {"Authorization": "Bearer test-token"}
    if personal_key:
        stream.api_key = "synthetic-personal-session-key"
        headers["X-FirstRoll-DeepSeek-Key"] = stream.api_key
        blocked = block_call(monkeypatch, api.auth_verifier, "verify_authorisation")
    else:
        blocked = block_call(monkeypatch, api.settings_store, "secret_state")

    def before_gate():
        assert stream.calls == ([] if personal_key else ["auth", "config", "config"])

    response = asyncio.run(health_while_blocked(
        api, blocked, "POST", f"{FILM_PATH}/study/stream", at_health=before_gate,
        json={"question": "Framing"}, headers=headers,
    ))
    if personal_key:
        assert response.status_code == 200
        assert stream.calls == [
            "auth", "config", "run", "film", "evidence", "quota", "model", "complete",
        ]
        stored = api.study_run_store.read(response.headers["x-firstroll-run-id"], "supabase:viewer")
        assert stored.result["credential_source"] == "personal_session"
    else:
        assert response.status_code == 503
        assert response.json() == {
            "detail": "Deep Study is not fully configured on this deployment yet.",
        }
        assert "x-firstroll-run-id" not in response.headers
        assert stream.calls == ["auth", "config", "config", "settings"]


@pytest.mark.parametrize("action", ["upload", "rebuild"])
@pytest.mark.parametrize("stage", ["catalogue", "index_status"])
def test_library_response_metadata_reads_keep_health_responsive(
    api, monkeypatch, action, stage,
):
    calls = []
    uploaded = []
    document = {"id": "document-1", "title": "Test document", "format": "PDF"}
    catalogue = {"state": "ready", "document_count": 1, "documents": [document]}
    index = {"state": "ready", "document_count": 1}

    def add(filename, source):
        assert filename == "test.pdf" and not source.closed
        uploaded.append(source)
        calls.append("upload")
        return document

    def build(selected_catalogue):
        assert selected_catalogue is api.library_catalogue
        calls.append("rebuild")

    def public_catalogue():
        assert all(source.closed for source in uploaded)
        calls.append("catalogue")
        return dict(catalogue)

    def status():
        calls.append("index_status")
        return index

    api.library_catalogue.add_document = add
    api.library_catalogue.public_catalogue = public_catalogue
    api.library_index.build = build
    api.library_index.status = status
    target, name = (
        (api.library_catalogue, "public_catalogue") if stage == "catalogue"
        else (api.library_index, "status")
    )
    blocked = block_call(monkeypatch, target, name)
    path = "/api/settings/library"
    kwargs = {}
    if action == "upload":
        kwargs["files"] = {"document": ("test.pdf", b"synthetic upload", "application/pdf")}
    else:
        path += "/rebuild"

    def before_metadata():
        assert calls == ([action] if stage == "catalogue" else [action, "catalogue"])

    response = asyncio.run(health_while_blocked(
        api, blocked, "POST", path, at_health=before_metadata, **kwargs,
    ))
    assert response.status_code == 200
    assert calls == [action, "catalogue", "index_status"]
    expected = {
        **catalogue, "index": index, "supported_formats": ["EPUB", "MD", "PDF", "TXT"],
        "max_upload_mb": 500, "indexable_document_count": 1, "index_needs_rebuild": False,
    }
    assert response.json() == (
        {"document": document, "library": expected} if action == "upload" else expected
    )
    assert all(source.closed for source in uploaded)
