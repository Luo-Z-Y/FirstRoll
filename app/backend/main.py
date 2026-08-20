import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, SecretStr
from starlette.concurrency import run_in_threadpool

from app.backend.criticism import (
    CrossrefResearchAdapter,
    CriticalResearchBundle,
    CriticismError,
    CriticismStore,
    DoubanMcpAdapter,
    GuardianPublicWebAdapter,
    LetterboxdApiAdapter,
    LetterboxdPublicWebAdapter,
    ReviewSource,
    build_bundle,
)
from app.backend.auth import AuthConfigurationError, AuthenticationError, configured_auth_verifier
from app.backend.discovery import DiscoveryService
from app.backend.evidence import EvidencePacket
from app.backend.library import MAX_DOCUMENT_BYTES, SUPPORTED_SUFFIXES, LocalLibraryCatalogue
from app.backend.library_index import LocalLibraryIndex
from app.backend.public_study import build_public_study_retrieval
from app.backend.quota import (
    QuotaIdentity,
    QuotaConfigurationError,
    QuotaExceededError,
    QuotaServiceError,
    configured_quota_client,
)
from app.backend.research_stream import (
    ResearchProgressStream,
    StudyRunStore,
    public_progress_message,
)
from app.backend.settings import CONNECTORS, LocalSettingsStore
from app.backend.study_service import DeepSeekStudyService, StudyGenerationError
from app.backend.video_sources import (
    BilibiliPublicVideoAdapter,
    FilmVideoService,
    FilmVideoStore,
    VideoSourceError,
    YouTubeVideoAdapter,
)

app = FastAPI(
    title="FirstRoll API",
    version="0.1.0",
    description="Evidence-grounded film discovery and scene analysis for filmmakers.",
)


def environment_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def public_mode_enabled() -> bool:
    return environment_flag("FIRSTROLL_PUBLIC_MODE")


def hosted_frontend_preview_enabled() -> bool:
    """Serve the hosted UI from FastAPI for an exact local production preview."""
    return environment_flag("FIRSTROLL_SERVE_HOSTED_FRONTEND")


def _git_value(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parents[2]), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def frontend_build_identity() -> dict[str, str | int]:
    """Return a comparable UI build identity for live and local frontends.

    A live build uses the Git commit count. A local preview deliberately uses
    the next number, making it clear that the working copy is the candidate
    which will follow the currently deployed release.
    """
    configured_channel = os.getenv("FIRSTROLL_BUILD_CHANNEL", "").strip().casefold()
    default_channel = (
        "local"
        if hosted_frontend_preview_enabled() or not public_mode_enabled()
        else "live"
    )
    channel = configured_channel or default_channel
    if channel not in {"local", "live", "preview"}:
        channel = default_channel

    configured_number = os.getenv("FIRSTROLL_BUILD_NUMBER", "").strip()
    git_count = _git_value("rev-list", "--count", "HEAD")
    raw_number = configured_number or git_count or "0"
    try:
        build_number = max(0, int(raw_number))
    except ValueError:
        build_number = 0
    if not configured_number and channel == "local":
        build_number += 1

    commit = (
        os.getenv("FIRSTROLL_BUILD_COMMIT", "").strip()
        or _git_value("rev-parse", "--short=8", "HEAD")
        or "unknown"
    )
    return {
        "buildId": f"v{build_number}",
        "buildNumber": build_number,
        "buildChannel": channel,
        "buildCommit": commit,
    }


def video_analysis_enabled() -> bool:
    return environment_flag(
        "FIRSTROLL_VIDEO_ANALYSIS_ENABLED",
        default=not public_mode_enabled(),
    )


allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FIRSTROLL_CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-FirstRoll-DeepSeek-Key",
            "X-FirstRoll-YouTube-Key",
        ],
        expose_headers=["X-FirstRoll-Run-ID"],
    )

settings_store = LocalSettingsStore()
discovery_service = DiscoveryService()
library_catalogue = LocalLibraryCatalogue()
library_index = LocalLibraryIndex()
study_service = DeepSeekStudyService(settings_store)
douban_adapter = DoubanMcpAdapter(settings_store)
guardian_web_adapter = GuardianPublicWebAdapter()
crossref_research_adapter = CrossrefResearchAdapter()
letterboxd_adapter = LetterboxdApiAdapter(settings_store)
letterboxd_web_adapter = LetterboxdPublicWebAdapter()
criticism_store = CriticismStore()
youtube_video_adapter = YouTubeVideoAdapter(settings_store)
bilibili_video_adapter = BilibiliPublicVideoAdapter()
video_store = FilmVideoStore()
video_service = FilmVideoService(youtube_video_adapter, bilibili_video_adapter, video_store)
auth_verifier = configured_auth_verifier()
quota_client = configured_quota_client()
study_run_store = StudyRunStore()
reception_cache: dict[str, dict] = {}
web_directory = Path(__file__).resolve().parents[1] / "web"


