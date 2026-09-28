"""Seal and verify single-server (VPS) releases without executing artefact code.

The build job seals a receipt that binds the static site inventory and the immutable API
image digest to one commit, workflow run and attempt. After human approval, the deploy job
re-verifies that receipt and the uploaded archive before any SSH credential is written, and
checks the live site and API afterwards. Only the two production origins are ever fetched.
"""

from __future__ import annotations

import argparse
import json
import tarfile
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from tools.release.protocol import (
    DIGEST,
    MAX_BYTES,
    MAX_FILES,
    REPOSITORY,
    REQUIRED_FILES,
    SCHEMA,
    SHA,
    canonical,
    fingerprint,
    inventory,
    now,
    output,
    read_json,
    receipt_digest,
    safe_path,
    timestamp,
    write_json,
)


SITE = "https://firstroll.app"
API = "https://api.firstroll.app"
IMAGE_REPOSITORY = "ghcr.io/luo-z-y/firstroll-api"
COMPONENT = "vps"
APPROVAL_WINDOW = timedelta(days=7)
HIDDEN_API_PATHS = ("docs", "redoc", "openapi.json")
REQUIRED_API_PATHS = ("api/contract", "api/discovery/status")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LiveClient:
    """Bounded HTTPS access to the two production origins only."""

    def __init__(self, timeout: float = 10) -> None:
        self.timeout = timeout
        self.opener = build_opener(NoRedirects())

    def _open(self, url: str, *, method: str = "GET", headers: dict | None = None):
        if not url.startswith((SITE + "/", API + "/")):
            raise ValueError("Unapproved release verification origin")
        request = Request(
            url,
            method=method,
            headers={
                "Cache-Control": "no-cache",
                "User-Agent": "FirstRoll-release-verifier",
                **(headers or {}),
            },
        )
        return self.opener.open(request, timeout=self.timeout)

    def get(self, url: str) -> bytes:
        with self._open(url) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Release response exceeds its size budget")
        return data

    def status(self, url: str) -> int:
        try:
            with self._open(url) as response:
                return response.status
        except HTTPError as exc:
            return exc.code

    def preflight(self, url: str, origin: str) -> str | None:
        headers = {"Origin": origin, "Access-Control-Request-Method": "GET"}
        with self._open(url, method="OPTIONS", headers=headers) as response:
            return response.headers.get("Access-Control-Allow-Origin")


def expected_image(commit: str) -> str:
    return f"{IMAGE_REPOSITORY}:{commit}"


def prepare(
    site: Path,
    *,
    commit: str,
    run_id: int,
    attempt: int,
    image: str,
    image_digest: str,
    clock: datetime | None = None,
) -> dict:
    """Seal the built site and pushed image into a receipt written beside the site files."""
    if not SHA.fullmatch(commit or ""):
        raise ValueError("Commit must be a full 40-character SHA")
    if not DIGEST.fullmatch(image_digest or ""):
        raise ValueError("Image digest must be sha256:<64 hex>")
    if image != expected_image(commit):
        raise ValueError("The pushed image does not match the approved image repository")
    if run_id <= 0 or attempt <= 0:
        raise ValueError("Workflow run and attempt must be positive")
    files = inventory(site)
    created = clock or now()
    receipt = {
        "schema_version": SCHEMA,
        "repository": REPOSITORY,
        "environment": "production",
        "branch": "master",
        "component": COMPONENT,
        "commit_sha": commit,
        "workflow_run_id": run_id,
        "run_attempt": attempt,
        "release_id": f"{COMPONENT}-{commit[:8]}-{run_id}-{attempt}",
        "artifact_name": f"{COMPONENT}-release-{run_id}-{attempt}",
        "created_at": created.isoformat(),
        "expires_at": (created + APPROVAL_WINDOW).isoformat(),
        "image": image,
        "image_digest": image_digest,
        "payload_digest": fingerprint(canonical(files)),
        "files": files,
    }
    receipt["receipt_digest"] = receipt_digest(receipt)
    write_json(site / "release.json", receipt)
    output("artifact-name", receipt["artifact_name"])
    output("receipt-digest", receipt["receipt_digest"])
    output("release-id", receipt["release_id"])
    print(
        "# FirstRoll single-server release is ready\n\n"
        f"- Release: `{receipt['release_id']}`\n"
        f"- Source: `{commit}`\n"
        f"- Image: `{image}` at `{image_digest}`\n"
        f"- Site fingerprint: `{receipt['payload_digest']}` ({len(files)} files)\n"
        f"- Approval expires: {receipt['expires_at']}\n"
        "- Checks: exact-commit CI, dependency audit, frontend build, container smoke test and "
        "file inventory passed.\n"
        "- Changes: replaces the API container by immutable digest and the static site together "
        "on the single server. No Terraform apply or database migration runs.\n"
        "- After approval: recheck commit, receipt, archive inventory and current master before "
        "the SSH key is written; upload once; release on the server; verify the live receipt, "
        "files, API identity, hidden docs and CORS. Failure restores the previous release.\n"
        "- Artefacts retained for 90 days, subject to repository retention settings.\n"
        "- Browser sign-in, film search and study checks remain a manual acceptance step."
    )
    return receipt


