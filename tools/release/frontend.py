"""Prepare, verify and recover static releases without executing artefact code."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from tools.release.protocol import (
    REPOSITORY,
    MAX_BYTES,
    canonical,
    change_base,
    create_receipt,
    fingerprint,
    inventory,
    output,
    read_json,
    validate_receipt,
    verify_directory,
    write_json,
)


SITE = "https://firstroll.app"
API = "https://api.firstroll.app"
WORKFLOW = ".github/workflows/azure-static-web-apps-salmon-field-03695a010.yml"


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url: str, *, github: bool = False, limit: int = MAX_BYTES, timeout: float = 10) -> bytes:
    # No artefact-supplied URL reaches this function. Authentication is sent only
    # to api.github.com; redirects fail rather than forwarding credentials.
    allowed = "https://api.github.com/" if github else (SITE + "/", API + "/")
    if not url.startswith(allowed):
        raise ValueError("Unapproved release verification origin")
    headers = {"Cache-Control": "no-cache", "User-Agent": "FirstRoll-release-verifier"}
    if github:
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
        headers["Accept"] = "application/vnd.github+json"
    with build_opener(NoRedirects()).open(
        Request(url, headers=headers), timeout=timeout
    ) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Release response exceeds its size budget")
    return data


def github_json(path: str) -> dict:
    return json.loads(
        fetch(f"https://api.github.com/repos/{REPOSITORY}/{path}", github=True, limit=1024 * 1024)
    )


def live_receipt() -> dict | None:
    try:
        data = fetch(f"{SITE}/release.json?release_check={time.time_ns()}", limit=1024 * 1024)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    receipt = json.loads(data)
    validate_receipt(receipt, component="frontend", fresh=False)
    return receipt


def resolve_previous(receipt: dict) -> dict:
    """Bind the live receipt to a successful same-repository production build."""
    validate_receipt(receipt, component="frontend", fresh=False)
    run = github_json(f"actions/runs/{receipt['workflow_run_id']}")
    if not (
        run.get("path") == WORKFLOW
        and run.get("head_sha") == receipt["commit_sha"]
        and run.get("head_branch") == "master"
        and run.get("conclusion") == "success"
        and run.get("status") == "completed"
        and run.get("head_repository", {}).get("full_name") == REPOSITORY
        and run.get("event") in {"workflow_run", "workflow_dispatch"}
    ):
        raise ValueError("The live frontend has no successful trusted release run")
    records = github_json(f"actions/runs/{receipt['workflow_run_id']}/artifacts?per_page=100")
    matches = [item for item in records["artifacts"] if item["name"] == receipt["artifact_name"]]
    if len(matches) != 1 or matches[0]["expired"] or type(matches[0]["id"]) is not int:
        raise ValueError(
            "The previous frontend artefact is missing or expired; recovery is required"
        )
    return {
        "artifact_id": matches[0]["id"],
        "run_id": receipt["workflow_run_id"],
        "commit_sha": receipt["commit_sha"],
        "receipt_digest": receipt["receipt_digest"],
    }


def frontend_risk(commit: str, previous_commit: str) -> str:
    """Never label delivery-control changes as an ordinary static-content update."""
    base = change_base(commit, previous_commit)
    changed = subprocess.run(
        ["git", "diff", "--name-only", "-z", base, commit, "--"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    return (
        "high"
        if any(path.startswith((b".github/workflows/", b"tools/release/")) for path in changed)
        else "medium"
    )


def prepare(site: Path, *, commit: str, run_id: int, attempt: int, allow_initial: bool) -> dict:
    current = live_receipt()
    if current is None and not allow_initial:
        raise ValueError(
            "No live release receipt. Run Frontend Release manually with allow_initial_release "
            "to acknowledge that this first release has no automatic rollback baseline."
        )
    previous = resolve_previous(current) if current else None
    files = inventory(site)
    receipt = create_receipt(
        component="frontend",
        commit=commit,
        run_id=run_id,
        attempt=attempt,
        payload_digest=fingerprint(canonical(files)),
        files=files,
        previous=previous,
        bootstrap=previous is None,
        # All frontend updates are at least medium risk; bootstrap/control changes are high.
        risk="high" if previous is None else frontend_risk(commit, previous["commit_sha"]),
    )
    write_json(site / "release.json", receipt)
    output("artifact-name", receipt["artifact_name"])
    output("receipt-digest", receipt["receipt_digest"])
    output("commit-sha", commit)
    output("run-attempt", attempt)
    rollback = (
        "Restore the retained, verified previous static package if live checks fail."
        if previous
        else "INITIAL RELEASE: no verified previous package exists. "
        "Automatic rollback is unavailable; approval explicitly accepts this bootstrap risk."
    )
    print(
        f"# FirstRoll frontend release is ready\n\n"
        f"- Release: `{receipt['release_id']}`\n- Source: `{commit}`\n"
        f"- Fingerprint: `{receipt['payload_digest']}`\n"
        f"- Approval expires: {receipt['expires_at']}\n"
        "- Checks: exact-commit CI, dependency audit, build and file inventory passed.\n"
        f"- Risk: {receipt['risk']} (conservative baseline, not a vulnerability scan).\n"
        "- Changes: replace the frontend static files only. API and database are unchanged.\n"
        "- No Terraform apply or database migration runs in this workflow.\n"
        "- After approval: recheck commit, receipt, expiry and rollback baseline; upload once; "
        "verify live files and API reachability.\n"
        f"- Recovery: {rollback}\n"
        "- Artefacts retained for 90 days, subject to repository retention settings.\n"
        "- Complete browser sign-in, film search and study testing remains a manual acceptance step."
    )
    return receipt


def check_baseline(candidate: dict) -> dict | None:
    """Recheck after human approval, before any production token is used."""
    validate_receipt(candidate, component="frontend")
    current = live_receipt()
    previous = candidate["previous"]
    if previous is None:
        if current is not None or not candidate["bootstrap"]:
            raise ValueError("Production changed after initial-release preparation")
        return None
    if current is None or resolve_previous(current) != previous:
        raise ValueError("Production changed while approval was pending; build a fresh candidate")
    return previous


def verify_rollback(candidate: dict, site: Path) -> dict:
    previous = candidate.get("previous")
    if not previous:
        raise ValueError("No approved rollback baseline")
    receipt = read_json(site / "release.json")
    # Seven days limits *new* approvals, not restoration of a retained known-good release.
    validate_receipt(
        receipt,
        component="frontend",
        commit=previous["commit_sha"],
        run_id=previous["run_id"],
        expected_digest=previous["receipt_digest"],
        fresh=False,
    )
    verify_directory(receipt, site)
    return receipt


def verify_live(receipt: dict, *, include_api: bool = True, deadline_seconds: float = 180) -> None:
    """Check the served receipt and every static file, retrying bounded CDN propagation."""
    validate_receipt(receipt, component="frontend", fresh=False)
    deadline = time.monotonic() + deadline_seconds
    while True:
        try:

            def get(url: str) -> bytes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Live verification deadline exceeded")
                return fetch(url, timeout=min(10, remaining))

            nonce = str(time.time_ns())
            live = json.loads(get(f"{SITE}/release.json?release_check={nonce}"))
            if live != receipt:
                raise ValueError("The live frontend serves a different release")
            for name, digest in receipt["files"].items():
                if name == "staticwebapp.config.json":
                    continue  # Azure consumes this deployment config; it is not a public asset.
                if fingerprint(get(f"{SITE}/{name}?release_check={nonce}")) != digest:
                    raise ValueError(f"Live file fingerprint mismatch: {name}")
            if include_api:
                health = json.loads(get(API + "/api/health"))
                if health.get("status") != "ok":
                    raise ValueError("Live API is unhealthy")
                for path in ("api/contract", "api/discovery/status"):
                    get(API + "/" + path)
            return
        except (OSError, ValueError) as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError("Live frontend verification failed within its deadline") from exc
            time.sleep(min(5, max(0, deadline - time.monotonic())))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("prepare", "baseline", "verify-rollback", "live", "live-rollback")
    )
    parser.add_argument("--site", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--allow-initial", choices=("true", "false"), default="false")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(
            args.site,
            commit=args.commit,
            run_id=args.run_id,
            attempt=args.attempt,
            allow_initial=args.allow_initial == "true",
        )
    elif args.command == "baseline":
        previous = check_baseline(read_json(args.candidate))
        output("artifact-id", previous["artifact_id"] if previous else "")
        output("run-id", previous["run_id"] if previous else "")
    elif args.command == "verify-rollback":
        verify_rollback(read_json(args.candidate), args.site)
    elif args.command == "live-rollback":
        verify_live(verify_rollback(read_json(args.candidate), args.site), include_api=False)
    else:
        verify_live(read_json(args.site / "release.json"))


if __name__ == "__main__":
    main()
