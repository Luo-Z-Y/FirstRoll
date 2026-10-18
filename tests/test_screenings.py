"""Venue adapters and the year-less date and clock helpers they share."""

import threading
import time
from datetime import date

import pytest

from app.backend import screenings_sgiff, screenings_venues
from app.backend.screenings_http import ScreeningError
from app.backend.screenings_model import festival_day, infer_day, parse_clock, safe_url
from app.backend.screenings_sgiff import SgiffAdapter
from app.backend.screenings_venues import (
    AllianceFrancaiseAdapter,
    AsianFilmArchiveAdapter,
    FilmhouseAdapter,
    PeatixOrganiser,
    PeatixScreeningsAdapter,
    ShawTheatresAdapter,
)

TODAY = date(2026, 10, 16)


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


def test_29_february_resolves_to_the_leap_year_and_impossible_dates_do_not() -> None:
    # Only one year in any three candidates has a 29 February; the others must not end the search.
    assert festival_day(29, "Feb", "Tue", date(2028, 2, 20)) == date(2028, 2, 29)
    assert festival_day(29, "Feb", "Tue", date(2029, 1, 20)) == date(2028, 2, 29)
    assert infer_day(29, "Feb", date(2027, 12, 20)) == date(2028, 2, 29)
    assert festival_day(31, "Apr", "Mon", TODAY) is None
    assert infer_day(31, "April", TODAY) is None


def test_retrieved_urls_are_percent_encoded_and_existing_escapes_kept() -> None:
    sgiff, afa = {"sgiff.com"}, {"asianfilmarchive.org"}

    assert safe_url("https://sgiff.com/wp-content/uploads/Café.jpg", sgiff) == (
        "https://sgiff.com/wp-content/uploads/Caf%C3%A9.jpg")
    assert safe_url("/wp-content/uploads/2026/10/くちづけ poster.jpg", afa, "https://asianfilmarchive.org/") == (
        "https://asianfilmarchive.org/wp-content/uploads/2026/10/%E3%81%8F%E3%81%A1%E3%81%A5%E3%81%91%20poster.jpg")
    assert safe_url("https://sgiff.com/a%20b.jpg?x=1&y=(2)#top", sgiff) == "https://sgiff.com/a%20b.jpg?x=1&y=(2)#top"
    assert safe_url("https://evil.example/Café.jpg", sgiff) is None


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
