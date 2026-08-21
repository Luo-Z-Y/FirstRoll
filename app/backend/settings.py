from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any


CONNECTORS: dict[str, dict[str, Any]] = {
    "tmdb": {
        "name": "TMDb catalogue",
        "secret_key": "tmdb_bearer_token",
        "environment_key": "TMDB_BEARER_TOKEN",
        "state": "available",
        "description": (
            "Primary official film catalogue for fast title matching, posters, credits and "
            "IMDb/Wikidata identity links. Wikidata remains the key-free fallback."
        ),
        "credential_label": "Read Access Token",
        "documentation_url": "https://developer.themoviedb.org/docs/authentication-application",
        "testable": True,
    },
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
    "letterboxd": {
        "name": "Letterboxd API",
        "credentials": [
            {
                "id": "client_id",
                "label": "Client ID",
                "secret_key": "letterboxd_client_id",
                "environment_key": "LETTERBOXD_CLIENT_ID",
            },
            {
                "id": "client_secret",
                "label": "Client Secret",
                "secret_key": "letterboxd_client_secret",
                "environment_key": "LETTERBOXD_CLIENT_SECRET",
            },
        ],
        "state": "available",
        "description": (
            "Official OAuth API access for attributed Letterboxd reviews. "
            "Requires credentials granted by Letterboxd."
        ),
        "credential_label": "OAuth credentials",
        "documentation_url": "https://api-docs.letterboxd.com/",
        "testable": True,
    },
    "youtube": {
        "name": "YouTube",
        "secret_key": "youtube_api_key",
        "environment_key": "YOUTUBE_API_KEY",
        "state": "available",
        "description": (
            "Official YouTube Data API search for public, embeddable film videos. "
            "Bilibili public search remains available without this key."
        ),
        "credential_label": "Data API key",
        "documentation_url": "https://developers.google.com/youtube/v3/getting-started",
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
        states = self.credential_states(connector_id)
        configured = bool(states) and all(state["configured"] for state in states)
        sources = {state["source"] for state in states if state["configured"]}
        source = next(iter(sources)) if len(sources) == 1 else "mixed" if sources else "none"
        hint = states[0]["hint"] if len(states) == 1 else f"{len(states)} fields" if configured else None
        return SecretState(configured, source, hint)

    def effective_secret(self, connector_id: str) -> str:
        credential = self.credential_definitions(connector_id)[0]
        return self._effective_credential(credential)

    def effective_credential(self, connector_id: str, credential_id: str) -> str:
        credential = next(
            (
                item
                for item in self.credential_definitions(connector_id)
                if item["id"] == credential_id
            ),
            None,
        )
        if credential is None:
            raise KeyError(f"Unknown credential {credential_id!r} for {connector_id!r}.")
        return self._effective_credential(credential)

    def credential_definitions(self, connector_id: str) -> list[dict[str, str]]:
        definition = CONNECTORS[connector_id]
        credentials = definition.get("credentials")
        if credentials:
            return [dict(item) for item in credentials]
        return [
            {
                "id": "value",
                "label": definition["credential_label"],
                "secret_key": definition["secret_key"],
                "environment_key": definition["environment_key"],
            }
        ]

    def credential_states(self, connector_id: str) -> list[dict[str, Any]]:
        states: list[dict[str, Any]] = []
        for credential in self.credential_definitions(connector_id):
            environment_value = os.getenv(credential["environment_key"], "").strip()
            stored_value = self.get(credential["secret_key"])
            value = environment_value or stored_value
            states.append(
                {
                    "id": credential["id"],
                    "label": credential["label"],
                    "configured": bool(value),
                    "source": "environment" if environment_value else "local_store" if stored_value else "none",
                    "hint": self._mask(value) if value else None,
                    "environment_key": credential["environment_key"],
                }
            )
        return states

    def public_connectors(self) -> list[dict[str, Any]]:
        connectors: list[dict[str, Any]] = []
        for connector_id, definition in CONNECTORS.items():
            secret = self.secret_state(connector_id)
            credentials = self.credential_states(connector_id)
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
                    "environment_key": ", ".join(
                        credential["environment_key"]
                        for credential in self.credential_definitions(connector_id)
                    ),
                    "credentials": credentials,
                }
            )
        return connectors

    def _effective_credential(self, credential: dict[str, str]) -> str:
        return os.getenv(credential["environment_key"], "").strip() or self.get(
            credential["secret_key"]
        )

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
