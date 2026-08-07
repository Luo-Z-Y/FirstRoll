import json
import tempfile
from pathlib import Path

from app.backend.library import LocalLibraryCatalogue


def test_private_library_returns_metadata_without_file_paths() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        document = root / "Film Art An Introduction (z-lib.org).pdf"
        document.write_bytes(b"private research content")
        manifest = root / "library.json"
        manifest.write_text(json.dumps({"documents": [str(document)]}), encoding="utf-8")

        result = LocalLibraryCatalogue(root=root / "empty", manifest=manifest).public_catalogue()

        assert result["state"] == "ready"
        assert result["document_count"] == 1
        assert result["documents"][0]["title"] == "Film Art An Introduction"
        assert "film form" in result["documents"][0]["topics"]
        assert str(document) not in json.dumps(result)