@app.get("/assets/config.js", include_in_schema=False)
def web_runtime_config() -> Response:
    public_mode = public_mode_enabled()
    video_analysis = video_analysis_enabled()
    auth_provider = os.getenv("FIRSTROLL_AUTH_PROVIDER", "supabase").strip().casefold()
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not supabase_publishable_key.startswith("sb_publishable_"):
        supabase_url = ""
        supabase_publishable_key = ""
    entra_authority = os.getenv("ENTRA_AUTHORITY", "").strip().rstrip("/")
    entra_spa_client_id = os.getenv("ENTRA_SPA_CLIENT_ID", "").strip()
    entra_api_scope = os.getenv("ENTRA_API_SCOPE", "").strip()
    if not all((entra_authority, entra_spa_client_id, entra_api_scope)):
        entra_authority = ""
        entra_spa_client_id = ""
        entra_api_scope = ""
    build = frontend_build_identity()
    content = (
        "window.FIRSTROLL_CONFIG = Object.freeze({\n"
        '  apiBase: "",\n'
        f"  publicMode: {str(public_mode).lower()},\n"
        f"  videoAnalysisEnabled: {str(video_analysis).lower()},\n"
        f"  authProvider: {json.dumps(auth_provider)},\n"
        f"  supabaseUrl: {json.dumps(supabase_url)},\n"
        f"  supabasePublishableKey: {json.dumps(supabase_publishable_key)},\n"
        f"  entraAuthority: {json.dumps(entra_authority)},\n"
        f"  entraSpaClientId: {json.dumps(entra_spa_client_id)},\n"
        f"  entraApiScope: {json.dumps(entra_api_scope)},\n"
        f"  buildId: {json.dumps(build['buildId'])},\n"
        f"  buildNumber: {build['buildNumber']},\n"
        f"  buildChannel: {json.dumps(build['buildChannel'])},\n"
        f"  buildCommit: {json.dumps(build['buildCommit'])},\n"
        "});\n"
    )
    return Response(
        content=content,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


app.mount("/assets", StaticFiles(directory=web_directory), name="web-assets")


class ConnectorSecretUpdate(BaseModel):
    value: SecretStr | None = None
    credentials: dict[str, SecretStr] | None = None


class FilmStudyRequest(BaseModel):
    question: str | None = None


def prepare_film_study(
    film_id: str,
    film: dict,
    question: str | None,
    *,
    public_mode: bool,
) -> dict:
    critical_bundles = criticism_store.load_all(film_id)
    claims = [
        claim.model_copy(update={"claim_id": f"C{index}"})
        for index, claim in enumerate(
            (claim for bundle in critical_bundles for claim in bundle.claims),
            start=1,
        )
    ]
    reviews = [review for bundle in critical_bundles for review in bundle.reviews]
    video_bundle = video_service.enrich_cached(film_id)
    reading = (
        build_public_study_retrieval(film, question)
        if public_mode
        else library_index.retrieve_for_film(
            film,
            focus=question,
            critical_claims=claims,
            limit=10,
        )
    )
    packet = EvidencePacket.from_retrieval(
        film,
        reading,
        question,
        claims,
        reviews=reviews,
        videos=video_bundle.videos if video_bundle else [],
    )
    return {
        "film": film,
        "claims": claims,
        "reading": reading,
        "packet": packet,
    }


def authenticated_user(request: Request) -> dict[str, str | None]:
    try:
        return auth_verifier.verify_authorisation(
            request.headers.get("Authorization")
        ).as_dict()
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def quota_identity(user: dict[str, str | None], request: Request) -> QuotaIdentity:
    """Build the persistence identity only after bearer-token verification."""

    return QuotaIdentity(
        provider=str(user.get("provider") or ""),
        subject=str(user.get("id") or ""),
        # The legacy adapter alone consumes this field. PostgreSQL deliberately
        # receives only provider and subject.
        legacy_authorisation=request.headers.get("Authorization"),
    )


def account_owner_id(user: dict[str, str | None]) -> str:
    """Namespace transient result ownership across identity providers."""

    identity = QuotaIdentity(
        provider=str(user.get("provider") or ""),
        subject=str(user.get("id") or ""),
    ).validated()
    return f"{identity.provider}:{identity.subject}"


def hosted_deep_study_enabled() -> bool:
    return bool(
        hosted_deep_study_boundary_enabled()
        and settings_store.secret_state("deepseek").configured
    )


def hosted_deep_study_boundary_enabled() -> bool:
    auth_provider = os.getenv("FIRSTROLL_AUTH_PROVIDER", "supabase").strip().casefold()
    return bool(
        public_mode_enabled()
        and environment_flag("FIRSTROLL_DEEP_STUDY_ENABLED")
        and auth_verifier.configured
        and quota_client.configured
        and (auth_provider != "entra" or quota_client.backend_owned)
    )


def personal_provider_key(request: Request, provider: str) -> str | None:
    header = {
        "deepseek": "X-FirstRoll-DeepSeek-Key",
        "youtube": "X-FirstRoll-YouTube-Key",
    }.get(provider)
    if header is None:
        raise ValueError("Unknown personal provider credential.")
    value = request.headers.get(header, "").strip()
    if not value:
        return None
    if not 16 <= len(value) <= 512 or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise HTTPException(status_code=400, detail=f"The personal {provider.title()} key is invalid.")
    return value


CRITICISM_PROVIDERS = {
    "crossref": "Crossref scholarship",
    "douban": "Douban",
    "letterboxd": "Letterboxd",
    "letterboxd-web": "Letterboxd public web",
    "guardian-web": "The Guardian public web",
}


def cache_raw_criticism(
    film_id: str,
    provider_film_id: str,
    provider_film_title: str,
    reviews: list[ReviewSource],
    provider: str,
) -> CriticalResearchBundle:
    existing = criticism_store.load(film_id, provider)
    same_sources = bool(existing) and [review.review_id for review in existing.reviews] == [
        review.review_id for review in reviews
    ]
    claims = existing.claims if existing and same_sources else []
    has_preserved_claims = bool(claims)
    bundle = build_bundle(
        film_id,
        provider_film_id,
        provider_film_title,
        reviews,
        claims,
        provider=provider,
        claim_status="structured" if has_preserved_claims else "pending",
        notice=(
            "Attributed reviews were refreshed. Previously structured claims remain "
            "visible until an explicit DeepSeek refresh."
            if has_preserved_claims
            else (
                "Attributed reviews were fetched from the named public source. They are "
                "secondary criticism, not verified film observations or creator statements."
            )
        ),
    )
    criticism_store.save(bundle)
    return bundle


def require_local_settings_request(request: Request) -> None:
    if public_mode_enabled():
        raise HTTPException(status_code=404, detail="FirstRoll settings are not published.")
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail="FirstRoll settings are available locally only.")


