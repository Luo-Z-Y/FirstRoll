"""Local serving and container/build contracts for the modular frontend."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.backend import main


ROOT = Path(__file__).resolve().parents[1]


def test_missing_local_bundle_has_an_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "web_directory", tmp_path)
    response = TestClient(main.app).get("/assets/app.js")
    assert response.status_code == 503
    assert "npm run build:local" in response.json()["detail"]


def test_local_bundle_is_compiled_javascript_not_the_raw_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "web_directory", tmp_path)
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "app.js").write_text("/* compiled fixture */", encoding="utf-8")
    (tmp_path / "app.js").write_text("import './src/main.ts';", encoding="utf-8")
    response = TestClient(main.app).get("/assets/app.js?v=test")
    assert response.status_code == 200
    assert response.text == "/* compiled fixture */"
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"


def test_container_and_hosted_builds_compile_the_same_source():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    hosted = (ROOT / "tools/build_web.sh").read_text(encoding="utf-8")
    assert "RUN npm run build:local" in dockerfile
    assert "COPY --from=frontend-builder /web/app/web/generated/app.js" in dockerfile
    for name in ("package.json", "package-lock.json", "tsconfig.json", "tools/frontend-build.cjs"):
        assert f"!{name}\n" in ignore
    assert 'node "$project_root/tools/frontend-build.cjs" "$output_dir/assets/app.js"' in hosted
