from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


SUPPORTED_SUFFIXES = {".pdf", ".epub", ".md", ".txt"}


class LocalLibraryCatalogue:
    """Metadata-only view of private study documents on this device."""

    def __init__(self, root: Path | None = None, manifest: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        private_root = project_root / ".firstroll"
        self.root = root or Path(os.getenv("FIRSTROLL_LIBRARY_PATH", private_root / "library"))
        self.manifest = manifest or Path(
            os.getenv("FIRSTROLL_LIBRARY_MANIFEST", private_root / "library.json")
        )

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

    def _document_paths(self) -> list[Path]:
        paths: list[Path] = []
        if self.root.exists():
            paths.extend(
                path
                for path in self.root.rglob("*")
                if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES
            )
        if self.manifest.exists():
            try:
                payload = json.loads(self.manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            for raw_path in payload.get("documents", []) if isinstance(payload, dict) else []:
                path = Path(raw_path).expanduser()
                if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES:
                    paths.append(path)

        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            resolved = str(path.resolve())
            if resolved not in seen:
                seen.add(resolved)
                unique.append(path)
        return unique

    def _public_document(self, path: Path) -> dict[str, Any]:
        title = self._clean_title(path.stem)
        return {
            "id": hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12],
            "title": title,
            "format": path.suffix.lstrip(".").upper(),
            "size_mb": round(path.stat().st_size / 1_048_576, 1),
            "topics": self._topics(title),
            "scope": "general_reference",
        }

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
