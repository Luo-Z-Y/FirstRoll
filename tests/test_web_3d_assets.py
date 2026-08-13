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
    assert (WEB / "vendor" / "three" / "LICENSE").is_file()


def test_single_wall_shelf_caps_rows_and_fills_sparse_director_results() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    runtime = (WEB / "closet3d.js").read_text(encoding="utf-8")
    blender_builder = (ROOT / "tools" / "build_closet_blender.py").read_text(
        encoding="utf-8"
    )

    assert ".slice(0, 15)" in app
    assert "complete director row" in app
    assert app.count('wall: "back"') == 3
    assert 'wall: "left"' not in app
    assert 'wall: "right"' not in app
    assert 'collection.shelf === "lower" ? 12 : 10' in runtime
    assert "middle: 2.27" in runtime
    assert "middle: 1.91" in runtime
    assert "2.4, 0.10" in runtime
    assert "placeholder: true" in runtime
    assert "selectableCase: !film.placeholder" in runtime
    assert "const gap = 0.06" in runtime
    assert "const depth = 0.13" in runtime
    assert "amount * 0.13" in runtime
    assert "wireframe: true" not in runtime
    assert "if shelf_index in (1, 2, 3)" in blender_builder
    assert 'build_side_shelves("left", materials)' not in blender_builder
    assert 'build_side_shelves("right", materials)' not in blender_builder
    assert "rotation_z=0.0" in blender_builder
    assert "random.uniform(0.11, 0.15)" in blender_builder
