"""The organised developer entry points keep their paths and preview boundary."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("port", [None, "4199"])
def test_preview_launcher_uses_repo_root_and_explicit_frontend_flags(tmp_path, port):
    # Replace only the executable boundary: do not start a server, install packages
    # or load private configuration while checking the launcher contract.
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "print(json.dumps({'cwd': os.getcwd(), 'args': sys.argv[1:], "
        "'flags': {key: os.environ.get(key) for key in "
        "['FIRSTROLL_PUBLIC_MODE', 'FIRSTROLL_SERVE_HOSTED_FRONTEND', "
        "'FIRSTROLL_VIDEO_ANALYSIS_ENABLED', 'FIRSTROLL_BUILD_CHANNEL']}}))\n"
    )
    fake_uv.chmod(0o700)
    env = {"PATH": f"{tmp_path}{os.pathsep}{os.defpath}"}
    if port:
        env["PORT"] = port
    result = subprocess.run(
        ["sh", str(ROOT / "tools/frontend/preview.sh")],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=True,
    )
    recorded = json.loads(result.stdout)
    assert Path(recorded["cwd"]).resolve() == ROOT
    assert recorded["args"] == [
        "run", "uvicorn", "app.backend.main:app", "--host", "127.0.0.1",
        "--port", port or "4173",
    ]
    assert recorded["flags"] == {
        "FIRSTROLL_PUBLIC_MODE": "true",
        "FIRSTROLL_SERVE_HOSTED_FRONTEND": "true",
        "FIRSTROLL_VIDEO_ANALYSIS_ENABLED": "false",
        "FIRSTROLL_BUILD_CHANNEL": "local",
    }


def test_preview_builds_before_serving_and_docker_includes_nested_compiler():
    scripts = json.loads((ROOT / "package.json").read_text())["scripts"]
    assert scripts["preview"] == "npm run build:local && sh tools/frontend/preview.sh"
    assert scripts["build:local"] == "node tools/frontend/build.cjs --local"
    ignore = (ROOT / ".dockerignore").read_text()
    assert "!tools\n!tools/frontend\n!tools/frontend/build.cjs\n" in ignore
    assert "COPY tools/frontend/build.cjs ./tools/frontend/build.cjs" in (
        ROOT / "Dockerfile"
    ).read_text()
