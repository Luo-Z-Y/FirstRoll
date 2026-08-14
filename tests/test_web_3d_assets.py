from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def test_blender_closet_glb_is_packaged_as_a_web_asset() -> None:
    model = WEB / "models" / "firstroll-closet.glb"

    assert model.is_file()
    assert model.stat().st_size > 100_000
    assert model.read_bytes()[:4] == b"glTF"


def test_webgl_runtime_is_local_and_loaded_by_the_discovery_page() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    runtime = (WEB / "closet3d.js").read_text(encoding="utf-8")

    assert 'type="importmap"' in index
    assert 'src="/assets/closet3d.js' in index
    assert 'from "three"' in runtime
    assert "firstroll-closet.glb" in runtime
    assert "firstroll:select-film" in runtime
    assert "waitForShelfReveal" in runtime
    assert 'textContent = "Shelf ready"' in runtime
    assert "window.setTimeout(resolve, 540)" in runtime
    assert "window.FirstRollCloset?.unmount()" in (WEB / "app.js").read_text(
        encoding="utf-8"
    )
    assert (WEB / "vendor" / "three" / "LICENSE").is_file()


def test_single_wall_shelf_uses_five_rows_of_real_films() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    runtime = (WEB / "closet3d.js").read_text(encoding="utf-8")
    discovery = (ROOT / "app" / "backend" / "discovery.py").read_text(encoding="utf-8")
    blender_builder = (ROOT / "tools" / "build_closet_blender.py").read_text(
        encoding="utf-8"
    )

    assert "const rowSize = 10" in app
    assert "displayableFilms" in app
    assert "related?limit=60" in app
    assert "usedFilmIds" in app
    assert "usedFilmEditions" in app
    assert "shelfFilmIdentity" in app
    assert "LIMIT 168" in discovery
    assert "candidate_ids[:168]" in discovery
    assert "RELATED_POSTER_FALLBACK_LIMIT = 8" in discovery
    assert "fetchRelatedFilmsWithRetry" in app
    assert "hydrateFilmShelf" in app
    assert "showFilmShelfError" in app
    assert "Not enough distinct verified films" in app
    assert "renderFilmArchive(primary, [], uniqueFilms(nearby" not in app
    assert "!/^Q\\d+$/i.test(text)" in app
    assert "closet-help" not in app
    assert app.count('wall: "back"') == 5
    assert 'wall: "left"' not in app
    assert 'wall: "right"' not in app
    assert "const SHELF_ROW_SIZE = 10" in runtime
    assert "DEFAULT_CAMERA_POSITION = new THREE.Vector3(0, 1.65, 0.12)" in runtime
    assert runtime.count("this.camera.position.copy(DEFAULT_CAMERA_POSITION)") == 2
    assert "this.camera.getWorldDirection(forward)" in runtime
    assert "crossVectors(forward, this.camera.up)" in runtime
    assert "const { forward } = this.movementBasis()" in runtime
    assert "const { right } = this.movementBasis()" in runtime
    assert "placeholder: true" not in runtime
    assert "FirstRoll Archive" not in runtime
    assert "selectableCase: true" in runtime
    assert "bottom: 0.61" in runtime
    assert "top: 3.93" in runtime
    assert "middle: 2.27" in runtime
    assert "middle: 1.91" in runtime
    assert "top: 3.57" in runtime
    assert "2.4, 0.12" in runtime
    assert "const gap = 0.035" in runtime
    assert "const depth = 0.13" in runtime
    assert "amount * 0.13" in runtime
    assert "wireframe: true" not in runtime
    assert "firstroll_ambient_case" not in runtime
    assert "updateCaseCaption" in runtime
    assert "uniqueFilmCount" in runtime
    assert "canvas.height = 96" in runtime
    assert "faceWidth / faceHeight" in runtime
    assert "loadPosterTexture" in runtime
    assert 'textContent = "Loading film artwork"' in runtime
    assert 'setCrossOrigin("anonymous")' in runtime
    assert "texture.repeat.set(0.46, 1)" in runtime
    assert "All five rows remain empty in the asset" in blender_builder
    assert "firstroll_ambient_case" not in blender_builder
    assert 'build_side_shelves("left", materials)' not in blender_builder
    assert 'build_side_shelves("right", materials)' not in blender_builder
