"""Venue adapters that turn one operator's public listings into ``Screening`` items.

Each adapter reads only its own allow-listed HTTPS hosts and keeps booking links and
poster URLs only when they point at hosts it expects. SGIFF lives in
``screenings_sgiff`` because its two-stage read needs its own worker pool.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable

from app.backend.screenings_http import ScreeningError, request_json, request_text, require_host
from app.backend.screenings_model import (
    CACHE_SECONDS,
    Screening,
    Venue,
    clean_text,
    combine,
    infer_day,
    parse_clock,
    safe_url,
    screening_at,
)

Transport = Callable[[str], Any]


class AsianFilmArchiveAdapter:
    """Oldham Theatre screenings from the Asian Film Archive's public WordPress events API."""

    venue = Venue("afa", "Asian Film Archive", "cinematheque", "https://asianfilmarchive.org/event-calendar/")
    cache_seconds = CACHE_SECONDS
    events_url = (
        "https://asianfilmarchive.org/wp-json/wp/v2/mep_events?per_page=100&orderby=modified"
        "&order=desc&_fields=id,link,title,event_informations,_links,_embedded"
        "&_embed=wp:featuredmedia"
    )
    hosts = frozenset({"asianfilmarchive.org", "www.asianfilmarchive.org"})
    link_hosts = hosts
    poster_hosts = hosts

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport or (lambda url: request_json(url, allowed_hosts=self.hosts))

    def fetch(self, today: date) -> list[Screening]:
        events = self.transport(self.events_url)
        if not isinstance(events, list):
            raise ScreeningError("The Asian Film Archive returned an unexpected event list.")
        screenings: list[Screening] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            info = event.get("event_informations")
            info = info if isinstance(info, dict) else {}
            try:
                starts = datetime.strptime(self._first(info, "event_start_datetime"), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            # Programme umbrella posts are dated at midnight; individual screenings are not.
            if starts.hour == 0 and starts.minute == 0:
                continue
            rendered = event.get("title")
            title = clean_text(rendered.get("rendered") if isinstance(rendered, dict) else "", 200)
            sold_out = "[SOLD OUT]" in title.upper()
            title = re.sub(r"\s*\[sold out\]\s*", " ", title, flags=re.IGNORECASE).strip()
            item = screening_at(
                title=title,
                venue=self.venue,
                location=f"{self.venue.name} · {self._first(info, 'mep_location_venue') or 'Oldham Theatre'}",
                starts_at=starts,
                url=safe_url(self._first(info, "booking_url"), self.link_hosts)
                or safe_url(event.get("link"), self.link_hosts),
                poster=self._image(event),
                details="Sold out" if sold_out else None,
            )
            if item:
                screenings.append(item)
        return screenings

    @staticmethod
    def _first(info: dict[str, Any], key: str) -> str:
        value = info.get(key)
        return str(value[0] if isinstance(value, list) and value else value or "")

    def _image(self, event: dict[str, Any]) -> str | None:
        embedded = event.get("_embedded")
        media = embedded.get("wp:featuredmedia") if isinstance(embedded, dict) else None
        if not isinstance(media, list) or not media or not isinstance(media[0], dict):
            return None
        details = media[0].get("media_details")
        sizes = details.get("sizes") if isinstance(details, dict) else None
        medium = sizes.get("medium") if isinstance(sizes, dict) else None
        url = medium.get("source_url") if isinstance(medium, dict) else media[0].get("source_url")
        return safe_url(url, self.poster_hosts)


class ShawTheatresAdapter:
    """Shaw Theatres sessions from the JSON its own website requests for each day.

    The listing covers 14 days, but Shaw is read for seven to bound the load on its
    per-day endpoint; the source status says so through ``coverage_days``.
    """

    venue = Venue("shaw", "Shaw Theatres", "multiplex", "https://shaw.sg/")
    cache_seconds = 3 * 60 * 60
    coverage_days = 7
    hosts = frozenset({"shaw.sg", "www.shaw.sg"})
    link_hosts = hosts
    poster_hosts = hosts | {"snow-shaw-cdn.azureedge.net"}
    locations_url = "https://shaw.sg/internal/get_simple_locations"
    showtimes_url = (
        "https://shaw.sg/internal/get_show_times?date={day}&movieId=0&locationId=0&promotionId=0"
    )

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport or self._request

    def _request(self, url: str) -> Any:
        # Shaw's own pages send this header to reach its showtime API. It goes only to the
        # shaw.sg hosts: the guarded opener refuses any other host, redirects included.
        require_host(url, self.hosts)
        return request_json(url, allowed_hosts=self.hosts, headers={"x-api-forward-to": "internal"})

    def fetch(self, today: date) -> list[Screening]:
        locations = self.transport(self.locations_url)
        names = {
            item.get("id"): clean_text(item.get("name"), 80)
            for item in locations if isinstance(item, dict)
        } if isinstance(locations, list) else {}
        screenings: list[Screening] = []
        for offset in range(self.coverage_days):
            day = today + timedelta(days=offset)
            try:
                films = self.transport(self.showtimes_url.format(day=day.isoformat()))
                if not isinstance(films, list):
                    raise ScreeningError("Shaw Theatres returned an unexpected showtime list.")
            except ScreeningError:
                # Today's sessions decide whether the source works; a later day that fails
                # is skipped and read again on the next refresh.
                if offset == 0:
                    raise
                continue
            screenings.extend(self._sessions(films, names))
        return screenings

    def _sessions(self, films: list[Any], names: dict[Any, str]) -> list[Screening]:
        screenings: list[Screening] = []
        for film in films:
            if not isinstance(film, dict):
                continue
            release = film.get("movieReleaseId")
            film_url = f"https://shaw.sg/movie-details/{release}" if isinstance(release, int) else None
            poster = safe_url(film.get("posterUrl"), self.poster_hosts)
            rating = clean_text(film.get("classifyCode"), 12)
            sessions = film.get("showTimes")
            for session in sessions if isinstance(sessions, list) else []:
                if not isinstance(session, dict):
                    continue
                clock = parse_clock(str(session.get("displayTime") or ""))
                try:
                    session_day = date.fromisoformat(str(session.get("displayDate")))
                except ValueError:
                    continue
                if clock is None:
                    continue
                hall = clean_text(session.get("locationVenueName"), 80)
                item = screening_at(
                    title=str(film.get("primaryTitle") or ""),
                    venue=self.venue,
                    location=names.get(session.get("locationId")) or f"Shaw Theatres {hall}".strip(),
                    starts_at=combine(session_day, clock),
                    url=film_url,
                    poster=poster,
                    details=" · ".join(part for part in (rating, hall) if part),
                )
                if item:
                    screenings.append(item)
        return screenings


class FilmhouseAdapter:
    """Filmhouse sessions from its public film listing page (dates carry no year)."""

    venue = Venue("filmhouse", "Filmhouse", "independent", "https://filmhouse.sg/films/")
    cache_seconds = CACHE_SECONDS
    hosts = frozenset({"filmhouse.sg", "www.filmhouse.sg"})
    link_hosts = hosts
    poster_hosts = hosts | {"cdn.taposapp.com"}
    token = re.compile(
        r'<div class="heading">\s*[A-Za-z]+\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>[A-Za-z]+)\s*</div>'
        r'|<a href="(?P<href>[^"]+)" class="film_book_button">.*?<span class="time">(?P<time>[^<]+)</span>',
        re.DOTALL,
    )

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport or (lambda url: request_text(url, allowed_hosts=self.hosts))

    def fetch(self, today: date) -> list[Screening]:
        page = self.transport(self.venue.url)
        blocks = page.split('<div class="jacro-event ')[1:]
        if not blocks and "jacrofilm-list" not in page:
            raise ScreeningError("Filmhouse's film listing changed shape.")
        screenings: list[Screening] = []
        for block in blocks:
            title_match = re.search(r'class="liveeventtitle"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not title_match:
                continue
            film_link = re.search(r'class="liveeventtitle" href="([^"]+)"', block)
            film_url = safe_url(
                film_link.group(1).replace("http://", "https://", 1) if film_link else None,
                self.link_hosts,
            )
            poster = re.search(r'<div class="film_img">.*?<img[^>]+src="([^"]+)"', block, re.DOTALL)
            director = re.search(r"<span>(Directed by [^<]+)</span>", block)
            current: date | None = None
            for match in self.token.finditer(block):
                if match.group("day"):
                    current = infer_day(int(match.group("day")), match.group("month"), today)
                    continue
                clock = parse_clock(match.group("time") or "")
                if current is None or clock is None:
                    continue
                item = screening_at(
                    title=title_match.group(1),
                    venue=self.venue,
                    location="Filmhouse · Golden Mile Tower",
                    starts_at=combine(current, clock),
                    url=safe_url(match.group("href"), self.link_hosts) or film_url,
                    poster=safe_url(poster.group(1), self.poster_hosts) if poster else None,
                    details=director.group(1).replace("|", ", ") if director else None,
                )
                if item:
                    screenings.append(item)
        return screenings


class AllianceFrancaiseAdapter:
    """Film screenings from Alliance Française de Singapour's public events page.

    The page is cut into one block per card, from each card's title link to the next,
    so a card without a date can never borrow the next card's, and every search runs
    over a bounded block rather than the rest of the page.
    """

    venue = Venue(
        "alliance-francaise", "Alliance Française de Singapour", "cultural",
        "https://alliancefrancaise.org.sg/events?tag=1",
    )
    cache_seconds = CACHE_SECONDS
    hosts = frozenset({"alliancefrancaise.org.sg"})
    link_hosts = hosts
    poster_hosts = hosts
    block_limit = 8_000
    title_link = re.compile(r'<a href="(?P<href>/events/[^"<>\s]{1,300}/register)">\s*<h4[^>]*>')
    original_title = re.compile(r"\s*</a>\s*<h5[^>]*>(.{0,400}?)</h5>", re.DOTALL)
    start_date = re.compile(r'<span itemprop="startDate">([^<]{1,200})</span>')

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport or (lambda url: request_text(url, allowed_hosts=self.hosts))

    def fetch(self, today: date) -> list[Screening]:
        page = self.transport(self.venue.url)
        links = list(self.title_link.finditer(page))
        screenings: list[Screening] = []
        for index, link in enumerate(links):
            end = links[index + 1].start() if index + 1 < len(links) else len(page)
            block = page[link.end():min(end, link.end() + self.block_limit)]
            if item := self._card(link.group("href"), block, today):
                screenings.append(item)
        return screenings

    def _card(self, href: str, block: str, today: date) -> Screening | None:
        title_end = block.find("</h4>")
        when = self.start_date.search(block)
        if title_end < 0 or not when:
            return None
        day_match = re.search(r"(\d{1,2})\s+([A-Za-z]+)", when.group(1))
        clock = parse_clock(when.group(1))
        day = infer_day(int(day_match.group(1)), day_match.group(2), today) if day_match else None
        if day is None or clock is None:
            return None
        original = self.original_title.match(block, title_end + len("</h4>"))
        event_id = re.search(r"-(\d+)/register$", href)
        title = clean_text(block[:title_end], 160)
        return screening_at(
            title=title.title() if title.isupper() else title,
            venue=self.venue,
            location="Alliance Française · Theatre",
            starts_at=combine(day, clock),
            url=safe_url(href, self.link_hosts, "https://alliancefrancaise.org.sg/"),
            poster=f"https://alliancefrancaise.org.sg/event/image/{event_id.group(1)}/small_pic"
            if event_id else None,
            details=clean_text(original.group(1), 120) or None if original else None,
        )


@dataclass(frozen=True)
class PeatixOrganiser:
    id: int
    name: str
    query: str


class PeatixScreeningsAdapter:
    """Film screenings by allow-listed Singapore organisers who sell tickets on Peatix.

    Peatix's own search page requests these results as JSON. They are read with
    FirstRoll's own user agent, one request per organiser, at the pace robots.txt asks
    for. Only named organisers are kept, and only events that look like screenings.
    """

    venue = Venue("peatix", "Objectifs (via Peatix)", "independent", "https://peatix.com/group/12256")
    cache_seconds = 3 * 60 * 60
    hosts = frozenset({"peatix.com"})
    link_hosts = hosts
    poster_hosts = frozenset({"cdn.peatix.com"})
    search_url = "https://peatix.com/search/events?q={query}&country=SG&p=1&size=50"
    organisers = (PeatixOrganiser(474137, "Objectifs", "objectifs"),)
    crawl_delay = 1.0
    screening = re.compile(r"\b(?:osff|screenings?|films?|shorts|cinema|movie|premiere)\b", re.IGNORECASE)
    not_screening = re.compile(
        r"\b(?:workshops?|class|masterclass|photo ?walk|talk|course|exhibition)\b", re.IGNORECASE)

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.transport = transport or (lambda url: request_json(
            url, allowed_hosts=self.hosts, headers={"X-Requested-With": "XMLHttpRequest"}))
        self.sleep = sleep

    def fetch(self, today: date) -> list[Screening]:
        screenings: list[Screening] = []
        for index, organiser in enumerate(self.organisers):
            if index:
                self.sleep(self.crawl_delay)
            payload = self.transport(self.search_url.format(query=organiser.query))
            data = payload.get("json_data") if isinstance(payload, dict) else None
            events = data.get("events") if isinstance(data, dict) else None
            if not isinstance(events, list):
                raise ScreeningError("Peatix returned an unexpected event list.")
            for event in events:
                if isinstance(event, dict) and (item := self._screening(event, organiser)):
                    screenings.append(item)
        return screenings

    def _screening(self, event: dict[str, Any], organiser: PeatixOrganiser) -> Screening | None:
        host = event.get("organizer")
        if not isinstance(host, dict) or host.get("id") != organiser.id:
            return None
        name = clean_text(event.get("name"), 200)
        # Multi-day listings are festival passes or runs rather than a single screening.
        if not self.screening.search(name) or self.not_screening.search(name) or event.get("days", 1) != 1:
            return None
        try:
            starts = datetime.strptime(str(event.get("datetime")), "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            return None
        if starts.utcoffset() != timedelta(hours=8):
            return None
        programme, _, title = name.rpartition(" | ")
        event_id = event.get("id")
        return screening_at(
            title=title or name,
            venue=self.venue,
            location=clean_text(event.get("venue_name"), 120) or organiser.name,
            starts_at=starts,
            url=f"https://peatix.com/event/{event_id}" if isinstance(event_id, int) else None,
            poster=safe_url(event.get("cover"), self.poster_hosts),
            details=" · ".join(part for part in (organiser.name, programme) if part),
        )


@dataclass(frozen=True)
class UnlistedVenue:
    """A venue shown in the source list with a reason its times are not read."""

    venue: Venue
    notice: str
    cache_seconds: int = CACHE_SECONDS

    def fetch(self, today: date) -> list[Screening]:
        return []
