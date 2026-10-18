"""HTTP routes for Singapore screening listings and their proxied posters.

Both routes run their blocking work on their own small thread limiters rather than on
the shared default pool, so a slow venue or image host can never starve
``/api/health`` or any other synchronous route of threads.

Listings are cached by browsers for ten minutes only when every venue has settled (read,
empty or unlisted, and nothing stale); while a venue is still loading, failed or stale the
lifetime is thirty seconds, so a reload soon picks up the read that finished meanwhile.
Responses vary by ``Origin`` as well as ``Accept-Encoding``, because CORS headers are added
only to cross-origin requests and a copy cached without them must not answer the site.
"""

from __future__ import annotations

import gzip
import json
from functools import partial
from typing import Any

import anyio
import anyio.to_thread
from anyio.lowlevel import RunVar
from fastapi import FastAPI, HTTPException, Request, Response

from app.backend.screenings import ScreeningsService
from app.backend.screenings_posters import POSTER_ID, PosterNotFound, PosterUnavailable

LISTING_THREADS = 3
POSTER_THREADS = 4
LISTING_HEADERS = {"Vary": "Accept-Encoding, Origin"}
SETTLED_CACHE = "public, max-age=600"
UNSETTLED_CACHE = "public, max-age=30"
SETTLED_STATES = frozenset({"ok", "empty", "unlisted"})
POSTER_HEADERS = {
    "Cache-Control": "public, max-age=86400",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cross-Origin-Resource-Policy": "cross-origin",
}
POSTER_ERROR_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}

# One limiter per event loop, as anyio keeps its own default limiter.
_listing_limiter: RunVar[anyio.CapacityLimiter] = RunVar("firstroll_screening_listings")
_poster_limiter: RunVar[anyio.CapacityLimiter] = RunVar("firstroll_screening_posters")


def _limiter(slot: RunVar[anyio.CapacityLimiter], tokens: int) -> anyio.CapacityLimiter:
    try:
        return slot.get()
    except LookupError:
        limiter = anyio.CapacityLimiter(tokens)
        slot.set(limiter)
        return limiter


def accepts_gzip(header: str) -> bool:
    """Whether an ``Accept-Encoding`` value allows gzip (explicitly or through ``*``)."""
    weights: dict[str, float] = {}
    for part in header.split(","):
        coding, *parameters = part.split(";")
        weight = 1.0
        for parameter in parameters:
            name, _, value = parameter.partition("=")
            if name.strip().casefold() == "q":
                try:
                    weight = float(value.strip())
                except ValueError:
                    weight = 0.0
        weights.setdefault(coding.strip().casefold(), weight)
    if "gzip" in weights:
        return weights["gzip"] > 0
    return weights.get("*", 0.0) > 0


def listings_settled(listings: dict[str, Any]) -> bool:
    """Whether every source has a settled answer worth caching for ten minutes."""
    return all(
        source.get("state") in SETTLED_STATES and not source.get("stale")
        for source in listings.get("sources", ())
    )


def encoded_listings(service: ScreeningsService, compress: bool) -> tuple[bytes, bool]:
    """The listings JSON, gzipped if asked, and whether every source has settled."""
    listings = service.listings()
    body = json.dumps(listings, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = gzip.compress(body, compresslevel=6, mtime=0) if compress else body
    return encoded, listings_settled(listings)


def add_screenings_routes(app: FastAPI, service: ScreeningsService) -> None:
    """Register both routes on ``app`` (the module-level API or a test's hosted shell)."""

    @app.get("/api/screenings/singapore")
    async def singapore_screenings(request: Request) -> Response:
        """Public listings from Singapore venues; each venue is cached and fails independently."""
        compress = accepts_gzip(request.headers.get("accept-encoding", ""))
        body, settled = await anyio.to_thread.run_sync(
            partial(encoded_listings, service, compress),
            limiter=_limiter(_listing_limiter, LISTING_THREADS),
        )
        headers = {**LISTING_HEADERS, "Cache-Control": SETTLED_CACHE if settled else UNSETTLED_CACHE}
        if compress:
            headers["Content-Encoding"] = "gzip"
        return Response(content=body, media_type="application/json", headers=headers)

    @app.get("/api/screenings/posters/{poster_id}")
    async def screening_poster(poster_id: str) -> Response:
        """A listed poster image, fetched from the venue by FirstRoll and never by the browser."""
        if not POSTER_ID.fullmatch(poster_id):
            raise HTTPException(status_code=404, detail="Unknown poster.", headers=POSTER_ERROR_HEADERS)
        try:
            poster = await anyio.to_thread.run_sync(
                service.posters.fetch, poster_id, limiter=_limiter(_poster_limiter, POSTER_THREADS)
            )
        except PosterNotFound as exc:
            raise HTTPException(
                status_code=404, detail="Unknown poster.", headers=POSTER_ERROR_HEADERS
            ) from exc
        except PosterUnavailable as exc:
            raise HTTPException(
                status_code=502, detail="The poster could not be fetched.", headers=POSTER_ERROR_HEADERS
            ) from exc
        return Response(content=poster.body, media_type=poster.content_type, headers=POSTER_HEADERS)
