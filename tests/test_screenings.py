import asyncio
import json
import logging
import threading
import time
from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.backend import main, screenings, screenings_sgiff, screenings_venues
from app.backend.screenings import SLOW_MESSAGE, STALE_SECONDS, ScreeningsService
from app.backend.screenings_api import LISTING_THREADS, accepts_gzip, add_screenings_routes
from app.backend.screenings_http import ScreeningError
from app.backend.screenings_model import (
    FAILURE_CACHE_SECONDS,
    SINGAPORE,
    Fetched,
    Venue,
    festival_day,
    infer_day,
    parse_clock,
    screening_at,
)
from app.backend.screenings_posters import PosterProxy
from app.backend.screenings_sgiff import SgiffAdapter
from app.backend.screenings_venues import (
    AllianceFrancaiseAdapter,
    AsianFilmArchiveAdapter,
    FilmhouseAdapter,
    PeatixOrganiser,
    PeatixScreeningsAdapter,
    ShawTheatresAdapter,
    UnlistedVenue,
)

TODAY = date(2026, 10, 16)
NOON = datetime(2026, 10, 16, 12, 0, tzinfo=SINGAPORE).timestamp()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def afa_event(title: str, starts: str, venue: str = "Oldham Theatre") -> dict:
    return {
        "id": 1,
        "link": "https://asianfilmarchive.org/event-calendar/example/",
        "title": {"rendered": title},
        "event_informations": {
            "event_start_datetime": [starts],
            "mep_location_venue": [venue],
            "booking_url": [""],
            "mep_reg_email": ["ignored@example.com"],
        },
        "_embedded": {"wp:featuredmedia": [{
            "source_url": "https://asianfilmarchive.org/wp-content/uploads/full.jpg",
            "media_details": {"sizes": {"medium": {
                "source_url": "https://asianfilmarchive.org/wp-content/uploads/medium.jpg"}}},
        }]},
    }


def test_clock_and_year_less_dates_resolve_in_singapore() -> None:
    assert parse_clock("7:15 pm") == (19, 15)
    assert parse_clock("12:00 AM") == (0, 0)
    assert parse_clock("Thursday 22 October 07:00 PM") == (19, 0)
    assert parse_clock("no time") is None
    assert infer_day(17, "October", TODAY) == date(2026, 10, 17)
    assert infer_day(3, "Jan", TODAY) == date(2027, 1, 3)
    assert infer_day(31, "February", TODAY) is None


def test_asian_film_archive_skips_programme_posts_and_marks_sold_out() -> None:
    off_list = afa_event("Elsewhere (2020)", "2026-10-19 19:30:00")
    off_list["event_informations"]["booking_url"] = ["https://tickets.example/afa"]
    off_list["_embedded"]["wp:featuredmedia"][0]["media_details"]["sizes"]["medium"]["source_url"] = (
        "https://images.example/poster.jpg")
    events = [
        afa_event("The Kiss (くちづけ, 1957) [SOLD OUT]", "2026-10-17 17:00:00"),
        afa_event("Off the Catalogue: November 2026", "2026-11-04 00:00:00"),
        afa_event("Darah-ku (My Blood, 1963)", "2026-10-18 19:30:00", venue=""),
        {"title": {"rendered": "Broken"}, "event_informations": {}},
        off_list,
    ]
    items = AsianFilmArchiveAdapter(transport=lambda url: events).fetch(TODAY)

    assert [item.title for item in items] == [
        "The Kiss (くちづけ, 1957)", "Darah-ku (My Blood, 1963)", "Elsewhere (2020)"]
    assert items[0].starts_at == "2026-10-17T17:00+08:00"
    assert items[0].details == "Sold out"
    assert items[0].venue == "Asian Film Archive · Oldham Theatre"
    assert items[0].poster == "https://asianfilmarchive.org/wp-content/uploads/medium.jpg"
    assert items[1].venue == "Asian Film Archive · Oldham Theatre"
    assert "ignored@example.com" not in str([item.model_dump() for item in items])
    # Off-list booking and image hosts are dropped; the event's own page stands in.
    assert items[2].url == "https://asianfilmarchive.org/event-calendar/example/"
    assert items[2].poster is None


def shaw_film(day: str, title: str = "Crawlers") -> dict:
    return {
        "movieReleaseId": 1811, "primaryTitle": title, "classifyCode": "NC16",
        "posterUrl": "https://snow-shaw-cdn.azureedge.net/poster",
        "showTimes": [
            {"displayDate": day, "displayTime": "6:00 PM", "locationId": 4,
             "locationVenueName": "Lot One Hall 7"},
            {"displayDate": day, "displayTime": "bad", "locationId": 4},
        ],
    }


