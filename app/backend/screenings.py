"""Public Singapore screening listings gathered from cinema and venue websites.

Each venue adapter (``screenings_venues``, ``screenings_sgiff``) turns one operator's
public listings into the shared ``Screening`` shape. Adapters fail independently: one
blocked or redesigned site never hides the others, and its failure is reported as a
source state instead of an empty listing. This module schedules and caches the reads.

* Each venue is refreshed by one in-flight read at a time (single-flight), on a
  long-lived bounded pool, so concurrent visitors never multiply upstream requests.
* A request waits at most ``deadline_seconds`` in total. A venue still being read after
  that is served from its earlier listings, marked ``stale``, or reported as an error;
  its read carries on in the background and fills the cache for the next request.
* A refresh that fails keeps serving the earlier listings, marked ``stale``, for up to
  a day, and is retried after ``FAILURE_CACHE_SECONDS``.
* Booking links and posters survive only on each adapter's allow-listed hosts, and
  poster URLs are swapped for FirstRoll's own proxy paths before leaving the server.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterable

from app.backend.screenings_http import ScreeningError, host_allowed, log_source_failure
from app.backend.screenings_model import (
    CACHE_SECONDS,
    FAILURE_CACHE_SECONDS,
    LISTING_DAYS,
    SINGAPORE,
    Fetched,
    Screening,
    ScreeningAdapter,
    SourceState,
    SourceStatus,
    Venue,
)
from app.backend.screenings_posters import PosterProxy
from app.backend.screenings_sgiff import SgiffAdapter
from app.backend.screenings_venues import (
    AllianceFrancaiseAdapter,
    AsianFilmArchiveAdapter,
    FilmhouseAdapter,
    PeatixScreeningsAdapter,
    ShawTheatresAdapter,
    UnlistedVenue,
)

DEADLINE_SECONDS = 20.0
STALE_SECONDS = 24 * 60 * 60
MAX_WORKERS = 8
SLOW_MESSAGE = "The venue is slow to answer; its listings should appear shortly."
CHANGED_MESSAGE = "The venue's listings changed shape and could not be read."
STALE_SUFFIX = "Showing the listings read earlier."


@dataclass(frozen=True)
class _Entry:
    expires: float
    read_at: float | None  # When ``items`` were last read successfully.
    status: SourceStatus
    items: tuple[Screening, ...]


class ScreeningsService:
    """Concurrent, cached and failure-isolated listings across every configured venue."""

    def __init__(
        self,
        adapters: Iterable[ScreeningAdapter],
        *,
        clock: Callable[[], float] = time.time,
        posters: PosterProxy | None = None,
        deadline_seconds: float = DEADLINE_SECONDS,
    ) -> None:
        self.adapters = list(adapters)
        self.clock = clock
        self.posters = posters or PosterProxy()
        self.deadline_seconds = deadline_seconds
        self._cache: dict[str, _Entry] = {}
        self._inflight: dict[str, Future[None]] = {}
        self._venue_locks = {adapter.venue.id: threading.Lock() for adapter in self.adapters}
        self._lock = threading.Lock()
        # Threads start on first use and the pool lives as long as the service. With one
        # read per venue in flight at most, it never needs more workers than venues.
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(MAX_WORKERS, len(self.adapters))),
            thread_name_prefix="screenings",
        )

    def listings(self, *, days: int = LISTING_DAYS) -> dict[str, Any]:
        now_ts = self.clock()
        now = datetime.fromtimestamp(now_ts, SINGAPORE)
        today = now.date()
        span = max(1, min(days, LISTING_DAYS))
        last_day = today + timedelta(days=span - 1)
        refreshing = {
            adapter.venue.id: self._refresh_in_background(adapter, today)
            for adapter in self.adapters
            if self._due(adapter, now_ts)
        }
        if refreshing:
            wait(list(refreshing.values()), timeout=self.deadline_seconds)

        statuses: list[dict[str, Any]] = []
        screenings: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        cutoff = now - timedelta(minutes=30)
        first, last = today.isoformat(), last_day.isoformat()
        for adapter in self.adapters:
            future = refreshing.get(adapter.venue.id)
            status, items = self._current(adapter, self.clock(), future is not None and not future.done())
            link_hosts = frozenset(getattr(adapter, "link_hosts", ()))
            poster_hosts = frozenset(getattr(adapter, "poster_hosts", ()))
            kept = 0
            for item in items:
                if not first <= item.date <= last:
                    continue
                if item.starts_at and datetime.fromisoformat(item.starts_at) < cutoff:
                    continue
                key = (item.source, item.venue, item.title.casefold(), item.starts_at or item.date)
                if key in seen:
                    continue
                seen.add(key)
                entry = item.model_dump()
                entry["url"] = item.url if item.url and host_allowed(item.url, link_hosts) else None
                entry["poster"] = self.posters.register(item.poster, poster_hosts)
                screenings.append(entry)
                kept += 1
            update: dict[str, Any] = {"coverage_days": self._coverage(adapter, span)}
            if status.state == "ok":
                update.update(state="ok" if kept else "empty", count=kept)
            statuses.append(status.model_copy(update=update).model_dump())

        screenings.sort(key=lambda item: (item["starts_at"] or f"{item['date']}T99", item["title"].casefold()))
        return {
            "generated_at": now.isoformat(timespec="seconds"),
            "timezone": "Asia/Singapore",
            "range": {"from": first, "to": last},
            "sources": statuses,
            "screenings": screenings,
        }

    @staticmethod
    def _coverage(adapter: ScreeningAdapter, span: int) -> int | None:
        if isinstance(adapter, UnlistedVenue):
            return None
        return min(int(getattr(adapter, "coverage_days", LISTING_DAYS)), span)

    def _due(self, adapter: ScreeningAdapter, now: float) -> bool:
        if isinstance(adapter, UnlistedVenue):
            return False
        with self._lock:
            entry = self._cache.get(adapter.venue.id)
        return entry is None or entry.expires <= now

    def _refresh_in_background(self, adapter: ScreeningAdapter, today: date) -> Future[None]:
        venue_id = adapter.venue.id
        with self._lock:
            future = self._inflight.get(venue_id)
            if future is None or future.done():
                future = self._executor.submit(self._refresh, adapter, today)
                self._inflight[venue_id] = future
        return future

    def _current(
        self, adapter: ScreeningAdapter, now: float, pending: bool
    ) -> tuple[SourceStatus, tuple[Screening, ...]]:
        if isinstance(adapter, UnlistedVenue):
            return self._status(adapter, now, "unlisted", message=adapter.notice), ()
        with self._lock:
            entry = self._cache.get(adapter.venue.id)
        if entry is not None and not pending:
            return entry.status, entry.items
        # Still being read after the deadline: earlier listings stand in, marked stale.
        if entry is not None and entry.items and self._recent(entry, now):
            status = entry.status.model_copy(update={"stale": True, "message": SLOW_MESSAGE})
            return status, entry.items
        return self._status(adapter, now, "error", message=SLOW_MESSAGE), ()

    @staticmethod
    def _recent(entry: _Entry, now: float) -> bool:
        return entry.read_at is not None and now - entry.read_at <= STALE_SECONDS

    def _refresh(self, adapter: ScreeningAdapter, today: date) -> None:
        venue_id = adapter.venue.id
        with self._venue_locks[venue_id]:
            now = self.clock()
            with self._lock:
                previous = self._cache.get(venue_id)
            if previous is not None and previous.expires > now:
                return  # Another read finished first.
            try:
                result = adapter.fetch(today)
                if isinstance(result, Fetched):
                    items, lifetime = list(result.items), result.cache_seconds
                else:
                    items, lifetime = list(result), int(getattr(adapter, "cache_seconds", CACHE_SECONDS))
                state: SourceState = "ok" if items else "empty"
                entry = _Entry(
                    expires=now + lifetime,
                    read_at=now,
                    status=self._status(adapter, now, state, count=len(items)),
                    items=tuple(items),
                )
            except Exception as exc:  # A parser bug in one adapter must not break the listing.
                log_source_failure(venue_id, exc)
                message = str(exc) if isinstance(exc, ScreeningError) else CHANGED_MESSAGE
                if previous is not None and previous.items and self._recent(previous, now):
                    status = previous.status.model_copy(
                        update={"stale": True, "message": f"{message} {STALE_SUFFIX}"})
                    entry = _Entry(now + FAILURE_CACHE_SECONDS, previous.read_at, status, previous.items)
                else:
                    status = self._status(adapter, now, "error", message=message)
                    entry = _Entry(now + FAILURE_CACHE_SECONDS, None, status, ())
            with self._lock:
                self._cache[venue_id] = entry

    @staticmethod
    def _status(
        adapter: ScreeningAdapter,
        now: float,
        state: SourceState,
        *,
        count: int = 0,
        message: str | None = None,
    ) -> SourceStatus:
        venue: Venue = adapter.venue
        return SourceStatus(
            id=venue.id,
            name=venue.name,
            kind=venue.kind,
            url=venue.url,
            state=state,
            count=count,
            fetched_at=datetime.fromtimestamp(now, SINGAPORE).isoformat(timespec="seconds"),
            message=message,
        )


def default_adapters() -> list[ScreeningAdapter]:
    return [
        AsianFilmArchiveAdapter(),
        FilmhouseAdapter(),
        AllianceFrancaiseAdapter(),
        ShawTheatresAdapter(),
        SgiffAdapter(),
        PeatixScreeningsAdapter(),
        UnlistedVenue(
            Venue("gv", "Golden Village", "multiplex", "https://www.gv.com.sg/"),
            "its website blocks automated reading, so check gv.com.sg",
        ),
        UnlistedVenue(
            Venue("artscience", "ArtScience Cinema", "museum",
                  "https://www.marinabaysands.com/museum/experiences/cinema.html"),
            "closed from 1 September 2026, according to the venue",
        ),
    ]
