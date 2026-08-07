from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any


CONNECTORS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "name": "DeepSeek",
        "secret_key": "deepseek_api_key",
        "environment_key": "DEEPSEEK_API_KEY",
        "state": "available",
        "description": (
            "LLM provider for evidence-grounded film synthesis. "
            "FirstRoll sends selected passages only when you generate a Deep Study."
        ),
        "credential_label": "API Key",
        "documentation_url": "https://api-docs.deepseek.com/",
        "testable": True,
    },
    "douban": {
        "name": "Douban",
        "secret_key": "douban_cookie",
        "environment_key": "DOUBAN_COOKIE",
        "state": "available",
        "description": (
            "Optional Chinese-language reviews through an unofficial local MCP server. "
            "Not required for film identity search."
        ),
        "credential_label": "Cookie",
        "documentation_url": "https://lobehub.com/mcp/moria97-douban-mcp",
        "testable": True,
    },
    "nyt": {
        "name": "The New York Times",
        "secret_key": "nyt_api_key",
        "environment_key": "NYT_API_KEY",
        "state": "planned",
        "description": "Attributed professional film reviews from New York Times critics.",
        "credential_label": "API Key",
        "documentation_url": "https://developer.nytimes.com/docs/movie-reviews-api/1/overview",
        "testable": False,
    },
    "guardian": {
        "name": "The Guardian",
        "secret_key": "guardian_api_key",
        "environment_key": "GUARDIAN_API_KEY",
        "state": "planned",
        "description": "Professional criticism and filmmaker interviews from the Content API.",
        "credential_label": "API Key",
        "documentation_url": "https://open-platform.theguardian.com/documentation/",
        "testable": False,
    },
}


@dataclass(frozen=True)
class SecretState:
    configured: bool
    source: str
    hint: str | None


class LocalSettingsStore:
    """Small local-only secret store for the FirstRoll development backend."""

    def __init__(self, path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        configured_path = os.getenv("FIRSTROLL_SETTINGS_PATH")
        if path is not None:
            self.path = path
        elif configured_path:
            self.path = Path(configured_path)
        else:
            self.path = project_root / ".firstroll" / "settings.json"
        self._lock = RLock()

    def get(self, secret_key: str) -> str:
        with self._lock:
            value = self._read().get(secret_key, "")
        return value if isinstance(value, str) else ""

    def set(self, secret_key: str, value: str) -> None:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Credential cannot be empty. Use Clear to remove it.")
        with self._lock:
            settings = self._read()
            settings[secret_key] = cleaned
            self._write(settings)

    def clear(self, secret_key: str) -> None:
        with self._lock:
            settings = self._read()
            if secret_key in settings:
                del settings[secret_key]
                self._write(settings)

    def secret_state(self, connector_id: str) -> SecretState:
        definition = CONNECTORS[connector_id]
        environment_value = os.getenv(definition["environment_key"], "").strip()
        if environment_value:
            return SecretState(True, "environment", self._mask(environment_value))
        stored_value = self.get(definition["secret_key"])
        if stored_value:
            return SecretState(True, "local_store", self._mask(stored_value))
        return SecretState(False, "none", None)

    def effective_secret(self, connector_id: str) -> str:
        definition = CONNECTORS[connector_id]
        return os.getenv(definition["environment_key"], "").strip() or self.get(
            definition["secret_key"]
        )

    def public_connectors(self) -> list[dict[str, Any]]:
        connectors: list[dict[str, Any]] = []
        for connector_id, definition in CONNECTORS.items():
            secret = self.secret_state(connector_id)
            connectors.append(
                {
                    "id": connector_id,
                    "name": definition["name"],
                    "state": definition["state"],
                    "description": definition["description"],
                    "credential_label": definition["credential_label"],
                    "documentation_url": definition["documentation_url"],
                    "testable": definition["testable"],
                    "configured": secret.configured,
                    "credential_source": secret.source,
                    "credential_hint": secret.hint,
                    "environment_key": definition["environment_key"],
                }
            )
        return connectors

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("The local FirstRoll settings file could not be read.") from exc
        return payload if isinstance(payload, dict) else {}

    def _write(self, settings: dict[str, Any]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(settings, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(self.path)
        os.chmod(self.path, 0o600)

    @staticmethod
    def _mask(value: str) -> str:
        if len(value) <= 4:
            return "••••"
        return f"••••{value[-4:]}"
