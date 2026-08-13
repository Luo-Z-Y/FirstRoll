import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
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
from app.backend.discovery import DiscoveryService
from app.backend.evidence import EvidencePacket
from app.backend.library import MAX_DOCUMENT_BYTES, SUPPORTED_SUFFIXES, LocalLibraryCatalogue
from app.backend.library_index import LocalLibraryIndex
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
web_directory = Path(__file__).resolve().parents[1] / "web"
app.mount("/assets", StaticFiles(directory=web_directory), name="web-assets")


class ConnectorSecretUpdate(BaseModel):
    value: SecretStr | None = None
    credentials: dict[str, SecretStr] | None = None


class FilmStudyRequest(BaseModel):
    question: str | None = None


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
            "Attributed reviews were refreshed and cached locally. Previously validated "
            "claims remain visible while DeepSeek prepares a replacement."
            if has_preserved_claims
            else "Attributed reviews were fetched and cached locally. DeepSeek structuring is pending."
        ),
    )
    criticism_store.save(bundle)
    return bundle


def require_local_settings_request(request: Request) -> None:
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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=FileResponse)
def web_app() -> FileResponse:
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
            "GET /api/discovery/search",
            "GET /api/discovery/films/{film_id}",
            "POST /api/discovery/films/{film_id}/videos",
            "POST /api/discovery/films/{film_id}/study",
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
    local_library = library_catalogue.public_catalogue()
    local_library["index"] = library_index.status()
    status["local_library"] = local_library
    return status


@app.get("/api/library/status")
def library_status() -> dict:
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


@app.get("/api/discovery/films/{film_id:path}")
def discovery_film(film_id: str) -> dict:
    try:
        result = discovery_service.detail(film_id)
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
def discovery_film_videos(film_id: str) -> dict:
    try:
        film = discovery_service.detail(film_id)["film"]
        bundle = video_service.search(film_id, film)
        return {"video_sources": bundle.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VideoSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/study")
def generate_film_study(film_id: str, study_request: FilmStudyRequest) -> dict:
    try:
        detail = discovery_service.detail(film_id)
        film = detail["film"]
        critical_bundles = criticism_store.load_all(film_id)
        claims = [claim for bundle in critical_bundles for claim in bundle.claims]
        reading = library_index.retrieve_for_film(
            film,
            focus=study_request.question,
            critical_claims=claims,
            limit=10,
        )
        packet = EvidencePacket.from_retrieval(
            film,
            reading,
            study_request.question,
            claims,
        )
        return {
            "film_id": film_id,
            "study": study_service.generate(
                film,
                reading.get("passages", []),
                study_request.question,
                claims,
                evidence_packet=packet,
            ),
        }
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StudyGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
async def research_letterboxd_web_criticism(film_id: str, request: Request) -> dict:
    require_local_settings_request(request)
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
async def research_guardian_web_criticism(film_id: str, request: Request) -> dict:
    require_local_settings_request(request)
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
