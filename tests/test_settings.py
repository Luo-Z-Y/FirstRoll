import json
import os
import stat
import tempfile
from pathlib import Path

from app.backend.settings import LocalSettingsStore


def test_tmdb_is_available_as_the_primary_catalogue_connector() -> None:
    previous = os.environ.pop("TMDB_BEARER_TOKEN", None)
    try:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalSettingsStore(Path(directory) / "settings.json")
            tmdb = next(
                connector
                for connector in store.public_connectors()
                if connector["id"] == "tmdb"
            )

            assert tmdb["state"] == "available"
            assert tmdb["environment_key"] == "TMDB_BEARER_TOKEN"
            assert tmdb["configured"] is False
            assert tmdb["testable"] is True
    finally:
        if previous is not None:
            os.environ["TMDB_BEARER_TOKEN"] = previous


def test_deepseek_is_available_for_local_key_storage() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        deepseek = next(
            connector
            for connector in store.public_connectors()
            if connector["id"] == "deepseek"
        )

        assert deepseek["state"] == "available"
        assert deepseek["environment_key"] == "DEEPSEEK_API_KEY"
        assert deepseek["configured"] is False


def test_youtube_is_available_for_local_key_storage() -> None:
    previous = os.environ.pop("YOUTUBE_API_KEY", None)
    try:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalSettingsStore(Path(directory) / "settings.json")
            youtube = next(
                connector
                for connector in store.public_connectors()
                if connector["id"] == "youtube"
            )

            assert youtube["state"] == "available"
            assert youtube["environment_key"] == "YOUTUBE_API_KEY"
            assert youtube["configured"] is False
    finally:
        if previous is not None:
            os.environ["YOUTUBE_API_KEY"] = previous


def test_local_settings_store_masks_and_clears_secrets() -> None:
    previous = os.environ.pop("DOUBAN_COOKIE", None)
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private" / "settings.json"
            store = LocalSettingsStore(path)
            token = "test-token-that-must-not-be-returned-1234"

            store.set("douban_cookie", token)

            state = store.secret_state("douban")
            public = next(
                connector
                for connector in store.public_connectors()
                if connector["id"] == "douban"
            )
            raw = path.read_text(encoding="utf-8")
            assert state.configured is True
            assert state.source == "local_store"
            assert state.hint == "••••1234"
            assert public["credential_hint"] == "••••1234"
            assert token not in json.dumps(public)
            assert json.loads(raw)["douban_cookie"] == token
            assert stat.S_IMODE(path.stat().st_mode) == 0o600

            store.clear("douban_cookie")
            assert store.secret_state("douban").configured is False
    finally:
        if previous is not None:
            os.environ["DOUBAN_COOKIE"] = previous


def test_environment_secret_takes_precedence_without_being_exposed() -> None:
    previous = os.environ.get("DOUBAN_COOKIE")
    os.environ["DOUBAN_COOKIE"] = "environment-token-9876"
    try:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalSettingsStore(Path(directory) / "settings.json")
            store.set("douban_cookie", "stored-token-1234")

            state = store.secret_state("douban")

            assert state.source == "environment"
            assert state.hint == "••••9876"
            assert store.effective_secret("douban") == "environment-token-9876"
            assert "environment-token-9876" not in json.dumps(store.public_connectors())
    finally:
        if previous is None:
            os.environ.pop("DOUBAN_COOKIE", None)
        else:
            os.environ["DOUBAN_COOKIE"] = previous


def test_letterboxd_requires_two_write_only_credentials() -> None:
    previous_id = os.environ.pop("LETTERBOXD_CLIENT_ID", None)
    previous_secret = os.environ.pop("LETTERBOXD_CLIENT_SECRET", None)
    try:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalSettingsStore(Path(directory) / "settings.json")
            store.set("letterboxd_client_id", "client-123456")

            partial = next(
                connector
                for connector in store.public_connectors()
                if connector["id"] == "letterboxd"
            )
            assert partial["configured"] is False
            assert len(partial["credentials"]) == 2

            store.set("letterboxd_client_secret", "secret-987654")
            configured = next(
                connector
                for connector in store.public_connectors()
                if connector["id"] == "letterboxd"
            )
            public = json.dumps(configured)

            assert configured["configured"] is True
            assert "client-123456" not in public
            assert "secret-987654" not in public
            assert store.effective_credential("letterboxd", "client_id") == "client-123456"
            assert (
                store.effective_credential("letterboxd", "client_secret")
                == "secret-987654"
            )
    finally:
        if previous_id is not None:
            os.environ["LETTERBOXD_CLIENT_ID"] = previous_id
        if previous_secret is not None:
            os.environ["LETTERBOXD_CLIENT_SECRET"] = previous_secret
