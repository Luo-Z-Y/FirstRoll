"""Source-smoke fixtures supplement, but do not replace, executable frontend tests."""

from pathlib import Path

import pytest


@pytest.fixture
def application_source() -> str:
    """Follow the modular source tree rather than assuming one monolithic app.js."""
    web = Path(__file__).resolve().parents[1] / "app" / "web"
    files = [
        web / "app.ts",
        *sorted(path for path in (web / "src").rglob("*") if path.suffix in {".js", ".ts"}),
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)
