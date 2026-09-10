"""Shared, dependency-free release receipts and fail-closed deployment checks.

Build artefacts are data, never deployment scripts. Deploy jobs fetch this control
module from the exact CI-approved Git commit before obtaining cloud credentials.
A receipt hash detects changes; it is not an independent signature or attestation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
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


def change_base(commit: str, production_commit: str | None) -> str:
    """Diff from what is deployed, not merely the most recent merge.

    Unknown/legacy production versions force a whole-tree review; they never
    silently skip pending backend changes. A non-ancestor is handled likewise.
    """
    if not SHA.fullmatch(commit):
        raise ValueError("Invalid candidate commit")
    if isinstance(production_commit, str) and SHA.fullmatch(production_commit):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", production_commit, commit], capture_output=True
        )
        if result.returncode == 0:
            return production_commit
    return subprocess.run(
        ["git", "hash-object", "-w", "-t", "tree", "--stdin"],
        input="",
        text=True,
        check=True,
        capture_output=True,
    ).stdout.strip()


def health_commit(path: Path) -> str | None:
    """An unavailable/unversioned API must not prevent preparing a recovery release."""
    try:
        health = read_json(path)
    except (OSError, ValueError):
        return None
    commit = health.get("release_sha")
    if health.get("status") != "ok" or not isinstance(commit, str) or not SHA.fullmatch(commit):
        return None
    return commit


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


def create_receipt(
    *,
    component: str,
    commit: str,
    run_id: int,
    attempt: int,
    payload_digest: str,
    files: dict | None = None,
    evidence_digest: str | None = None,
    previous: dict | None = None,
    bootstrap: bool = False,
    risk: str = "high",
    clock: datetime | None = None,
) -> dict:
    created = clock or now()
    receipt = {
        "schema_version": SCHEMA,
        "repository": REPOSITORY,
        "environment": "production",
        "branch": "master",
        "component": component,
        "commit_sha": commit,
        "workflow_run_id": run_id,
        "run_attempt": attempt,
        "release_id": f"{component}-{commit[:8]}-{run_id}-{attempt}",
        "artifact_name": f"{component}-release-{run_id}-{attempt}",
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(days=7)).isoformat(),
        "payload_digest": payload_digest,
        "evidence_digest": evidence_digest,
        "files": files or {},
        "previous": previous,
        "bootstrap": bootstrap,
        "checks": {"ci": True, "build": True},
        "risk": risk,
    }
    receipt["receipt_digest"] = receipt_digest(receipt)
    validate_receipt(receipt, clock=created)
    return receipt


def validate_receipt(
    receipt: dict,
    *,
    component: str | None = None,
    commit: str | None = None,
    run_id: int | None = None,
    attempt: int | None = None,
    expected_digest: str | None = None,
    fresh: bool = True,
    clock: datetime | None = None,
) -> None:
    """Expected bindings come from GitHub job outputs, not from the downloaded receipt."""
    valid = (
        receipt.get("schema_version") == SCHEMA
        and receipt.get("repository") == REPOSITORY
        and receipt.get("environment") == "production"
        and receipt.get("branch") == "master"
        and receipt.get("component") in {"frontend", "backend"}
        and isinstance(receipt.get("commit_sha"), str)
        and SHA.fullmatch(receipt["commit_sha"])
        and type(receipt.get("workflow_run_id")) is int
        and receipt["workflow_run_id"] > 0
        and type(receipt.get("run_attempt")) is int
        and receipt["run_attempt"] > 0
        and isinstance(receipt.get("payload_digest"), str)
        and DIGEST.fullmatch(receipt["payload_digest"])
        and receipt.get("checks", {}).get("ci") is True
        and receipt.get("checks", {}).get("build") is True
        and receipt.get("risk") in {"low", "medium", "high"}
        and type(receipt.get("bootstrap")) is bool
        and receipt.get("receipt_digest") == receipt_digest(receipt)
    )
    if not valid:
        raise ValueError("Invalid release receipt, checks or fingerprint")
    for key, expected in (
        ("component", component),
        ("commit_sha", commit),
        ("workflow_run_id", run_id),
        ("run_attempt", attempt),
        ("receipt_digest", expected_digest),
    ):
        if expected is not None and receipt.get(key) != expected:
            raise ValueError(f"Release {key} does not match the approved candidate")
    expected_name = (
        f"{receipt['component']}-release-{receipt['workflow_run_id']}-{receipt['run_attempt']}"
    )
    if receipt.get("artifact_name") != expected_name:
        raise ValueError("Unexpected release artefact name")
    expected_id = f"{receipt['component']}-{receipt['commit_sha'][:8]}-{receipt['workflow_run_id']}-{receipt['run_attempt']}"
    if receipt.get("release_id") != expected_id:
        raise ValueError("Unexpected release ID")
    created, expires = timestamp(receipt["created_at"]), timestamp(receipt["expires_at"])
    current = clock or now()
    if expires - created != timedelta(days=7) or created > current + timedelta(minutes=5):
        raise ValueError("Invalid release validity window")
    if fresh and current >= expires:
        raise ValueError("Release approval window expired; build a fresh candidate")
    if receipt["component"] == "frontend":
        files = receipt.get("files")
        if (
            not isinstance(files, dict)
            or not REQUIRED_FILES.issubset(files)
            or len(files) > MAX_FILES
        ):
            raise ValueError("Invalid frontend inventory")
        if any(
            not safe_path(path)
            or path == "release.json"
            or not isinstance(digest, str)
            or not DIGEST.fullmatch(digest)
            for path, digest in files.items()
        ):
            raise ValueError("Unsafe frontend inventory entry")
        if fingerprint(canonical(files)) != receipt["payload_digest"]:
            raise ValueError("Frontend inventory fingerprint mismatch")
        if receipt["bootstrap"] != (receipt.get("previous") is None):
            raise ValueError("Missing explicit initial-release acknowledgement")
    elif not isinstance(receipt.get("evidence_digest"), str) or not DIGEST.fullmatch(
        receipt["evidence_digest"]
    ):
        raise ValueError("Missing backend evidence fingerprint")


def verify_directory(receipt: dict, directory: Path) -> None:
    if inventory(directory) != receipt["files"]:
        raise ValueError("Frontend files differ from the approved inventory")


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seal-backend", "verify"))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--component", choices=("frontend", "backend"), default="backend")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--expected-digest")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--site", type=Path)
    args = parser.parse_args()
    if args.command == "seal-backend":
        evidence = read_json(args.evidence)
        receipt = create_receipt(
            component="backend",
            commit=args.commit,
            run_id=args.run_id,
            attempt=args.attempt,
            payload_digest=evidence["candidate"]["image_digest"],
            evidence_digest=fingerprint(args.evidence.read_bytes()),
            risk=evidence["change_summary"]["risk_level"],
        )
        write_json(args.receipt, receipt)
        output("receipt-digest", receipt["receipt_digest"])
        output("artifact-name", receipt["artifact_name"])
        print(
            f"Receipt: {receipt['release_id']}\nApprove before: {receipt['expires_at']}\n"
            "Evidence retained for 90 days; new deployments expire after seven days."
        )
    else:
        if not args.expected_digest:
            parser.error("verify requires --expected-digest from the build job")
        receipt = read_json(args.receipt)
        validate_receipt(
            receipt,
            component=args.component,
            commit=args.commit,
            run_id=args.run_id,
            attempt=args.attempt,
            expected_digest=args.expected_digest,
        )
        if args.component == "frontend":
            verify_directory(receipt, args.site)
        elif fingerprint(args.evidence.read_bytes()) != receipt["evidence_digest"]:
            raise ValueError("Backend evidence differs from the approved receipt")


if __name__ == "__main__":
    main()
