import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, SecretStr
from starlette.concurrency import run_in_threadpool

from app.backend.criticism import (
    CriticismError,
    CriticismStore,
    DoubanMcpAdapter,
    build_bundle,
)
from app.backend.discovery import DiscoveryService
from app.backend.evidence import EvidencePacket
from app.backend.library import LocalLibraryCatalogue
from app.backend.library_index import LocalLibraryIndex
from app.backend.settings import CONNECTORS, LocalSettingsStore
from app.backend.study_service import DeepSeekStudyService, StudyGenerationError

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
criticism_store = CriticismStore()
web_directory = Path(__file__).resolve().parents[1] / "web"
app.mount("/assets", StaticFiles(directory=web_directory), name="web-assets")


class ConnectorSecretUpdate(BaseModel):
    value: SecretStr


class FilmStudyRequest(BaseModel):
    question: str | None = None


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


@app.put("/api/settings/connectors/{connector_id}")
def save_connector_secret(
    connector_id: str,
    update: ConnectorSecretUpdate,
    request: Request,
) -> dict:
    require_local_settings_request(request)
    if connector_id not in CONNECTORS:
        raise HTTPException(status_code=404, detail="Unknown connector.")
    current = settings_store.secret_state(connector_id)
    if current.source == "environment":
        raise HTTPException(
            status_code=409,
            detail=f"This credential is controlled by {CONNECTORS[connector_id]['environment_key']}.",
        )
    try:
        settings_store.set(CONNECTORS[connector_id]["secret_key"], update.value.get_secret_value())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connector": public_connector(connector_id)}


@app.delete("/api/settings/connectors/{connector_id}")
def clear_connector_secret(connector_id: str, request: Request) -> dict:
    require_local_settings_request(request)
    if connector_id not in CONNECTORS:
        raise HTTPException(status_code=404, detail="Unknown connector.")
    current = settings_store.secret_state(connector_id)
    if current.source == "environment":
        raise HTTPException(
            status_code=409,
            detail=f"Unset {CONNECTORS[connector_id]['environment_key']} in the backend environment.",
        )
    settings_store.clear(CONNECTORS[connector_id]["secret_key"])
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
        raise HTTPException(status_code=501, detail="This optional connector is not implemented yet.")
    except (StudyGenerationError, CriticismError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/contract")
def contract() -> dict:
    return {
        "endpoints": [
            "GET /settings",
            "GET /api/settings",
            "PUT /api/settings/connectors/{connector_id}",
            "GET /api/discovery/status",
            "GET /api/discovery/search",
            "GET /api/discovery/films/{film_id}",
            "POST /api/discovery/films/{film_id}/study",
            "POST /api/discovery/films/{film_id}/criticism/douban",
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
        cached_criticism = criticism_store.load(film_id)
        result["film"]["critical_research"] = {
            "providers": {"douban": douban_adapter.status()},
            "bundle": cached_criticism.model_dump() if cached_criticism else None,
        }
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/discovery/films/{film_id:path}/study")
def generate_film_study(film_id: str, study_request: FilmStudyRequest) -> dict:
    try:
        detail = discovery_service.detail(film_id)
        film = detail["film"]
        critical_bundle = criticism_store.load(film_id)
        claims = critical_bundle.claims if critical_bundle else []
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
        claims = await run_in_threadpool(study_service.structure_reviews, film, reviews)
        bundle = build_bundle(film_id, provider_id, provider_title, reviews, claims)
        await run_in_threadpool(criticism_store.save, bundle)
        return {"critical_research": bundle.model_dump()}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CriticismError, StudyGenerationError) as exc:
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