def public_connector(connector_id: str) -> dict:
    return next(
        connector
        for connector in settings_store.public_connectors()
        if connector["id"] == connector_id
    )


def public_library_settings() -> dict:
    catalogue = library_catalogue.public_catalogue()
    index = library_index.status()
    catalogue["index"] = index
    catalogue["supported_formats"] = sorted(
        suffix.lstrip(".").upper() for suffix in SUPPORTED_SUFFIXES
    )
    catalogue["max_upload_mb"] = MAX_DOCUMENT_BYTES // (1024 * 1024)
    catalogue["indexable_document_count"] = sum(
        document["format"] == "PDF" for document in catalogue["documents"]
    )
    catalogue["index_needs_rebuild"] = (
        index.get("document_count") != catalogue["indexable_document_count"]
        or (catalogue["indexable_document_count"] > 0 and index.get("state") != "ready")
    )
    return catalogue


def reception_summary(scores: list[dict]) -> dict:
    available = {
        str(score.get("provider") or "").casefold(): score
        for score in scores
        if isinstance(score.get("normalised"), (int, float))
    }
    douban = available.get("douban")
    letterboxd = available.get("letterboxd")
    aggregate = None
    if douban and letterboxd:
        aggregate = {
            "score": round(
                float(douban["normalised"]) * 0.5
                + float(letterboxd["normalised"]) * 0.5,
                1,
            ),
            "scale": 100,
            "method": "50% Douban · 50% Letterboxd",
        }
    return {"aggregate": aggregate, "scores": list(available.values())}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=FileResponse)
