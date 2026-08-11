from io import BytesIO
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend import main
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


def test_library_adds_and_removes_documents_without_deleting_sources() -> None:
    with tempfile.TemporaryDirectory() as directory:
        private = Path(directory)
        external = private / "Existing Film Book.pdf"
        external.write_bytes(b"existing private book")
        manifest = private / "library.json"
        manifest.write_text(json.dumps({"documents": [str(external)]}), encoding="utf-8")
        catalogue = LocalLibraryCatalogue(root=private / "managed", manifest=manifest)

        added = catalogue.add_document("Uploaded Notes.MD", BytesIO(b"private notes"))
        ready = catalogue.public_catalogue()

        assert ready["document_count"] == 2
        assert added["format"] == "MD"
        assert added["source"] == "managed_library"
        assert str(external) not in json.dumps(ready)

        external_id = next(
            document["id"]
            for document in ready["documents"]
            if document["source"] == "registered_path"
        )
        catalogue.remove_document(external_id)
        catalogue.remove_document(added["id"])

        assert catalogue.public_catalogue()["document_count"] == 0
        assert external.exists()
        assert next((private / "managed").glob("*.md")).exists()


def test_library_rejects_unsupported_and_empty_uploads() -> None:
    with tempfile.TemporaryDirectory() as directory:
        catalogue = LocalLibraryCatalogue(
            root=Path(directory) / "managed",
            manifest=Path(directory) / "library.json",
        )

        for filename, content, message in (
            ("notes.docx", b"content", "Unsupported document format"),
            ("notes.pdf", b"", "selected document is empty"),
        ):
            try:
                catalogue.add_document(filename, BytesIO(content))
            except ValueError as exc:
                assert message in str(exc)
            else:
                raise AssertionError(f"{filename} should have been rejected")


def test_settings_library_api_manages_private_catalogue(monkeypatch) -> None:
    class StubIndex:
        def __init__(self) -> None:
            self.document_count = 0

        def status(self) -> dict:
            return {
                "state": "ready",
                "document_count": self.document_count,
                "chunk_count": 0,
            }

        def build(self, catalogue: LocalLibraryCatalogue) -> dict:
            self.document_count = catalogue.public_catalogue()["document_count"]
            return self.status()

    with tempfile.TemporaryDirectory() as directory:
        catalogue = LocalLibraryCatalogue(
            root=Path(directory) / "managed",
            manifest=Path(directory) / "library.json",
        )
        index = StubIndex()
        monkeypatch.setattr(main, "library_catalogue", catalogue)
        monkeypatch.setattr(main, "library_index", index)
        client = TestClient(main.app)
        headers = {"X-FirstRoll-Settings": "local"}

        response = client.post(
            "/api/settings/library",
            headers=headers,
            files={"document": ("Film Form.pdf", b"private book", "application/pdf")},
        )
        assert response.status_code == 200
        document = response.json()["document"]
        assert response.json()["library"]["index_needs_rebuild"] is True

        rebuilt = client.post("/api/settings/library/rebuild", headers=headers)
        assert rebuilt.status_code == 200
        assert rebuilt.json()["index_needs_rebuild"] is False

        removed = client.delete(
            f"/api/settings/library/{document['id']}",
            headers=headers,
        )
        assert removed.status_code == 200
        assert removed.json()["library"]["document_count"] == 0
