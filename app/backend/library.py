from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from threading import RLock
from typing import Any, BinaryIO


SUPPORTED_SUFFIXES = {".pdf", ".epub", ".md", ".txt"}
MAX_DOCUMENT_BYTES = 500 * 1024 * 1024


class LocalLibraryCatalogue:
    """Metadata-only view of private study documents on this device."""

    def __init__(self, root: Path | None = None, manifest: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        private_root = project_root / ".firstroll"
        self.root = root or Path(os.getenv("FIRSTROLL_LIBRARY_PATH", private_root / "library"))
        self.manifest = manifest or Path(
            os.getenv("FIRSTROLL_LIBRARY_MANIFEST", private_root / "library.json")
        )
        self._lock = RLock()

    def public_catalogue(self) -> dict[str, Any]:
        documents = [self._public_document(path) for path in self._document_paths()]
        documents.sort(key=lambda item: item["title"].casefold())
        return {
            "state": "ready" if documents else "empty",
            "document_count": len(documents),
            "documents": documents,
            "privacy": "File paths and contents remain local and are not returned by the API.",
        }

    def index_records(self) -> list[dict[str, Any]]:
        """Return local paths plus public metadata for the private index builder."""
        return [{"path": path, **self._public_document(path)} for path in self._document_paths()]

    def add_document(self, filename: str, source: BinaryIO) -> dict[str, Any]:
        """Copy an uploaded document into FirstRoll's managed private library."""
        safe_name = self._safe_filename(filename)
        suffix = Path(safe_name).suffix.casefold()
        if suffix not in SUPPORTED_SUFFIXES:
            formats = ", ".join(sorted(item.lstrip(".").upper() for item in SUPPORTED_SUFFIXES))
            raise ValueError(f"Unsupported document format. Choose {formats}.")

        with self._lock:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                os.chmod(self.root, 0o700)
            except OSError:
                pass
            destination = self._available_destination(safe_name)
            temporary = destination.with_name(f".{destination.name}.uploading")
            written = 0
            try:
                with temporary.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        if written > MAX_DOCUMENT_BYTES:
                            raise ValueError("The document exceeds the 500 MB local upload limit.")
                        output.write(chunk)
                if written == 0:
                    raise ValueError("The selected document is empty.")
                os.chmod(temporary, 0o600)
                temporary.replace(destination)
                self._restore_document(destination)
            except Exception:
                if temporary.exists():
                    temporary.unlink()
                raise
        return self._public_document(destination)

    def remove_document(self, document_id: str) -> dict[str, Any]:
        """Remove a document from the catalogue without deleting its source file."""
        with self._lock:
            path = next(
                (
                    candidate
                    for candidate in self._document_paths()
                    if self._document_id(candidate) == document_id
                ),
                None,
            )
            if path is None:
                raise LookupError("The library document was not found.")
            document = self._public_document(path)
            payload = self._read_manifest(strict=True)
            target = str(path.resolve())
            documents = payload.get("documents", [])
            if not isinstance(documents, list):
                documents = []
            payload["documents"] = [
                raw_path
                for raw_path in documents
                if not isinstance(raw_path, str)
                or self._resolved_manifest_path(raw_path) != target
            ]
            if self._is_managed(path):
                excluded = payload.get("excluded_documents", [])
                if not isinstance(excluded, list):
                    excluded = []
                payload["excluded_documents"] = list(dict.fromkeys([*excluded, target]))
            self._write_manifest(payload)
        return document

    def _document_paths(self) -> list[Path]:
        paths: list[Path] = []
        payload = self._read_manifest()
        excluded = {
            self._resolved_manifest_path(raw_path)
            for raw_path in payload.get("excluded_documents", [])
            if isinstance(raw_path, str)
        }
        if self.root.exists():
            paths.extend(
                path
                for path in self.root.rglob("*")
                if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES
            )
        for raw_path in payload.get("documents", []) if isinstance(payload, dict) else []:
            if isinstance(raw_path, str):
                path = Path(raw_path).expanduser()
                if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES:
                    paths.append(path)

        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            resolved = str(path.resolve())
            if resolved not in seen and resolved not in excluded:
                seen.add(resolved)
                unique.append(path)
        return unique

    def _public_document(self, path: Path) -> dict[str, Any]:
        title = self._clean_title(path.stem)
        return {
            "id": self._document_id(path),
            "title": title,
            "format": path.suffix.lstrip(".").upper(),
            "size_mb": round(path.stat().st_size / 1_048_576, 1),
            "topics": self._topics(title),
            "scope": "general_reference",
            "source": "managed_library" if self._is_managed(path) else "registered_path",
        }

    def _read_manifest(self, strict: bool = False) -> dict[str, Any]:
        if not self.manifest.exists():
            return {}
        try:
            payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if strict:
                raise RuntimeError("The private library manifest could not be read.") from exc
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_manifest(self, payload: dict[str, Any]) -> None:
        self.manifest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            os.chmod(self.manifest.parent, 0o700)
        except OSError:
            pass
        temporary = self.manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.manifest)
        os.chmod(self.manifest, 0o600)

    def _restore_document(self, path: Path) -> None:
        payload = self._read_manifest(strict=True)
        target = str(path.resolve())
        excluded = payload.get("excluded_documents", [])
        if not isinstance(excluded, list):
            return
        retained = [
            item
            for item in excluded
            if not isinstance(item, str) or self._resolved_manifest_path(item) != target
        ]
        if retained != excluded:
            payload["excluded_documents"] = retained
            self._write_manifest(payload)

    def _available_destination(self, filename: str) -> Path:
        stem = Path(filename).stem
        suffix = Path(filename).suffix.casefold()
        destination = self.root / f"{stem}{suffix}"
        number = 2
        while destination.exists() or destination.with_name(f".{destination.name}.uploading").exists():
            destination = self.root / f"{stem} ({number}){suffix}"
            number += 1
        return destination

    def _is_managed(self, path: Path) -> bool:
        return path.resolve().is_relative_to(self.root.resolve())

    @staticmethod
    def _safe_filename(filename: str) -> str:
        candidate = Path((filename or "").replace("\\", "/")).name
        stem = re.sub(r"[\x00-\x1f/:]+", "_", Path(candidate).stem).strip(" .")
        suffix = Path(candidate).suffix.casefold()
        if not stem or not suffix:
            raise ValueError("Choose a named document with a supported file extension.")
        return f"{stem}{suffix}"

    @staticmethod
    def _resolved_manifest_path(raw_path: str) -> str:
        return str(Path(raw_path).expanduser().resolve())

    @staticmethod
    def _document_id(path: Path) -> str:
        return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _clean_title(value: str) -> str:
        cleaned = re.sub(r"\s*\(z-lib\.org\)\s*$", "", value, flags=re.IGNORECASE)
        return " ".join(cleaned.split())

    @staticmethod
    def _topics(title: str) -> list[str]:
        lowered = title.casefold()
        rules = (
            (("shot by shot", "镜头设计"), ["shot design", "storyboarding", "staging"]),
            (("cinematic motion",), ["camera movement", "blocking", "staging"]),
            (("sight, sound, motion",), ["media aesthetics", "composition", "sound"]),
            (("film art",), ["film form", "style", "narrative"]),
            (("movie history",), ["film history", "industry", "movements"]),
            (("elements of style",), ["research writing", "prose"]),
        )
        for needles, topics in rules:
            if any(needle in lowered for needle in needles):
                return topics
        return ["film studies"]
