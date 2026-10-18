"""Shared shapes and parsing helpers for Singapore screening listings.

Retrieved titles and copy are untrusted data: they are reduced to plain text here and
are only ever rendered as text by the browser.
"""

from __future__ import annotations

import html
import re
import string
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Protocol
from urllib.parse import quote, urljoin

from pydantic import BaseModel, ConfigDict

from app.backend.screenings_http import host_allowed

# Singapore has observed UTC+8 without daylight saving since 1982.
SINGAPORE = timezone(timedelta(hours=8), "SGT")
LISTING_DAYS = 14
CACHE_SECONDS = 60 * 60
FAILURE_CACHE_SECONDS = 5 * 60

VenueKind = Literal["multiplex", "independent", "cinematheque", "museum", "cultural", "festival"]
SourceState = Literal["ok", "empty", "error", "unlisted"]


class Screening(BaseModel):
    """One session. Inside the service ``poster`` is the venue's image URL; the API
    replaces it with FirstRoll's own proxy path before anything leaves the server."""

    model_config = ConfigDict(extra="forbid")

    title: str
    venue: str
    source: str
    starts_at: str | None = None
    date: str
    url: str | None = None
    poster: str | None = None
    details: str | None = None


class SourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: VenueKind
    url: str
    state: SourceState
    count: int = 0
    fetched_at: str
    message: str | None = None
    # Days ahead this source is read for, which can be shorter than the listing range.
    coverage_days: int | None = None
    # True when earlier listings stand in for a refresh that failed or is still running.
    stale: bool = False


@dataclass(frozen=True)
class Venue:
    id: str
    name: str
    kind: VenueKind
    url: str


@dataclass(frozen=True)
class Fetched:
    """Listings with the cache lifetime that suits how completely they were read."""

    items: list[Screening]
    cache_seconds: int


class ScreeningAdapter(Protocol):
    """One venue's reader. Adapters may also declare ``coverage_days`` (default: the
    whole listing range), ``link_hosts`` and ``poster_hosts`` (default: none allowed)."""

    @property
    def venue(self) -> Venue: ...

    @property
    def cache_seconds(self) -> int: ...

    def fetch(self, today: date) -> list[Screening] | Fetched: ...


def clean_text(value: Any, limit: int = 240) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def safe_url(value: Any, hosts: frozenset[str] | set[str], base: str | None = None) -> str | None:
    """An HTTPS URL on one of ``hosts``, resolved against ``base``; anything else is dropped.

    Non-ASCII characters, spaces and control characters are percent-encoded, as the standard
    library does for redirect targets, so a poster such as ``Café.jpg`` can be requested.
    ASCII punctuation, including existing ``%XX`` escapes, is left as it is.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    resolved = quote(urljoin(base, raw) if base else raw, safe=string.punctuation)
    return resolved if host_allowed(resolved, hosts) else None


def to_singapore(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=SINGAPORE)
    return moment.astimezone(SINGAPORE)


def screening_at(
    *,
    title: str,
    venue: Venue,
    location: str | None = None,
    starts_at: datetime | None = None,
    on: date | None = None,
    url: str | None = None,
    poster: str | None = None,
    details: str | None = None,
) -> Screening | None:
    name = clean_text(title, 160)
    if not name or (starts_at is None and on is None):
        return None
    moment = to_singapore(starts_at) if starts_at else None
    day = moment.date() if moment else on
    return Screening(
        title=name,
        venue=clean_text(location, 120) or venue.name,
        source=venue.id,
        starts_at=moment.isoformat(timespec="minutes") if moment else None,
        date=day.isoformat(),  # type: ignore[union-attr]
        url=url,
        poster=poster,
        details=clean_text(details, 160) or None,
    )


MONTH_NUMBERS = {
    name: number
    for number, names in enumerate(
        [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
         ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
         ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
         ("dec", "december")],
        start=1,
    )
    for name in names
}
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def infer_day(day: int, month_name: str, today: date) -> date | None:
    """Resolve a year-less listing date to the nearest plausible future occurrence."""
    month = MONTH_NUMBERS.get(month_name.casefold())
    if not month:
        return None
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue  # 29 February exists only in leap years.
        if candidate >= today - timedelta(days=60):
            return candidate
    return None


def festival_day(day: int, month_name: str, weekday: str, today: date) -> date | None:
    """Resolve a year-less date whose printed weekday pins down the year."""
    month = MONTH_NUMBERS.get(month_name.casefold())
    expected = WEEKDAYS.index(weekday[:3].casefold()) if weekday[:3].casefold() in WEEKDAYS else -1
    if not month or expected < 0:
        return None
    candidates: list[date] = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue  # 29 February exists only in leap years.
        if candidate.weekday() == expected:
            candidates.append(candidate)
    return min(candidates, key=lambda candidate: abs((candidate - today).days), default=None)


def parse_clock(value: str) -> tuple[int, int] | None:
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", value, re.IGNORECASE)
    if not match:
        match = re.search(r"\b(\d{1,2}):(\d{2})\b", value)
        if not match:
            return None
        hour, minute = int(match.group(1)), int(match.group(2))
    else:
        hour, minute = int(match.group(1)) % 12, int(match.group(2) or 0)
        if match.group(3).casefold() == "p":
            hour += 12
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def combine(day: date, clock: tuple[int, int]) -> datetime:
    return datetime(day.year, day.month, day.day, clock[0], clock[1], tzinfo=SINGAPORE)