def web_app() -> Response:
    if public_mode_enabled() and not hosted_frontend_preview_enabled():
        return JSONResponse(
            {
                "service": "FirstRoll API",
                "status": "ok",
                "health": "/api/health",
            },
            headers={"Cache-Control": "no-store"},
        )
    return FileResponse(
        web_directory / "index.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    require_local_settings_request(request)
    page = Path(__file__).with_name("settings.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/api/settings")
def get_settings(request: Request) -> dict:
    require_local_settings_request(request)
    return {
        "connectors": settings_store.public_connectors(),
        "storage": {
            "kind": "local_private_file",
            "path_hint": ".firstroll/settings.json",
            "secrets_returned": False,
        },
    }


@app.get("/api/settings/library")
def get_settings_library(request: Request) -> dict:
    require_local_settings_request(request)
    return public_library_settings()


@app.post("/api/settings/library")
async def add_settings_library_document(
    request: Request,
    document: UploadFile = File(...),
) -> dict:
    require_local_settings_request(request)
    try:
        added = await run_in_threadpool(
            library_catalogue.add_document,
            document.filename or "",
            document.file,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await document.close()
    return {"document": added, "library": public_library_settings()}


@app.delete("/api/settings/library/{document_id}")
def remove_settings_library_document(document_id: str, request: Request) -> dict:
    require_local_settings_request(request)
    try:
        removed = library_catalogue.remove_document(document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"document": removed, "library": public_library_settings()}


@app.post("/api/settings/library/rebuild")
async def rebuild_settings_library_index(request: Request) -> dict:
    require_local_settings_request(request)
    try:
        await run_in_threadpool(library_index.build, library_catalogue)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="The private search index could not be rebuilt. Check the backend log.",
        ) from exc
    return public_library_settings()


@app.put("/api/settings/connectors/{connector_id}")
def save_connector_secret(
    connector_id: str,
    update: ConnectorSecretUpdate,
    request: Request,
) -> dict:
    require_local_settings_request(request)
    if connector_id not in CONNECTORS:
        raise HTTPException(status_code=404, detail="Unknown connector.")
    definitions = settings_store.credential_definitions(connector_id)
    values = update.credentials or {}
    if update.value is not None and len(definitions) == 1:
        values = {definitions[0]["id"]: update.value}
    if not values:
        raise HTTPException(status_code=400, detail="No credentials were supplied.")
    known = {definition["id"]: definition for definition in definitions}
    unknown = sorted(set(values) - set(known))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown credential fields: {', '.join(unknown)}.",
        )
    try:
        for credential_id, secret in values.items():
            definition = known[credential_id]
            if os.getenv(definition["environment_key"], "").strip():
                raise HTTPException(
                    status_code=409,
                    detail=f"This credential is controlled by {definition['environment_key']}.",
                )
            settings_store.set(definition["secret_key"], secret.get_secret_value())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connector": public_connector(connector_id)}


@app.delete("/api/settings/connectors/{connector_id}")
def clear_connector_secret(connector_id: str, request: Request) -> dict:
    require_local_settings_request(request)
    if connector_id not in CONNECTORS:
        raise HTTPException(status_code=404, detail="Unknown connector.")
    cleared = False
    environment_keys: list[str] = []
    for definition in settings_store.credential_definitions(connector_id):
        if os.getenv(definition["environment_key"], "").strip():
            environment_keys.append(definition["environment_key"])
            continue
        settings_store.clear(definition["secret_key"])
        cleared = True
    if not cleared and environment_keys:
        raise HTTPException(
            status_code=409,
            detail=f"Unset {', '.join(environment_keys)} in the backend environment.",
        )
    return {"connector": public_connector(connector_id)}


