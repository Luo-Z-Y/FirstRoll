"""Shared, dependency-free release primitives for the VPS release receipt.

Build artefacts are data, never deployment scripts. The deploy job fetches this module
and tools/release/vps.py from the exact CI-approved Git commit before it obtains the
production SSH key. A receipt hash detects changes; it is not an independent signature
or attestation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


SCHEMA = 1
REPOSITORY = "Luo-Z-Y/FirstRoll"
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
MAX_FILES = 100
MAX_BYTES = 64 * 1024 * 1024
REQUIRED_FILES = {
    "index.html",
    "assets/config.js",
    "assets/app.js",
    "assets/auth.js",
    "assets/styles.css",
}


def fingerprint(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def receipt_digest(receipt: dict) -> str:
    return fingerprint(
        canonical({key: value for key, value in receipt.items() if key != "receipt_digest"})
    )


def now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Release timestamps require a timezone")
    return parsed


def safe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and not path.is_absolute()
        and ".." not in path.parts
        and str(path) == name
        and re.fullmatch(r"[A-Za-z0-9_./-]+", name)
        and not any(part.startswith(".") for part in path.parts)
    )


def inventory(directory: Path) -> dict[str, str]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Release directory must be a real directory")
    files: dict[str, str] = {}
    total = 0
    for path in sorted(directory.rglob("*")):
        name = path.relative_to(directory).as_posix()
        if path.is_symlink() or not safe_path(name):
            raise ValueError("Unsafe release path")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("Non-regular release file")
        if name == "release.json":
            continue  # Receipt includes the inventory; exclude this circular reference.
        total += path.stat().st_size
        if total > MAX_BYTES or len(files) >= MAX_FILES:
            raise ValueError("Release exceeds its file or size budget")
        files[name] = fingerprint(path.read_bytes())
    if not REQUIRED_FILES.issubset(files):
        raise ValueError("Required frontend files are missing")
    return files


def read_json(path: Path) -> dict:
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Invalid receipt file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Receipt must be an object")
    return value


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def output(name: str, value: str | int) -> None:
    text = str(value)
    if "\n" in text or "\r" in text:
        raise ValueError("Unsafe GitHub output")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(f"{name}={text}\n")
