"""Poster images for screening listings, served through FirstRoll.

Listings never carry a venue's image URL. Each poster is registered under an opaque id
(the first 32 hex characters of the SHA-256 of its HTTPS URL) and the browser asks
FirstRoll for ``/api/screenings/posters/<id>``, so visitors' browsers never contact a
venue host. Images are fetched on demand through the guarded transport, accepted only
as JPEG, PNG, WebP, GIF or AVIF whose leading bytes agree, and kept in a bounded
in-memory cache.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Iterable

from app.backend.screenings_http import (
    ScreeningError,
    host_allowed,
    log_source_failure,
    normalise_hosts,
    request_bytes,
)

POSTER_PATH = "/api/screenings/posters/"
POSTER_ID = re.compile(r"[0-9a-f]{32}")
IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"})
IMAGE_ACCEPT = "image/avif,image/webp,image/png,image/jpeg,image/gif;q=0.9"
POSTER_TIMEOUT_SECONDS = 10
MAX_POSTER_BYTES = 3 * 1024 * 1024
CACHE_BYTES = 64 * 1024 * 1024
POSTER_CACHE_SECONDS = 24 * 60 * 60
FAILURE_CACHE_SECONDS = 10 * 60
REGISTRY_SECONDS = 24 * 60 * 60
REGISTRY_LIMIT = 5_000

# Returns the body and the media type the upstream server declared.
ImageTransport = Callable[[str, frozenset[str]], tuple[bytes, str]]


class PosterNotFound(LookupError):
    """The id is malformed, was never listed or has expired."""


class PosterUnavailable(RuntimeError):
    """The venue's image could not be fetched or is not an accepted image."""


@dataclass(frozen=True)
class Poster:
    content_type: str
    body: bytes


def poster_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def sniff_image(body: bytes) -> str | None:
    """The image type that the leading bytes identify, if it is one FirstRoll serves."""
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if body[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    if body[4:8] == b"ftyp":
        box = min(int.from_bytes(body[:4], "big"), len(body), 64)
        brands = {body[8:12], *(body[offset:offset + 4] for offset in range(16, box - 3, 4))}
        if brands & {b"avif", b"avis"}:
            return "image/avif"
    return None


def download_image(url: str, hosts: frozenset[str]) -> tuple[bytes, str]:
    body, content_type, _ = request_bytes(
        url,
        allowed_hosts=hosts,
        accept=IMAGE_ACCEPT,
        timeout=POSTER_TIMEOUT_SECONDS,
        max_bytes=MAX_POSTER_BYTES,
        total_seconds=POSTER_TIMEOUT_SECONDS,
    )
    return body, content_type


class PosterProxy:
    """Registry of listed posters plus a single-flight, size-capped LRU byte cache."""

    def __init__(
        self,
        transport: ImageTransport | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        cache_bytes: int = CACHE_BYTES,
    ) -> None:
        self.transport = transport or download_image
        self.clock = clock
        self.cache_bytes = cache_bytes
        self._registry: OrderedDict[str, tuple[str, frozenset[str], float]] = OrderedDict()
        self._images: OrderedDict[str, tuple[float, Poster]] = OrderedDict()
        self._image_bytes = 0
        self._failures: dict[str, float] = {}
        self._flights: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def register(self, url: str | None, hosts: Iterable[str]) -> str | None:
        """Record a listed poster and return its FirstRoll path, or None if off-list."""
        allowed = normalise_hosts(hosts)
        if not url or not host_allowed(url, allowed):
            return None
        identifier = poster_id(url)
        with self._lock:
            self._registry[identifier] = (url, allowed, self.clock())
            self._registry.move_to_end(identifier)
            while len(self._registry) > REGISTRY_LIMIT:
                self._registry.popitem(last=False)
        return POSTER_PATH + identifier

    def fetch(self, identifier: str) -> Poster:
        if not POSTER_ID.fullmatch(identifier):
            raise PosterNotFound(identifier)
        with self._lock:
            url, hosts = self._known(identifier)
            if cached := self._cached(identifier):
                return cached
            flight = self._flights.setdefault(identifier, threading.Lock())
        with flight:
            try:
                with self._lock:
                    # Another request for the same id may have finished while this waited.
                    if cached := self._cached(identifier):
                        return cached
                try:
                    poster = self._download(url, hosts)
                except PosterUnavailable:
                    with self._lock:
                        self._record_failure(identifier)
                    raise
                with self._lock:
                    self._store(identifier, poster)
                return poster
            finally:
                with self._lock:
                    if self._flights.get(identifier) is flight:
                        del self._flights[identifier]

    def _known(self, identifier: str) -> tuple[str, frozenset[str]]:
        entry = self._registry.get(identifier)
        if entry is None or self.clock() - entry[2] > REGISTRY_SECONDS:
            self._registry.pop(identifier, None)
            self._drop_image(identifier)
            raise PosterNotFound(identifier)
        return entry[0], entry[1]

    def _cached(self, identifier: str) -> Poster | None:
        now = self.clock()
        image = self._images.get(identifier)
        if image is not None:
            if image[0] > now:
                self._images.move_to_end(identifier)
                return image[1]
            self._drop_image(identifier)
        failed_until = self._failures.get(identifier)
        if failed_until is not None:
            if failed_until > now:
                raise PosterUnavailable("The venue's image failed recently.")
            del self._failures[identifier]
        return None

    def _download(self, url: str, hosts: frozenset[str]) -> Poster:
        try:
            body, declared = self.transport(url, hosts)
        except ScreeningError as exc:
            log_source_failure("poster", exc)
            raise PosterUnavailable("The venue's image could not be fetched.") from exc
        declared_type = str(declared or "").split(";", 1)[0].strip().casefold()
        sniffed = sniff_image(body)
        if declared_type not in IMAGE_TYPES or sniffed is None:
            raise PosterUnavailable("The venue's image is not an accepted image type.")
        return Poster(content_type=sniffed, body=body)

    def _store(self, identifier: str, poster: Poster) -> None:
        size = len(poster.body)
        if size > self.cache_bytes:
            return
        self._drop_image(identifier)
        self._images[identifier] = (self.clock() + POSTER_CACHE_SECONDS, poster)
        self._image_bytes += size
        while self._image_bytes > self.cache_bytes and self._images:
            oldest = next(iter(self._images))
            self._drop_image(oldest)

    def _drop_image(self, identifier: str) -> None:
        image = self._images.pop(identifier, None)
        if image is not None:
            self._image_bytes -= len(image[1].body)

    def _record_failure(self, identifier: str) -> None:
        now = self.clock()
        self._failures[identifier] = now + FAILURE_CACHE_SECONDS
        if len(self._failures) > REGISTRY_LIMIT:
            for key in [key for key, until in self._failures.items() if until <= now]:
                del self._failures[key]
            while len(self._failures) > REGISTRY_LIMIT:
                del self._failures[next(iter(self._failures))]
