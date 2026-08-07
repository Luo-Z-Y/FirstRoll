import json
import os
import stat
import tempfile
from pathlib import Path

from app.backend.settings import LocalSettingsStore


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