def test_shaw_groups_halls_under_named_cinemas() -> None:
    def transport(url: str):
        if "get_simple_locations" in url:
            return [{"id": 4, "name": "Shaw Theatres Lot One"}]
        if "date=2026-10-16" in url:
            return [shaw_film("2026-10-16")]
        return []

    items = ShawTheatresAdapter(transport=transport).fetch(TODAY)

    assert len(items) == 1
    assert items[0].venue == "Shaw Theatres Lot One"
    assert items[0].starts_at == "2026-10-16T18:00+08:00"
    assert items[0].url == "https://shaw.sg/movie-details/1811"
    assert items[0].poster == "https://snow-shaw-cdn.azureedge.net/poster"
    assert items[0].details == "NC16 · Lot One Hall 7"


def test_shaw_first_day_failure_is_a_source_failure() -> None:
    def failing(url: str):
        raise ScreeningError("Shaw Theatres returned HTTP 503.")

    with pytest.raises(ScreeningError):
        ShawTheatresAdapter(transport=failing).fetch(TODAY)
    with pytest.raises(ScreeningError):  # A malformed first day counts the same way.
        ShawTheatresAdapter(transport=lambda url: {"error": "maintenance"}).fetch(TODAY)


def test_shaw_skips_a_failing_or_malformed_later_day_and_reads_seven_days() -> None:
    requested: list[str] = []

    def transport(url: str):
        requested.append(url)
        if "get_simple_locations" in url:
            return [{"id": 4, "name": "Shaw Theatres Lot One"}]
        if "date=2026-10-17" in url:
            return {"error": "not a list"}
        if "date=2026-10-18" in url:
            raise ScreeningError("The venue website returned HTTP 500.")
        day = url.split("date=")[1][:10]
        return [shaw_film(day)]

    items = ShawTheatresAdapter(transport=transport).fetch(TODAY)

    assert len([url for url in requested if "get_show_times" in url]) == 7
    assert [item.date for item in items] == [
        "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]


def test_shaw_requests_use_the_guarded_helper_and_send_its_header_only_to_shaw(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_request_json(url: str, *, allowed_hosts, headers=None):
        seen.append({"url": url, "hosts": set(allowed_hosts), "headers": headers})
        return []

    monkeypatch.setattr(screenings_venues, "request_json", fake_request_json)
    adapter = ShawTheatresAdapter()
    adapter.fetch(TODAY)

    assert seen and all(call["hosts"] == {"shaw.sg", "www.shaw.sg"} for call in seen)
    assert all(call["headers"] == {"x-api-forward-to": "internal"} for call in seen)
    with pytest.raises(ScreeningError):
        adapter._request("https://shaw.example/internal/get_simple_locations")
    with pytest.raises(ScreeningError):
        adapter._request("http://shaw.sg/internal/get_simple_locations")
    assert len(seen) == 8  # Locations plus seven days; the off-list requests never left.


FILMHOUSE_PAGE = """
<div class="jacrofilm-list">
<div class="jacro-event movie-tabs row 4k">
  <div class="film_img"><a href="http://filmhouse.sg/film/220/fjord">
    <img alt="filmimg" src="https://cdn.taposapp.com/poster/fjord.jpg"></a></div>
  <a class="liveeventtitle" href="http://filmhouse.sg/film/220/fjord">Fjord</a>
  <div class="film-info"><span>Directed by Ervin Han|Raúl García</span></div>
  <ul class="performance-list-items"><div class="heading">Friday 16th October</div>
    <li><a href="https://filmhouse.sg/filmhouse-singapore/booknow/1830" class="film_book_button">
      <span class="hover">Book</span><span class="time">7:15 pm</span></a></li>
    <div class="heading">Tuesday 20th October</div>
    <li><a href="https://tickets.example/booknow/1857" class="film_book_button">
      <span class="hover">Book</span><span class="time">4:15 pm</span></a></li>
  </ul>
</div>
</div>
"""


def test_filmhouse_reads_dated_sessions_with_booking_links() -> None:
    items = FilmhouseAdapter(transport=lambda url: FILMHOUSE_PAGE).fetch(TODAY)

    assert [item.starts_at for item in items] == ["2026-10-16T19:15+08:00", "2026-10-20T16:15+08:00"]
    assert items[0].url == "https://filmhouse.sg/filmhouse-singapore/booknow/1830"
    assert items[1].url == "https://filmhouse.sg/film/220/fjord"  # Off-list booking host dropped.
    assert items[0].poster == "https://cdn.taposapp.com/poster/fjord.jpg"
    assert items[0].details == "Directed by Ervin Han, Raúl García"


def test_filmhouse_redesign_is_reported_not_silently_empty() -> None:
    with pytest.raises(ScreeningError):
        FilmhouseAdapter(transport=lambda url: "<html>new site</html>").fetch(TODAY)


def af_card(slug: str, title: str, when: str | None, original: str | None = None) -> str:
    return (
        f'<div class="card"><a href="/events/{slug}/register">\n  <h4 class="card-title">{title}</h4></a>\n'
        + (f'<h5 class="card-title">{original}</h5>\n' if original else "")
        + (f'<div><span itemprop="startDate">{when}</span></div>' if when else "<div>Date to come</div>")
        + "</div>\n"
    )


def test_alliance_francaise_reads_film_cards() -> None:
    page = af_card("the-money-maker-2026-10-22-5449", "THE MONEY MAKER", "Thursday 22 October 07:00 PM",
                   "L'Affaire Bojarski")
    items = AllianceFrancaiseAdapter(transport=lambda url: page).fetch(TODAY)

    assert len(items) == 1
    assert items[0].title == "The Money Maker"
    assert items[0].details == "L'Affaire Bojarski"
    assert items[0].starts_at == "2026-10-22T19:00+08:00"
    assert items[0].url == "https://alliancefrancaise.org.sg/events/the-money-maker-2026-10-22-5449/register"
    assert items[0].poster == "https://alliancefrancaise.org.sg/event/image/5449/small_pic"


def test_alliance_francaise_card_never_borrows_the_next_cards_date() -> None:
    page = (af_card("undated-2026-10-20-1", "Undated Talk", None)
            + af_card("dated-2026-10-23-2", "Dated Film", "Friday 23 October 08:00 PM"))
    items = AllianceFrancaiseAdapter(transport=lambda url: page).fetch(TODAY)

    assert [(item.title, item.starts_at) for item in items] == [("Dated Film", "2026-10-23T20:00+08:00")]


def test_alliance_francaise_parsing_stays_linear_on_a_large_page() -> None:
    page = "".join(af_card(f"talk-{index}", f"Talk {index}", None) for index in range(6000))
    page += af_card("late-2026-10-24-9", "Late Film", "Saturday 24 October 06:00 PM")

    started = time.perf_counter()
    items = AllianceFrancaiseAdapter(transport=lambda url: page).fetch(TODAY)

    assert [item.title for item in items] == ["Late Film"]
    assert time.perf_counter() - started < 2.0


def sgiff_card(slug: str, title: str, venues: str, times: list[str]) -> str:
    dates = "".join(
        f'<div class="s_date"><div class="s_date_wrap"><figure><img src="icon.svg" alt=""></figure>'
        f"<p>{when}</p></div></div>" for when in times
    )
    return f"""
    <div class="s_item" data-venue="{venues}" data-date="" data-genre="" data-category="Standpoint">
      <figure><a href="https://sgiff.com/film/{slug}/">
        <img src="https://sgiff.com/wp-content/uploads/2026/09/{slug}.jpg"></a></figure>
      <div class="s_content">
        <div class="s_header">
          <label><a href="/festival-programmes/standpoint/">Standpoint</a></label>
          <div class="s_header_bookmark"><h3><a href="https://sgiff.com/film/{slug}/">{title}</a></h3></div>
        </div>
        <p>Morteza Atabaki / Turkey / 2025 / 83 min / PG</p>
      </div>
      <div class="s_content"><p>Logline.</p>{dates}</div>
    </div>"""


SGIFF_EXPLORE = f"""
<div class="s_tablink"><div class="s_item v_active"><a href="https://sgiff.com/explore-films/">Explore</a></div></div>
<section class="c__explorefilms"><div class="s_films">
{sgiff_card("32-meters", "32 Meters", "Oldham Theatre", ["24 Oct, Sat 7:00PM", "1 Nov, Sun 4:30PM"])}
{sgiff_card("burn", "Burn", "Golden Village Cineleisure, Hall 2 / Filmhouse, Redrum",
            ["28 Oct, Wed 5:45PM", "29 Oct, Thu 4:00PM"])}
{sgiff_card("later", "Later", "Oldham Theatre", ["1 Nov, Sun 9:15PM"])}
</div></section>
"""

SGIFF_FILM = """
<div class="u__label"><p>Southeast Asian Premiere</p></div>
<section class="c__screeningtimes"><div><div class="s_screenings">
  <div class="s_screening" data-screeningid="a1">
    <div class="s_screening_info">
      <div class="u__label v_icon"><p><span class="u__iconqna"></span>
        Standpoint, Q&amp;A, SELLING FAST, SOLD OUT</p></div>
      <p>24 Oct, Sat 7:00PM / 83 min</p>
      <p>Oldham Theatre</p>
    </div>
    <div class="eventive-button u__primarybtn" data-event="a1"></div>
  </div>
  <div class="s_screening" data-screeningid="a2">
    <div class="s_screening_info">
      <p>1 Nov, Sun 4:30PM / 83 min</p>
      <p>Golden Village Bugis+, Hall 6</p>
    </div>
  </div>
  <div class="s_passholder_note"><p>Access your pass benefits when checking out.</p></div>
</div></div></section>
"""


def test_festival_day_uses_the_printed_weekday_to_choose_the_year() -> None:
    assert festival_day(24, "Oct", "Sat", TODAY) == date(2026, 10, 24)
    assert festival_day(1, "Nov", "Sunday", TODAY) == date(2026, 11, 1)
    assert festival_day(24, "Oct", "Fri", TODAY) == date(2025, 10, 24)  # Last year's leftover page.
    assert festival_day(24, "Oct", "Noday", TODAY) is None


def test_sgiff_reads_film_pages_for_films_showing_in_range() -> None:
    requested: list[str] = []

    def transport(url: str) -> str:
        requested.append(url)
        return SGIFF_EXPLORE if url.endswith("/explore-films/") else SGIFF_FILM

    adapter = SgiffAdapter(transport=transport)
    result = adapter.fetch(TODAY)
    items = result.items

    # "Later" shows only after the 14-day range, so its film page is never requested.
    assert sorted(requested) == ["https://sgiff.com/explore-films/", "https://sgiff.com/film/32-meters/",
                                 "https://sgiff.com/film/burn/"]
    assert result.cache_seconds == SgiffAdapter.complete_cache_seconds
    meters = [item for item in items if item.title == "32 Meters"]
    assert [(item.starts_at, item.venue) for item in meters] == [
        ("2026-10-24T19:00+08:00", "SGIFF · Oldham Theatre"),
        ("2026-11-01T16:30+08:00", "SGIFF · Golden Village Bugis+, Hall 6"),
    ]
    assert meters[0].details == ("Standpoint · Q&A · Selling fast · Morteza Atabaki / Turkey / 2025 / 83 min / PG"
                                 " · Sold out")
    assert meters[1].details == "Standpoint · Morteza Atabaki / Turkey / 2025 / 83 min / PG"
    assert meters[0].url == "https://sgiff.com/film/32-meters/"
    assert meters[0].poster == "https://sgiff.com/wp-content/uploads/2026/09/32-meters.jpg"
    later = [item for item in items if item.title == "Later"]
    assert [(item.starts_at, item.venue) for item in later] == [("2026-11-01T21:15+08:00", "SGIFF · Oldham Theatre")]

    adapter.fetch(TODAY)
    assert len(requested) == 4  # Film pages come from the page cache on the next refresh.


def test_sgiff_pairs_explore_venues_with_times_when_film_pages_fail() -> None:
    def transport(url: str) -> str:
        if url.endswith("/explore-films/"):
            return SGIFF_EXPLORE
        raise ScreeningError("The venue website returned HTTP 503.")

    result = SgiffAdapter(transport=transport).fetch(TODAY)

    burn = [(item.starts_at, item.venue) for item in result.items if item.title == "Burn"]
    assert burn == [("2026-10-28T17:45+08:00", "SGIFF · Golden Village Cineleisure, Hall 2"),
                    ("2026-10-29T16:00+08:00", "SGIFF · Filmhouse, Redrum")]
    assert len([item for item in result.items if item.title == "32 Meters"]) == 2
    assert result.cache_seconds == SgiffAdapter.partial_cache_seconds


def test_sgiff_reports_partial_results_when_film_pages_are_slow() -> None:
    release = threading.Event()

    def transport(url: str) -> str:
        if url.endswith("/explore-films/"):
            return SGIFF_EXPLORE
        release.wait(5)
        return SGIFF_FILM

    adapter = SgiffAdapter(transport=transport)
    adapter.budget_seconds = 0.05
    try:
        first = adapter.fetch(TODAY)
    finally:
        release.set()

    assert first.cache_seconds == SgiffAdapter.partial_cache_seconds
    assert not any("Sold out" in (item.details or "") for item in first.items)
    assert len([item for item in first.items if item.title == "32 Meters"]) == 2

    for _ in range(100):  # The slow pages finish in the background and fill the cache.
        if len(adapter._pages) == 2:
            break
        threading.Event().wait(0.02)
    second = adapter.fetch(TODAY)
    assert second.cache_seconds == SgiffAdapter.complete_cache_seconds
    assert any("Sold out" in (item.details or "") for item in second.items)


def test_sgiff_keeps_one_pool_and_evicts_expired_film_pages(monkeypatch) -> None:
    pools: list[object] = []

    class CountingPool(screenings_sgiff.ThreadPoolExecutor):
        def __init__(self, *args, **kwargs) -> None:
            pools.append(self)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(screenings_sgiff, "ThreadPoolExecutor", CountingPool)
    clock = {"now": 1000.0}
    adapter = SgiffAdapter(
        transport=lambda url: SGIFF_EXPLORE if url.endswith("/explore-films/") else SGIFF_FILM,
        clock=lambda: clock["now"],
    )
    adapter._pages["https://sgiff.com/film/gone/"] = (999.0, ())

    adapter.fetch(TODAY)
    assert "https://sgiff.com/film/gone/" not in adapter._pages
    clock["now"] += SgiffAdapter.complete_cache_seconds + 1  # Every cached page has now expired.
    adapter.fetch(TODAY)

    assert len(pools) == 1
    assert sorted(adapter._pages) == ["https://sgiff.com/film/32-meters/", "https://sgiff.com/film/burn/"]
    assert all(expires > clock["now"] for expires, _ in adapter._pages.values())


def test_sgiff_redesign_is_reported_not_silently_empty() -> None:
    with pytest.raises(ScreeningError):
        SgiffAdapter(transport=lambda url: "<html>new site</html>").fetch(TODAY)


def peatix_event(event_id: int, name: str, when: str, *, organiser: int = 474137, days: int = 1) -> dict:
    return {
        "id": event_id, "name": name, "datetime": when, "days": days,
        "venue_name": "Objectifs - Centre for Photography & Film",
        "organizer": {"id": organiser, "nickname": "Objectifs"},
        "cover": f"https://cdn.peatix.com/event/{event_id}/cover.png",
        "address": "155 Middle Road",
    }


def test_peatix_keeps_screenings_by_allow_listed_organisers() -> None:
    payload = {"json_data": {"events": [
        peatix_event(1, "OSFF 2026 Current Frames | Clermont-Ferrand Selects", "2026-10-24 16:30:00 +0800"),
        peatix_event(2, "Riso Flipbook Workshop by Bedroom Press", "2026-10-31 14:00:00 +0800"),
        peatix_event(3, "Objectifs Short Film Festival Screening", "2026-10-22 19:30:00 +0800", days=9),
        peatix_event(4, "Short Film Night", "2026-10-21 19:00:00 +0800", organiser=99),
        peatix_event(5, "Cinema Journey", "2026-10-16 18:00:00 +0900"),
        peatix_event(6, "Late film screening", "not a date"),
    ]}}
    requested: list[str] = []

    def transport(url: str):
        requested.append(url)
        return payload

    items = PeatixScreeningsAdapter(transport=transport).fetch(TODAY)

    assert requested == ["https://peatix.com/search/events?q=objectifs&country=SG&p=1&size=50"]
    assert len(items) == 1
    assert items[0].title == "Clermont-Ferrand Selects"
    assert items[0].details == "Objectifs · OSFF 2026 Current Frames"
    assert items[0].starts_at == "2026-10-24T16:30+08:00"
    assert items[0].venue == "Objectifs - Centre for Photography & Film"
    assert items[0].url == "https://peatix.com/event/1"
    assert items[0].poster == "https://cdn.peatix.com/event/1/cover.png"
    assert "Middle Road" not in str(items[0].model_dump())


def test_peatix_identifies_itself_and_reports_unexpected_payloads(monkeypatch) -> None:
    seen: dict = {}

    def fake_request_json(url: str, *, allowed_hosts, headers=None):
        seen.update(url=url, hosts=set(allowed_hosts), headers=headers)
        return {"error": "nope"}

    monkeypatch.setattr(screenings_venues, "request_json", fake_request_json)
    with pytest.raises(ScreeningError):
        PeatixScreeningsAdapter().fetch(TODAY)
    assert seen["hosts"] == {"peatix.com"}
    assert seen["headers"] == {"X-Requested-With": "XMLHttpRequest"}


def test_peatix_waits_between_organisers() -> None:
    pauses: list[float] = []
    adapter = PeatixScreeningsAdapter(transport=lambda url: {"json_data": {"events": []}}, sleep=pauses.append)
    adapter.organisers = (*adapter.organisers, PeatixOrganiser(1, "Other", "other"))

    assert adapter.fetch(TODAY) == []
    assert pauses == [1.0]


class FakeAdapter:
    cache_seconds = 3600

    def __init__(self, venue_id: str, items=None, error: Exception | None = None) -> None:
        self.venue = Venue(venue_id, venue_id.title(), "independent", f"https://{venue_id}.example/")
        self.link_hosts = frozenset({f"{venue_id}.example"})
        self.poster_hosts = frozenset({f"img.{venue_id}.example"})
        self.items = items or []
        self.error = error
        self.gate: threading.Event | None = None
        self.started = threading.Event()
        self.calls = 0

    def fetch(self, today: date):
        self.calls += 1
        self.started.set()
        if self.gate is not None:
            assert self.gate.wait(10), "The test never released the adapter."
        if self.error:
            raise self.error
        return self.items


def item(venue: Venue, title: str, when: datetime, **extra):
    return screening_at(title=title, venue=venue, starts_at=when, **extra)


def statuses(result: dict) -> dict:
    return {source["id"]: source for source in result["sources"]}


def wait_until(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "The background read never finished."
        time.sleep(0.01)


def test_service_isolates_failures_filters_range_and_caches() -> None:
    clock = {"now": NOON}
    good = FakeAdapter("good")
    good.items = [
        item(good.venue, "Past", datetime(2026, 10, 16, 9, 0, tzinfo=SINGAPORE)),
        item(good.venue, "Tonight", datetime(2026, 10, 16, 20, 0, tzinfo=SINGAPORE)),
        item(good.venue, "Tonight", datetime(2026, 10, 16, 20, 0, tzinfo=SINGAPORE)),
        item(good.venue, "Too late", datetime(2026, 11, 30, 20, 0, tzinfo=SINGAPORE)),
    ]
    broken = FakeAdapter("broken", error=ScreeningError("The venue website returned HTTP 500."))
    buggy = FakeAdapter("buggy", error=KeyError("surprise"))
    quiet = FakeAdapter("quiet")
    unlisted = UnlistedVenue(Venue("gv", "Golden Village", "multiplex", "https://www.gv.com.sg/"), "blocked")
    service = ScreeningsService([good, broken, buggy, quiet, unlisted], clock=lambda: clock["now"])

    result = service.listings()

    assert result["range"] == {"from": "2026-10-16", "to": "2026-10-29"}
    assert [entry["title"] for entry in result["screenings"]] == ["Tonight"]
    sources = statuses(result)
    assert {key: (value["state"], value["count"]) for key, value in sources.items()} == {
        "good": ("ok", 1), "broken": ("error", 0), "buggy": ("error", 0),
        "quiet": ("empty", 0), "gv": ("unlisted", 0)}
    assert sources["broken"]["message"] == "The venue website returned HTTP 500."
    assert "surprise" not in str(sources["buggy"]["message"])
    assert {key: value["coverage_days"] for key, value in sources.items()} == {
        "good": 14, "broken": 14, "buggy": 14, "quiet": 14, "gv": None}
    assert not any(value["stale"] for value in sources.values())

    service.listings()
    assert (good.calls, broken.calls) == (1, 1)
    clock["now"] += 6 * 60  # Failures retry sooner than successes.
    service.listings()
    assert (good.calls, broken.calls) == (1, 2)


def test_service_reports_shaw_coverage_as_seven_days() -> None:
    shaw = ShawTheatresAdapter(transport=lambda url: [])
    sources = statuses(ScreeningsService([shaw], clock=lambda: NOON).listings())

    assert sources["shaw"]["coverage_days"] == 7
    assert sources["shaw"]["state"] == "empty"


def test_service_reads_each_venue_once_for_concurrent_requests() -> None:
    adapter = FakeAdapter("good")
    adapter.items = [item(adapter.venue, "Tomorrow", datetime(2026, 10, 17, 20, 0, tzinfo=SINGAPORE))]
    adapter.gate = threading.Event()
    service = ScreeningsService([adapter], clock=lambda: NOON)
    results: list[dict] = []
    callers = [threading.Thread(target=lambda: results.append(service.listings())) for _ in range(6)]
    for caller in callers:
        caller.start()
    assert adapter.started.wait(5)
    time.sleep(0.05)
    adapter.gate.set()
    for caller in callers:
        caller.join(5)

    assert adapter.calls == 1
    assert len(results) == 6
    assert all([entry["title"] for entry in result["screenings"]] == ["Tomorrow"] for result in results)


def test_service_answers_by_the_deadline_and_finishes_the_read_in_the_background() -> None:
    adapter = FakeAdapter("slow")
    adapter.items = [item(adapter.venue, "Tomorrow", datetime(2026, 10, 17, 20, 0, tzinfo=SINGAPORE))]
    adapter.gate = threading.Event()
    service = ScreeningsService([adapter], clock=lambda: NOON, deadline_seconds=0.05)
    try:
        started = time.monotonic()
        first = service.listings()
        assert time.monotonic() - started < 2
    finally:
        adapter.gate.set()

    source = statuses(first)["slow"]
    assert (source["state"], source["message"], first["screenings"]) == ("error", SLOW_MESSAGE, [])
    wait_until(lambda: service._inflight["slow"].done())
    second = service.listings()
    assert [entry["title"] for entry in second["screenings"]] == ["Tomorrow"]
    assert statuses(second)["slow"]["stale"] is False
    assert adapter.calls == 1


def test_service_serves_earlier_listings_while_a_slow_refresh_runs() -> None:
    clock = {"now": NOON}
    adapter = FakeAdapter("slow")
    adapter.items = [item(adapter.venue, "Tuesday", datetime(2026, 10, 20, 20, 0, tzinfo=SINGAPORE))]
    service = ScreeningsService([adapter], clock=lambda: clock["now"], deadline_seconds=0.05)
    service.listings()

    clock["now"] += 2 * 60 * 60
    adapter.gate = threading.Event()
    try:
        result = service.listings()
    finally:
        adapter.gate.set()

    source = statuses(result)["slow"]
    assert (source["state"], source["stale"], source["message"]) == ("ok", True, SLOW_MESSAGE)
    assert [entry["title"] for entry in result["screenings"]] == ["Tuesday"]
    wait_until(lambda: service._inflight["slow"].done())
    assert statuses(service.listings())["slow"]["stale"] is False


def test_service_serves_earlier_listings_when_a_refresh_fails_for_up_to_a_day(caplog) -> None:
    clock = {"now": NOON}
    adapter = FakeAdapter("flaky")
    adapter.items = [item(adapter.venue, "Tuesday", datetime(2026, 10, 20, 20, 0, tzinfo=SINGAPORE))]
    service = ScreeningsService([adapter], clock=lambda: clock["now"])
    service.listings()

    adapter.error = ScreeningError("The venue website returned HTTP 503.")
    clock["now"] += 2 * 60 * 60
    with caplog.at_level(logging.WARNING, logger="firstroll.screenings"):
        result = service.listings()

    source = statuses(result)["flaky"]
    assert (source["state"], source["stale"], source["count"]) == ("ok", True, 1)
    assert source["message"] == "The venue website returned HTTP 503. Showing the listings read earlier."
    assert [entry["title"] for entry in result["screenings"]] == ["Tuesday"]
    assert "flaky" in caplog.text and "HTTP 503" in caplog.text

    service.listings()
    assert adapter.calls == 2  # The failure is cached briefly before the next retry.
    clock["now"] += FAILURE_CACHE_SECONDS + 1
    service.listings()
    assert adapter.calls == 3

    clock["now"] = NOON + STALE_SECONDS + 1
    late = statuses(service.listings())["flaky"]
    assert (late["state"], late["stale"]) == ("error", False)


def test_service_logs_failures_with_the_venue_and_traceback_but_no_page_content(caplog) -> None:
    buggy = FakeAdapter("buggy", error=ValueError("unexpected '<td>Secret page fragment</td>'"))
    service = ScreeningsService([buggy], clock=lambda: NOON)

    with caplog.at_level(logging.WARNING, logger="firstroll.screenings"):
        service.listings()

    [record] = [entry for entry in caplog.records if entry.name == "firstroll.screenings"]
    assert record.levelno == logging.WARNING
    assert "buggy" in record.getMessage()
    assert record.exc_info is not None
    assert "ValueError" in caplog.text
    assert "Secret page fragment" not in caplog.text


def test_service_keeps_only_allow_listed_links_and_proxies_posters() -> None:
    adapter = FakeAdapter("good")
    when = datetime(2026, 10, 17, 20, 0, tzinfo=SINGAPORE)
    adapter.items = [
        item(adapter.venue, "Kept", when, url="https://good.example/book",
             poster="https://img.good.example/kept.jpg"),
        item(adapter.venue, "Off list", when, url="https://evil.example/book",
             poster="https://evil.example/poster.jpg"),
        item(adapter.venue, "Plain HTTP", when, url="http://good.example/book",
             poster="http://img.good.example/plain.jpg"),
    ]
    posters = PosterProxy(transport=lambda url, hosts: (PNG, "image/png"))
    service = ScreeningsService([adapter], clock=lambda: NOON, posters=posters)

    result = service.listings()
    listed = {entry["title"]: entry for entry in result["screenings"]}

    assert listed["Kept"]["url"] == "https://good.example/book"
    assert listed["Kept"]["poster"].startswith("/api/screenings/posters/")
    assert len(listed["Kept"]["poster"].rsplit("/", 1)[1]) == 32
    assert [listed[title][field] for title in ("Off list", "Plain HTTP") for field in ("url", "poster")] == [
        None, None, None, None]
    assert "img.good.example" not in json.dumps(result)
    assert posters.fetch(listed["Kept"]["poster"].rsplit("/", 1)[1]).body == PNG


def test_fetched_results_carry_their_own_cache_lifetime() -> None:
    clock = {"now": NOON}

    class Partial(FakeAdapter):
        def fetch(self, today: date):
            super().fetch(today)
            return Fetched(items=list(self.items), cache_seconds=60)

    adapter = Partial("partial")
    service = ScreeningsService([adapter], clock=lambda: clock["now"])
    service.listings()
    clock["now"] += 61
    service.listings()

    assert adapter.calls == 2


def test_default_adapters_cover_every_venue_without_reading_anything() -> None:
    ids = [adapter.venue.id for adapter in screenings.default_adapters()]

    assert ids == ["afa", "filmhouse", "alliance-francaise", "shaw", "sgiff", "peatix", "gv", "artscience"]


LISTINGS = "/api/screenings/singapore"


def hosted_application(monkeypatch, service):
    """The hosted API shell, as production builds it, with the screenings routes and health."""
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    application = main.create_api_application(public_mode=True)
    add_screenings_routes(application, service)
    application.add_api_route("/api/health", main.health)
    return application


def test_listings_route_is_public_cacheable_and_compressed_in_hosted_mode(monkeypatch) -> None:
    adapter = FakeAdapter("good")
    adapter.items = [item(adapter.venue, "Tomorrow", datetime(2026, 10, 17, 20, 0, tzinfo=SINGAPORE))]
    application = hosted_application(monkeypatch, ScreeningsService([adapter], clock=lambda: NOON))
    client = TestClient(application)

    assert application.openapi_url is None and client.get("/openapi.json").status_code == 404
    compressed = client.get(LISTINGS, headers={"Accept-Encoding": "gzip, deflate"})
    plain = client.get(LISTINGS, headers={"Accept-Encoding": "identity"})

    assert compressed.status_code == plain.status_code == 200
    assert compressed.headers["content-encoding"] == "gzip"
    assert "content-encoding" not in plain.headers
    for response in (compressed, plain):
        assert response.headers["cache-control"] == "public, max-age=600"
        assert response.headers["vary"] == "Accept-Encoding"
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["screenings"][0]["title"] == "Tomorrow"
        assert response.json()["sources"][0]["coverage_days"] == 14
    assert int(compressed.headers["content-length"]) < int(plain.headers["content-length"])


def test_accept_encoding_parsing_honours_refusals() -> None:
    assert accepts_gzip("gzip, deflate, br")
    assert accepts_gzip("br;q=1.0, GZIP;q=0.5")
    assert accepts_gzip("*")
    assert not accepts_gzip("")
    assert not accepts_gzip("identity")
    assert not accepts_gzip("gzip;q=0, *")
    assert not accepts_gzip("gzip;q=nonsense")


def test_slow_listings_use_their_own_threads_and_never_starve_health(monkeypatch) -> None:
    gate = threading.Event()
    lock = threading.Lock()
    active = {"now": 0, "most": 0}

    class BlockingService:
        posters = PosterProxy()

        def listings(self) -> dict:
            with lock:
                active["now"] += 1
                active["most"] = max(active["most"], active["now"])
            try:
                assert gate.wait(10), "The test never released the listings."
            finally:
                with lock:
                    active["now"] -= 1
            return {"sources": [], "screenings": []}

    application = hosted_application(monkeypatch, BlockingService())

    async def scenario() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            requests = [asyncio.create_task(client.get(LISTINGS)) for _ in range(8)]
            try:
                for _ in range(500):
                    if active["now"] == LISTING_THREADS:
                        break
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.1)
                health = await asyncio.wait_for(client.get("/api/health"), 5)
                assert health.status_code == 200
                assert active["most"] == LISTING_THREADS
                assert not any(request.done() for request in requests)
            finally:
                gate.set()
            return list(await asyncio.wait_for(asyncio.gather(*requests), 10))

    responses = asyncio.run(scenario())

    assert [response.status_code for response in responses] == [200] * 8
    assert active["most"] == LISTING_THREADS


def test_main_application_registers_the_screenings_routes_and_bundle() -> None:
    paths = {getattr(route, "path", None) for route in main.app.routes}
    client = TestClient(main.app)

    assert {LISTINGS, "/api/screenings/posters/{poster_id}"} <= paths
    assert isinstance(main.screenings_service, ScreeningsService)
    assert client.get("/assets/screenings.js").status_code in {200, 503}
    assert client.get("/assets/not-a-bundle.js").status_code == 404