def validate(
    receipt: dict,
    *,
    commit: str | None = None,
    run_id: int | None = None,
    attempt: int | None = None,
    expected_digest: str | None = None,
    image_digest: str | None = None,
    fresh: bool = True,
    clock: datetime | None = None,
) -> None:
    """Expected bindings come from GitHub job outputs, never from the downloaded receipt."""
    files = receipt.get("files")
    valid = (
        receipt.get("schema_version") == SCHEMA
        and receipt.get("repository") == REPOSITORY
        and receipt.get("environment") == "production"
        and receipt.get("branch") == "master"
        and receipt.get("component") == COMPONENT
        and isinstance(receipt.get("commit_sha"), str)
        and SHA.fullmatch(receipt["commit_sha"])
        and type(receipt.get("workflow_run_id")) is int
        and receipt["workflow_run_id"] > 0
        and type(receipt.get("run_attempt")) is int
        and receipt["run_attempt"] > 0
        and receipt.get("image") == expected_image(receipt["commit_sha"])
        and isinstance(receipt.get("image_digest"), str)
        and DIGEST.fullmatch(receipt["image_digest"])
        and isinstance(files, dict)
        and REQUIRED_FILES.issubset(files)
        and len(files) <= MAX_FILES
        and all(
            safe_path(path)
            and path != "release.json"
            and isinstance(digest, str)
            and DIGEST.fullmatch(digest)
            for path, digest in files.items()
        )
        and receipt.get("payload_digest") == fingerprint(canonical(files))
        and receipt.get("receipt_digest") == receipt_digest(receipt)
    )
    if not valid:
        raise ValueError("Invalid single-server release receipt or fingerprint")
    for key, expected in (
        ("commit_sha", commit),
        ("workflow_run_id", run_id),
        ("run_attempt", attempt),
        ("receipt_digest", expected_digest),
        ("image_digest", image_digest),
    ):
        if expected is not None and receipt.get(key) != expected:
            raise ValueError(f"Release {key} does not match the approved candidate")
    run, build = receipt["workflow_run_id"], receipt["run_attempt"]
    if receipt.get("artifact_name") != f"{COMPONENT}-release-{run}-{build}":
        raise ValueError("Unexpected release artefact name")
    if receipt.get("release_id") != f"{COMPONENT}-{receipt['commit_sha'][:8]}-{run}-{build}":
        raise ValueError("Unexpected release ID")
    created, expires = timestamp(receipt["created_at"]), timestamp(receipt["expires_at"])
    current = clock or now()
    if expires - created != APPROVAL_WINDOW or created > current + timedelta(minutes=5):
        raise ValueError("Invalid release validity window")
    if fresh and current >= expires:
        raise ValueError("Release approval window expired; build a fresh candidate")


def verify_archive(receipt: dict, archive: Path) -> None:
    """The uploaded site archive must contain exactly the sealed inventory and receipt."""
    with tempfile.TemporaryDirectory() as extracted:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(extracted, filter="data")
        directory = Path(extracted)
        if inventory(directory) != receipt["files"]:
            raise ValueError("Site archive differs from the approved inventory")
        if read_json(directory / "release.json") != receipt:
            raise ValueError("Site archive carries a different release receipt")


