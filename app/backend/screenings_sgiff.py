"""Singapore International Film Festival screenings from its public programme pages."""

from __future__ import annotations

import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable

from app.backend.screenings_http import ScreeningError, log_source_failure, request_text
from app.backend.screenings_model import (
    LISTING_DAYS,
    Fetched,
    Screening,
    Venue,
    clean_text,
    combine,
    festival_day,
    parse_clock,
    safe_url,
    screening_at,
)

Transport = Callable[[str], Any]


@dataclass(frozen=True)
class FestivalSession:
    starts_at: datetime
    location: str | None
    notes: tuple[str, ...] = ()
    minutes: int | None = None
    sold_out: bool = False


@dataclass(frozen=True)
class FestivalFilm:
    url: str
    title: str
    poster: str | None
    section: str | None
    credits: str | None
    sessions: tuple[FestivalSession, ...]


class SgiffAdapter:
    """Every SGIFF film, with per-screening detail while the festival is in range.

    The explore page lists every film with its dates, times and venues, so one request
    gives a complete listing. While the festival falls inside the listing range, film
    pages add per-screening venues, running times and sold-out notices. They are read by
    one long-lived pool of four workers within a time budget; films not reached in time
    keep the explore page's sessions, and the shorter cache lifetime returned with the
    result brings the next refresh round soon after to fill them in from the page cache.
    """

    venue = Venue("sgiff", "Singapore International Film Festival", "festival",
                  "https://sgiff.com/explore-films/")
    hosts = frozenset({"sgiff.com", "www.sgiff.com"})
    link_hosts = hosts
    poster_hosts = hosts
    cache_seconds = 12 * 60 * 60
    complete_cache_seconds = 12 * 60 * 60
    partial_cache_seconds = 10 * 60
    workers = 4
    budget_seconds = 12.0
    max_pages = 500
    film_link = re.compile(r'href="(https://sgiff\.com/film/[a-z0-9-]+/)"')
    when = re.compile(
        r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3,9}),?\s+(?P<weekday>[A-Za-z]{3,9})\.?\s+"
        r"(?P<clock>\d{1,2}(?::\d{2})?\s*[AaPp]\.?[Mm]\.?)"
    )

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport or (lambda url: request_text(url, allowed_hosts=self.hosts))
        self.clock = clock
        self._pages: dict[str, tuple[float, tuple[FestivalSession, ...]]] = {}
        self._reading: dict[str, Future[None]] = {}
        self._pool: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()

    def fetch(self, today: date) -> Fetched:
        page = self.transport(self.venue.url)
        start = page.find('class="c__explorefilms"')
        if start < 0:
            raise ScreeningError("SGIFF's film listing changed shape.")
        cards = page[start:].split('<div class="s_item" ')[1:]
        films = [film for card in cards if (film := self._card(card, today))]
        last_day = today + timedelta(days=LISTING_DAYS - 1)
        current = [film for film in films if any(
            today <= session.starts_at.date() <= last_day for session in film.sessions)]
        detailed, complete = self._film_pages([film.url for film in current], today)

        screenings: list[Screening] = []
        for film in films:
            for session in detailed.get(film.url) or film.sessions:
                notes = [*session.notes] or [film.section or ""]
                credits = film.credits or (f"{session.minutes} min" if session.minutes else "")
                info = clean_text(" · ".join(part for part in (*notes, credits) if part), 140)
                item = screening_at(
                    title=film.title,
                    venue=self.venue,
                    location=f"SGIFF · {session.location}" if session.location else "SGIFF",
                    starts_at=session.starts_at,
                    url=film.url,
                    poster=film.poster,
                    details=" · ".join(part for part in (info, "Sold out" if session.sold_out else "")
                                       if part),
                )
                if item:
                    screenings.append(item)
        lifetime = self.complete_cache_seconds if complete else self.partial_cache_seconds
        return Fetched(items=screenings, cache_seconds=lifetime)

    def _card(self, card: str, today: date) -> FestivalFilm | None:
        link = self.film_link.search(card)
        title = re.search(r"<h3>\s*<a [^>]*>(.*?)</a>", card, re.DOTALL)
        if not link or not title:
            return None
        listed = re.search(r'data-venue="([^"]*)"', card)
        venues = [clean_text(name, 120) for name in (listed.group(1) if listed else "").split(" / ")]
        times = [clean_text(value) for value in
                 re.findall(r'<div class="s_date_wrap">.*?<p>(.*?)</p>', card, re.DOTALL)]
        sessions: list[FestivalSession] = []
        for index, value in enumerate(times):
            starts = self._starts(value, today)
            if starts is None:
                continue
            # Venues are listed once each, so they pair with times only when the counts agree.
            location = venues[index] if len(venues) == len(times) else (
                venues[0] if len(venues) == 1 else None)
            sessions.append(FestivalSession(starts_at=starts, location=location or None))
        poster = re.search(r'<figure>\s*<a [^>]*>\s*<img src="([^"]+)"', card)
        section = re.search(r"<label><a [^>]*>(.*?)</a></label>", card, re.DOTALL)
        credits = re.search(r"</div>\s*<p>(.*?)</p>\s*</div>\s*<div class=\"s_content\">", card, re.DOTALL)
        return FestivalFilm(
            url=link.group(1),
            title=clean_text(title.group(1), 160),
            poster=safe_url(poster.group(1), self.poster_hosts) if poster else None,
            section=clean_text(section.group(1), 80) or None if section else None,
            credits=clean_text(credits.group(1), 100) or None if credits else None,
            sessions=tuple(sessions),
        )

    def _starts(self, value: str, today: date) -> datetime | None:
        match = self.when.search(value)
        if not match:
            return None
        day = festival_day(int(match.group("day")), match.group("month"), match.group("weekday"), today)
        clock = parse_clock(match.group("clock"))
        return combine(day, clock) if day and clock else None

    def _executor(self) -> ThreadPoolExecutor:
        # Called with the lock held. The pool is created once and kept for the process.
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="sgiff")
        return self._pool

    def _film_pages(
        self, urls: list[str], today: date
    ) -> tuple[dict[str, tuple[FestivalSession, ...]], bool]:
        now = self.clock()
        with self._lock:
            for url in [url for url, (expires, _) in self._pages.items() if expires <= now]:
                del self._pages[url]
            for url in [url for url, future in self._reading.items() if future.done()]:
                del self._reading[url]
            found = {url: self._pages[url][1] for url in urls if url in self._pages}
            missing = [url for url in urls if url not in found]
            if not missing:
                return found, True
            futures: list[Future[None]] = []
            for url in missing:
                future = self._reading.get(url)
                if future is None:
                    future = self._executor().submit(self._read, url, today)
                    self._reading[url] = future
                futures.append(future)

        # Pages still loading when the budget runs out finish in the background and land
        # in the page cache for the next request instead of holding this one up. Pages
        # that never started are cancelled, so the pool's queue stays bounded.
        _, unfinished = wait(futures, timeout=self.budget_seconds)
        for future in unfinished:
            future.cancel()
        with self._lock:
            found.update({url: self._pages[url][1] for url in missing if url in self._pages})
        return found, all(url in found for url in urls)

    def _read(self, url: str, today: date) -> None:
        try:
            sessions = self._sessions(self.transport(url), today)
        except Exception as exc:  # One film page must never break the festival listing.
            log_source_failure(f"{self.venue.id} film page", exc)
            return
        if not sessions:
            return
        with self._lock:
            self._pages[url] = (self.clock() + self.complete_cache_seconds, sessions)
            if len(self._pages) > self.max_pages:
                for oldest in sorted(self._pages, key=lambda key: self._pages[key][0])[
                        :len(self._pages) - self.max_pages]:
                    del self._pages[oldest]

    def _sessions(self, page: str, today: date) -> tuple[FestivalSession, ...]:
        start = page.find('class="c__screeningtimes"')
        if start < 0:
            return ()
        sessions: list[FestivalSession] = []
        for block in re.split(r'<div class="s_screening" ', page[start:])[1:]:
            if not block.startswith("data-screeningid="):
                continue
            block = block.split("eventive-", 1)[0]
            label = re.search(r'<div class="u__label[^"]*">(.*?)</div>', block, re.DOTALL)
            rest = block.replace(label.group(0), "") if label else block
            lines = [clean_text(value) for value in re.findall(r"<p>(.*?)</p>", rest, re.DOTALL)]
            index = next((i for i, line in enumerate(lines) if self.when.search(line)), None)
            if index is None:
                continue
            starts = self._starts(lines[index], today)
            if starts is None:
                continue
            tags = [clean_text(tag, 60) for tag in clean_text(label.group(1)).split(",")] if label else []
            tags = [tag.capitalize() if tag.isupper() and " " in tag else tag for tag in tags]
            minutes = re.search(r"/\s*(\d{1,3})\s*min", lines[index])
            sessions.append(FestivalSession(
                starts_at=starts,
                location=lines[index + 1] if index + 1 < len(lines) and lines[index + 1] else None,
                notes=tuple(tag for tag in tags if tag and tag.casefold() != "sold out"),
                minutes=int(minutes.group(1)) if minutes else None,
                sold_out=any(tag.casefold() == "sold out" for tag in tags),
            ))
        return tuple(sessions)
