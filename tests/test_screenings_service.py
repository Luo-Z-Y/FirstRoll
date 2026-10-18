"""ScreeningsService scheduling, caching and failure isolation, and the listings route."""

import asyncio
import json
import logging
import threading
import time
from datetime import date, datetime

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.backend import main, screenings
from app.backend.screenings import SLOW_MESSAGE, STALE_SECONDS, ScreeningsService
from app.backend.screenings_api import (
    LISTING_THREADS,
    accepts_gzip,
    add_screenings_routes,
    listings_settled,
)
from app.backend.screenings_http import ScreeningError
from app.backend.screenings_model import FAILURE_CACHE_SECONDS, SINGAPORE, Fetched, Venue, screening_at
from app.backend.screenings_posters import PosterProxy
from app.backend.screenings_venues import ShawTheatresAdapter, UnlistedVenue

NOON = datetime(2026, 10, 16, 12, 0, tzinfo=SINGAPORE).timestamp()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


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


def test_a_refresh_past_its_deadline_holds_no_later_request() -> None:
    clock = {"now": NOON}
    adapter = FakeAdapter("slow")
    adapter.items = [item(adapter.venue, "Tuesday", datetime(2026, 10, 20, 20, 0, tzinfo=SINGAPORE))]
    service = ScreeningsService([adapter], clock=lambda: clock["now"], deadline_seconds=0.5)
    service.listings()

    clock["now"] += 2 * 60 * 60
    adapter.gate = threading.Event()
    try:
        service.listings()  # Starts the refresh and waits for its deadline.
        started = time.monotonic()
        later = service.listings()
        elapsed = time.monotonic() - started
    finally:
        adapter.gate.set()

    assert elapsed < 0.25  # Not another full deadline.
    source = statuses(later)["slow"]
    assert (source["state"], source["stale"], source["message"]) == ("ok", True, SLOW_MESSAGE)
    assert [entry["title"] for entry in later["screenings"]] == ["Tuesday"]
    assert adapter.calls == 2


def test_a_request_joining_a_running_refresh_waits_only_for_what_is_left_of_its_deadline() -> None:
    adapter = FakeAdapter("slow")
    adapter.gate = threading.Event()
    service = ScreeningsService([adapter], clock=lambda: NOON, deadline_seconds=1.0)
    first = threading.Thread(target=service.listings)
    try:
        first.start()
        assert adapter.started.wait(5)
        time.sleep(0.5)
        started = time.monotonic()
        joined = service.listings()
        elapsed = time.monotonic() - started
    finally:
        adapter.gate.set()
        first.join(5)

    assert 0.2 < elapsed < 0.8  # About the 0.5 s left, not a fresh 1 s.
    assert statuses(joined)["slow"]["message"] == SLOW_MESSAGE
    assert adapter.calls == 1


def test_an_empty_venue_stays_empty_while_a_slow_refresh_runs() -> None:
    clock = {"now": NOON}
    quiet = FakeAdapter("quiet")
    broken = FakeAdapter("broken", error=ScreeningError("The venue website returned HTTP 500."))
    service = ScreeningsService([quiet, broken], clock=lambda: clock["now"], deadline_seconds=0.05)
    assert statuses(service.listings())["quiet"]["state"] == "empty"

    clock["now"] += 2 * 60 * 60
    quiet.gate = threading.Event()
    broken.gate = quiet.gate
    try:
        sources = statuses(service.listings())
    finally:
        quiet.gate.set()

    assert (sources["quiet"]["state"], sources["quiet"]["stale"], sources["quiet"]["message"]) == (
        "empty", True, SLOW_MESSAGE)
    # A venue whose last read failed has nothing to stand in, so it is still an error.
    assert (sources["broken"]["state"], sources["broken"]["stale"]) == ("error", False)


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
        assert response.headers["vary"] == "Accept-Encoding, Origin"
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["screenings"][0]["title"] == "Tomorrow"
        assert response.json()["sources"][0]["coverage_days"] == 14
    assert int(compressed.headers["content-length"]) < int(plain.headers["content-length"])


def test_listings_are_cached_for_ten_minutes_only_once_every_source_has_settled(monkeypatch) -> None:
    good = FakeAdapter("good")
    good.items = [item(good.venue, "Tomorrow", datetime(2026, 10, 17, 20, 0, tzinfo=SINGAPORE))]
    unlisted = UnlistedVenue(Venue("gv", "Golden Village", "multiplex", "https://www.gv.com.sg/"), "blocked")
    settled = ScreeningsService([good, FakeAdapter("quiet"), unlisted], clock=lambda: NOON)
    failing = ScreeningsService(
        [FakeAdapter("broken", error=ScreeningError("The venue website returned HTTP 500."))],
        clock=lambda: NOON)

    assert TestClient(hosted_application(monkeypatch, settled)).get(LISTINGS).headers[
        "cache-control"] == "public, max-age=600"
    assert TestClient(hosted_application(monkeypatch, failing)).get(LISTINGS).headers[
        "cache-control"] == "public, max-age=30"


def test_only_fresh_ok_empty_or_unlisted_sources_count_as_settled() -> None:
    def source(state: str, stale: bool = False) -> dict:
        return {"state": state, "stale": stale}

    assert listings_settled({"sources": [source("ok"), source("empty"), source("unlisted")]})
    assert listings_settled({"sources": []})
    assert not listings_settled({"sources": [source("ok"), source("error")]})
    assert not listings_settled({"sources": [source("ok", stale=True)]})
    assert not listings_settled({"sources": [source("empty", stale=True)]})


def test_requests_queued_behind_the_listing_threads_are_not_held_again(monkeypatch) -> None:
    adapter = FakeAdapter("slow")
    adapter.gate = threading.Event()
    service = ScreeningsService([adapter], clock=lambda: NOON, deadline_seconds=0.5)
    application = hosted_application(monkeypatch, service)

    async def scenario() -> tuple[list[httpx.Response], float]:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            started = time.monotonic()
            requests = [client.get(LISTINGS) for _ in range(2 * LISTING_THREADS)]
            responses = await asyncio.wait_for(asyncio.gather(*requests), 10)
            return list(responses), time.monotonic() - started

    try:
        responses, elapsed = asyncio.run(scenario())
    finally:
        adapter.gate.set()

    # The second wave reaches a listing thread after the read's deadline and answers at once.
    assert elapsed < 0.9
    assert [response.status_code for response in responses] == [200] * (2 * LISTING_THREADS)
    for response in responses:
        assert statuses(response.json())["slow"]["message"] == SLOW_MESSAGE
        assert response.headers["cache-control"] == "public, max-age=30"
    assert adapter.calls == 1


def test_listings_vary_by_origin_whether_or_not_cors_headers_are_added() -> None:
    application = FastAPI()
    application.add_middleware(CORSMiddleware, allow_origins=["https://firstroll.app"],
                               allow_methods=["GET"])
    add_screenings_routes(application, ScreeningsService([FakeAdapter("good")], clock=lambda: NOON))
    client = TestClient(application)

    direct = client.get(LISTINGS)
    site = client.get(LISTINGS, headers={"Origin": "https://firstroll.app"})

    assert "access-control-allow-origin" not in direct.headers
    assert site.headers["access-control-allow-origin"] == "https://firstroll.app"
    for response in (direct, site):
        assert "Origin" in [token.strip() for token in response.headers["vary"].split(",")]


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