def check_api(commit: str | None, client) -> dict:
    """Health, identity, required routes, hidden documentation and exact CORS origin."""
    health = json.loads(client.get(f"{API}/api/health"))
    if health.get("status") != "ok":
        raise ValueError("Live API is unhealthy")
    if commit is not None and health.get("release_sha") != commit:
        raise ValueError("Live API reports a different release")
    for path in REQUIRED_API_PATHS:
        client.get(f"{API}/{path}")
    for path in HIDDEN_API_PATHS:
        if client.status(f"{API}/{path}") != 404:
            raise ValueError(f"Generated API documentation is exposed at /{path}")
    if client.preflight(f"{API}/api/health", SITE) != SITE:
        raise ValueError("CORS does not allow exactly the production site origin")
    return health


def check_site(receipt: dict, client) -> None:
    nonce = str(time.time_ns())
    live = json.loads(client.get(f"{SITE}/release.json?release_check={nonce}"))
    if live != receipt:
        raise ValueError("The live site serves a different release")
    for name, digest in receipt["files"].items():
        if fingerprint(client.get(f"{SITE}/{name}?release_check={nonce}")) != digest:
            raise ValueError(f"Live file fingerprint mismatch: {name}")


def retry_until(check, *, deadline_seconds: float, clock=time.monotonic, sleep=time.sleep) -> None:
    deadline = clock() + deadline_seconds
    while True:
        try:
            check()
            return
        except (OSError, ValueError) as exc:
            if clock() >= deadline:
                raise RuntimeError("Live release verification failed within its deadline") from exc
            sleep(min(5, max(0, deadline - clock())))


def verify_live(
    receipt: dict,
    *,
    commit: str,
    client=None,
    deadline_seconds: float = 180,
    clock=time.monotonic,
    sleep=time.sleep,
) -> None:
    """Confirm the server serves exactly the approved site and the approved API build."""
    validate(receipt, commit=commit, fresh=False)
    client = client or LiveClient()

    def check() -> None:
        check_site(receipt, client)
        check_api(commit, client)

    retry_until(check, deadline_seconds=deadline_seconds, clock=clock, sleep=sleep)


def verify_health(
    *,
    commit: str | None = None,
    client=None,
    deadline_seconds: float = 120,
    clock=time.monotonic,
    sleep=time.sleep,
) -> None:
    """After a rollback, require a healthy API without asserting a particular release."""
    client = client or LiveClient()
    retry_until(
        lambda: check_api(commit, client),
        deadline_seconds=deadline_seconds,
        clock=clock,
        sleep=sleep,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify", "live", "health"))
    parser.add_argument("--site", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--image")
    parser.add_argument("--image-digest")
    parser.add_argument("--expected-digest")
    parser.add_argument("--deadline", type=float, default=180)
    args = parser.parse_args()
    if args.command == "prepare":
        for name in ("site", "commit", "run_id", "attempt", "image", "image_digest"):
            if getattr(args, name) is None:
                parser.error(f"prepare requires --{name.replace('_', '-')}")
        prepare(
            args.site,
            commit=args.commit,
            run_id=args.run_id,
            attempt=args.attempt,
            image=args.image,
            image_digest=args.image_digest,
        )
    elif args.command == "verify":
        for name in ("receipt", "archive", "commit", "run_id", "attempt", "expected_digest", "image_digest"):
            if getattr(args, name) is None:
                parser.error(f"verify requires --{name.replace('_', '-')}")
        receipt = read_json(args.receipt)
        validate(
            receipt,
            commit=args.commit,
            run_id=args.run_id,
            attempt=args.attempt,
            expected_digest=args.expected_digest,
            image_digest=args.image_digest,
        )
        verify_archive(receipt, args.archive)
        print(f"Verified {receipt['release_id']} and its site archive.")
    elif args.command == "live":
        if args.receipt is None or args.commit is None:
            parser.error("live requires --receipt and --commit")
        verify_live(read_json(args.receipt), commit=args.commit, deadline_seconds=args.deadline)
        print("Live site and API match the approved release.")
    else:
        verify_health(commit=args.commit, deadline_seconds=args.deadline)
        print("Live API is healthy.")


if __name__ == "__main__":
    main()