@app.post("/api/settings/connectors/{connector_id}/test")
async def test_connector(connector_id: str, request: Request) -> dict:
    require_local_settings_request(request)
    if connector_id not in CONNECTORS:
        raise HTTPException(status_code=404, detail="Unknown connector.")
    try:
        if connector_id == "deepseek":
            return await run_in_threadpool(study_service.test_connection)
        if connector_id == "douban":
            return await douban_adapter.test_connection()
        if connector_id == "letterboxd":
            return await run_in_threadpool(letterboxd_adapter.test_connection)
        if connector_id == "youtube":
            return await run_in_threadpool(youtube_video_adapter.test_connection)
        raise HTTPException(status_code=501, detail="This optional connector is not implemented yet.")
    except (StudyGenerationError, CriticismError, VideoSourceError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/contract")
def contract() -> dict:
    return {
        "endpoints": [
            "GET /settings",
            "GET /api/settings",
            "PUT /api/settings/connectors/{connector_id}",
            "GET /api/settings/library",
            "POST /api/settings/library",
            "DELETE /api/settings/library/{document_id}",
            "POST /api/settings/library/rebuild",
            "GET /api/discovery/status",
            "GET /api/auth/me",
            "GET /api/account/integrations",
            "GET /api/discovery/search",
            "GET /api/discovery/films/{film_id}",
            "GET /api/discovery/films/{film_id}/related",
            "GET /api/discovery/films/{film_id}/reception",
            "POST /api/discovery/films/{film_id}/videos",
            "POST /api/discovery/films/{film_id}/study",
            "POST /api/discovery/films/{film_id}/study/stream",
            "GET /api/research/runs/{run_id}",
            "POST /api/discovery/films/{film_id}/criticism/douban",
            "POST /api/discovery/films/{film_id}/criticism/letterboxd",
            "GET /api/library/status",
            "POST /api/analyze",
        ],
        "request": {
            "multipart/form-data": {
                "video": "binary file",
                "scene_sensitivity": "int 1..10",
                "shot_threshold": "float 0.05..0.95",
                "include_object_detection": "bool",
                "include_shot_scale": "bool",
            }
        },
        "response_keys": ["meta", "global", "shots", "scenes", "outputs"],
    }


@app.get("/api/discovery/status")
def discovery_status() -> dict:
    status = discovery_service.status()
    if not public_mode_enabled():
        local_library = library_catalogue.public_catalogue()
        local_library["index"] = library_index.status()
        status["local_library"] = local_library
    status["features"] = {
        "public_mode": public_mode_enabled(),
        "video_analysis": video_analysis_enabled(),
        "deep_study": not public_mode_enabled() or hosted_deep_study_enabled(),
        "authentication": auth_verifier.status(),
    }
    return status


@app.get("/api/auth/me")
def auth_me(request: Request) -> dict:
    return {"user": authenticated_user(request)}


@app.get("/api/account/integrations")
def account_integrations(request: Request) -> dict:
    if not public_mode_enabled():
        raise HTTPException(status_code=404, detail="Hosted account integrations are not enabled.")
    user = authenticated_user(request)
    try:
        quota = quota_client.status(quota_identity(user, request))
    except QuotaConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QuotaServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    douban = douban_adapter.status()
    return {
        "user": user,
        "deep_study": {
            "platform_enabled": hosted_deep_study_enabled(),
            "model": study_service.model,
            "quota": quota.as_dict(),
            "personal_session_key_supported": True,
        },
        "youtube": {
            "platform_enabled": youtube_video_adapter.status()["configured"],
            "personal_session_key_supported": True,
        },
        "douban": {
            "availability": "hosted" if douban["installed"] else "unavailable",
            "platform_enabled": douban["installed"],
            "personal_credentials_supported": False,
            "hosted_cookie_accepted": False,
            "connector_url": "https://github.com/moria97/douban-mcp",
        },
        "privacy": {
            "personal_credentials_stored": False,
            "credential_scope": "single_browser_tab",
        },
    }


@app.get("/api/library/status")
def library_status() -> dict:
    if public_mode_enabled():
        raise HTTPException(status_code=404, detail="The private library is not published.")
    result = library_catalogue.public_catalogue()
    result["index"] = library_index.status()
    return result


@app.get("/api/discovery/search")
def discovery_search(
    q: str = Query(min_length=1, max_length=160),
    year: int | None = Query(default=None, ge=1888, le=2100),
    director: str | None = Query(default=None, max_length=120),
) -> dict:
    try:
        return discovery_service.search(q, year=year, director=director)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/discovery/films/{film_id:path}/reception")
async def discovery_film_reception(film_id: str) -> dict:
    if cached := reception_cache.get(film_id):
        return cached

    try:
        film = discovery_service.detail(film_id)["film"]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    douban_status = douban_adapter.status()
    letterboxd_status = letterboxd_web_adapter.status()

    async def douban_score() -> dict | None:
        if not douban_status.get("installed"):
            return None
        try:
            return await douban_adapter.fetch_score(film)
        except CriticismError:
            return None

    async def letterboxd_score() -> dict | None:
        try:
            return await run_in_threadpool(letterboxd_web_adapter.fetch_score, film)
        except CriticismError:
            return None

    results = await asyncio.gather(douban_score(), letterboxd_score())
    summary = reception_summary([score for score in results if score])
    summary["providers"] = {
        "douban": douban_status,
        "letterboxd": letterboxd_status,
    }
    summary["awards"] = film.get("awards", [])[:3]
    if summary["scores"] or summary["awards"]:
        reception_cache[film_id] = summary
    return summary


@app.get("/api/discovery/films/{film_id:path}/related")
def discovery_film_related(
    film_id: str,
    limit: int = Query(default=12, ge=1, le=60),
    fast: bool = Query(default=True),
) -> dict:
    try:
        return discovery_service.related(film_id, limit=limit, fast=fast)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/discovery/films/{film_id:path}")
def discovery_film(film_id: str) -> dict:
    try:
        result = discovery_service.detail(film_id)
        if not public_mode_enabled():
            result["film"]["local_library"] = library_catalogue.public_catalogue()
            result["film"]["study_reading"] = library_index.retrieve_for_film(result["film"])
        cached_bundles = criticism_store.load_all(film_id)
        result["film"]["critical_research"] = {
            "providers": {
                "douban": douban_adapter.status(),
                "letterboxd": letterboxd_adapter.status(),
            },
            "bundles": {
                bundle.provider.casefold(): bundle.model_dump() for bundle in cached_bundles
            },
            "bundle": cached_bundles[0].model_dump() if cached_bundles else None,
        }
        result["film"]["video_sources"] = {
            "providers": video_service.status(),
            "bundle": (
                cached_video_bundle.model_dump()
                if (cached_video_bundle := video_store.load(film_id))
                else None
            ),
        }
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/videos")
def discovery_film_videos(film_id: str, request: Request) -> dict:
    try:
        youtube_key = personal_provider_key(request, "youtube")
        if public_mode_enabled() and youtube_key:
            authenticated_user(request)
        film = discovery_service.detail(film_id)["film"]
        bundle = video_service.search(film_id, film, youtube_api_key=youtube_key)
        return {"video_sources": bundle.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VideoSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/study")
def generate_film_study(
    film_id: str,
    study_request: FilmStudyRequest,
    request: Request,
) -> dict:
    public_mode = public_mode_enabled()
    quota = None
    personal_deepseek_key = personal_provider_key(request, "deepseek")
    if public_mode:
        user = authenticated_user(request)
        if not hosted_deep_study_boundary_enabled() or (
            not personal_deepseek_key and not hosted_deep_study_enabled()
        ):
            raise HTTPException(
                status_code=503,
                detail="Deep Study is not fully configured on this deployment yet.",
            )
    try:
        detail = discovery_service.detail(film_id)
        film = detail["film"]
        prepared = prepare_film_study(
            film_id,
            film,
            study_request.question,
            public_mode=public_mode,
        )
        if public_mode:
            quota = quota_client.reserve(quota_identity(user, request))
        result = {
            "film_id": film_id,
            "study": study_service.generate(
                film,
                prepared["reading"].get("passages", []),
                study_request.question,
                prepared["claims"],
                evidence_packet=prepared["packet"],
                api_key=personal_deepseek_key,
            ),
            "credential_source": (
                "personal_session" if personal_deepseek_key else "firstroll_platform"
            ),
        }
        if quota is not None:
            result["quota"] = quota.as_dict()
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except QuotaExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.quota.retry_after_seconds())},
        ) from exc
    except QuotaConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QuotaServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StudyGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/study/stream")
async def stream_film_study(
    film_id: str,
    study_request: FilmStudyRequest,
    request: Request,
) -> StreamingResponse:
    """Run Deep Study while streaming only allow-listed, public progress events."""

    user = authenticated_user(request)
    owner_id = account_owner_id(user)
    public_mode = public_mode_enabled()
    personal_deepseek_key = personal_provider_key(request, "deepseek")
    if public_mode and (
        not hosted_deep_study_boundary_enabled()
        or (not personal_deepseek_key and not hosted_deep_study_enabled())
    ):
        raise HTTPException(
            status_code=503,
            detail="Deep Study is not fully configured on this deployment yet.",
        )

    run_id = str(uuid4())
    study_run_store.create(run_id, owner_id)

    async def generate_events():
        progress = ResearchProgressStream(run_id)
        try:
            yield progress.frame("film_resolving")
            detail = await run_in_threadpool(discovery_service.detail, film_id)
            film = detail["film"]

            yield progress.frame("existing_evidence_loading")
            prepared = await run_in_threadpool(
                prepare_film_study,
                film_id,
                film,
                study_request.question,
                public_mode=public_mode,
            )
            packet = prepared["packet"]
            yield progress.frame(
                "evidence_assessed",
                counts={
                    "theory_sources": len(packet.theory_sources),
                    "critical_claims": len(packet.critical_claims),
                    "attributed_sources": len(packet.attributed_sources),
                },
            )

            quota = None
            if public_mode:
                quota = await run_in_threadpool(
                    quota_client.reserve,
                    quota_identity(user, request),
                )

            yield progress.frame("study_drafting")
            study = await run_in_threadpool(
                study_service.generate,
                film,
                prepared["reading"].get("passages", []),
                study_request.question,
                prepared["claims"],
                evidence_packet=packet,
                api_key=personal_deepseek_key,
            )
            payload = {
                "film_id": film_id,
                "study": study,
                "credential_source": (
                    "personal_session" if personal_deepseek_key else "firstroll_platform"
                ),
            }
            if quota is not None:
                payload["quota"] = quota.as_dict()
            study_run_store.complete(run_id, owner_id, payload)
            quality_passed = study.get("quality", {}).get("status") == "passed"
            yield progress.frame(
                "quality_checked",
                message_variant="passed" if quality_passed else "limited",
                counts={"sections": len(study.get("sections", []))},
            )
            yield progress.frame("run_completed")
        except asyncio.CancelledError:
            message = public_progress_message("run_failed", "disconnected")
            study_run_store.fail(run_id, owner_id, message)
            raise
        except LookupError:
            variant = "film_missing"
            message = public_progress_message("run_failed", variant)
            study_run_store.fail(run_id, owner_id, message)
            yield progress.frame("run_failed", message_variant=variant)
        except QuotaExceededError:
            variant = "quota_exhausted"
            message = public_progress_message("run_failed", variant)
            study_run_store.fail(run_id, owner_id, message)
            yield progress.frame("run_failed", message_variant=variant)
        except (QuotaConfigurationError, QuotaServiceError):
            variant = "quota_unavailable"
            message = public_progress_message("run_failed", variant)
            study_run_store.fail(run_id, owner_id, message)
            yield progress.frame("run_failed", message_variant=variant)
        except StudyGenerationError:
            variant = "invalid_study"
            message = public_progress_message("run_failed", variant)
            study_run_store.fail(run_id, owner_id, message)
            yield progress.frame("run_failed", message_variant=variant)
        except Exception:
            variant = "safe_stop"
            message = public_progress_message("run_failed", variant)
            study_run_store.fail(run_id, owner_id, message)
            yield progress.frame("run_failed", message_variant=variant)

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store, no-transform",
            "Vary": "Authorization, X-FirstRoll-DeepSeek-Key",
            "X-Content-Type-Options": "nosniff",
            "X-Accel-Buffering": "no",
            "X-FirstRoll-Run-ID": run_id,
        },
    )


@app.get("/api/research/runs/{run_id}")
def research_run_result(run_id: str, request: Request) -> JSONResponse:
    user = authenticated_user(request)
    try:
        stored = study_run_store.read(run_id, account_owner_id(user))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown research run.") from exc
    if stored.status == "running":
        raise HTTPException(status_code=409, detail="The research run is still in progress.")
    if stored.status == "failed":
        raise HTTPException(
            status_code=502,
            detail=stored.public_error or "The research run failed safely.",
        )
    if stored.result is None:
        raise HTTPException(status_code=502, detail="The research result is unavailable.")
    return JSONResponse(
        content=stored.result,
        headers={
            "Cache-Control": "no-store",
            "Vary": "Authorization",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/api/discovery/films/{film_id:path}/criticism/douban")
async def research_douban_criticism(film_id: str) -> dict:
    try:
        detail = discovery_service.detail(film_id)
        film = detail["film"]
        provider_id, provider_title, reviews = await douban_adapter.fetch_reviews(film)
        bundle = await run_in_threadpool(
            cache_raw_criticism,
            film_id,
            provider_id,
            provider_title,
            reviews,
            "Douban",
        )
        return {"critical_research": bundle.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CriticismError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/criticism/letterboxd")
async def research_letterboxd_criticism(film_id: str) -> dict:
    try:
        detail = discovery_service.detail(film_id)
        film = detail["film"]
        provider_id, provider_title, reviews = await run_in_threadpool(
            letterboxd_adapter.fetch_reviews, film
        )
        bundle = await run_in_threadpool(
            cache_raw_criticism,
            film_id,
            provider_id,
            provider_title,
            reviews,
            "Letterboxd",
        )
        return {"critical_research": bundle.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CriticismError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/criticism/letterboxd-web")
async def research_letterboxd_web_criticism(film_id: str) -> dict:
    try:
        detail = discovery_service.detail(film_id)
        film = detail["film"]
        provider_id, provider_title, reviews = await run_in_threadpool(
            letterboxd_web_adapter.fetch_reviews, film
        )
        bundle = await run_in_threadpool(
            cache_raw_criticism,
            film_id,
            provider_id,
            provider_title,
            reviews,
            "Letterboxd public web",
        )
        return {"critical_research": bundle.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CriticismError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/criticism/guardian-web")
async def research_guardian_web_criticism(film_id: str) -> dict:
    try:
        detail = discovery_service.detail(film_id)
        film = detail["film"]
        provider_id, provider_title, reviews = await run_in_threadpool(
            guardian_web_adapter.fetch_reviews, film
        )
        bundle = await run_in_threadpool(
            cache_raw_criticism,
            film_id,
            provider_id,
            provider_title,
            reviews,
            "The Guardian public web",
        )
        return {"critical_research": bundle.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CriticismError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/criticism/crossref")
async def research_crossref_criticism(film_id: str) -> dict:
    try:
        detail = discovery_service.detail(film_id)
        film = detail["film"]
        provider_id, provider_title, reviews = await run_in_threadpool(
            crossref_research_adapter.fetch_reviews, film
        )
        bundle = await run_in_threadpool(
            cache_raw_criticism,
            film_id,
            provider_id,
            provider_title,
            reviews,
            "Crossref scholarship",
        )
        return {"critical_research": bundle.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CriticismError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/criticism/{provider}/structure")
async def structure_cached_criticism(film_id: str, provider: str, request: Request) -> dict:
    require_local_settings_request(request)
    provider_name = CRITICISM_PROVIDERS.get(provider)
    if not provider_name:
        raise HTTPException(status_code=404, detail="Unknown criticism provider.")
    try:
        detail = discovery_service.detail(film_id)
        bundle = criticism_store.load(film_id, provider_name)
        if bundle is None or not bundle.reviews:
            raise HTTPException(
                status_code=409,
                detail="Fetch and cache attributed reviews before structuring them.",
            )
        claims = await run_in_threadpool(
            study_service.structure_reviews,
            detail["film"],
            bundle.reviews,
        )
        structured = bundle.model_copy(
            update={
                "claims": claims,
                "claim_status": "structured",
                "notice": (
                    f"DeepSeek structured {len(claims)} claims from attributed "
                    f"{provider_name} reviews. They remain secondary criticism, not verified "
                    "film observations or creator statements."
                ),
            }
        )
        await run_in_threadpool(criticism_store.save, structured)
        return {"critical_research": structured.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StudyGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/analyze")
async def analyze(
    video: UploadFile = File(...),
    scene_sensitivity: int = Form(6),
    shot_threshold: float = Form(0.35),
    include_object_detection: bool = Form(True),
    include_shot_scale: bool = Form(True),
):
    if not video_analysis_enabled():
        raise HTTPException(
            status_code=503,
            detail="Hosted video analysis is coming soon. Local analysis remains available.",
        )
    # Keep heavyweight computer-vision imports out of the film-discovery startup path.
    from app.backend.analysis_pipeline import analyze_video

    if not video.filename:
        raise HTTPException(status_code=400, detail="Missing video filename.")

    suffix = Path(video.filename).suffix or ".mp4"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
            temp_path = tf.name
            content = await video.read()
            tf.write(content)

        result = analyze_video(
            video_path=temp_path,
            original_filename=video.filename,
            scene_sensitivity=scene_sensitivity,
            shot_threshold=shot_threshold,
            include_object_detection=include_object_detection,
            include_shot_scale=include_shot_scale,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def run() -> None:
    import uvicorn

    uvicorn.run("app.backend.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
