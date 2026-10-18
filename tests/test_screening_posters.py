"""Poster proxy, poster route and the guarded HTTPS transport both screenings paths share."""

import asyncio
import email.message
import hashlib
import io
import socket
import threading
import time
import urllib.response
from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.backend import main, screenings_http, screenings_posters
from app.backend.screenings import ScreeningsService
from app.backend.screenings_api import POSTER_THREADS, add_screenings_routes
from app.backend.screenings_http import (
    ScreeningError,
    connect_public_ipv4_first,
    host_allowed,
    request_bytes,
    request_json,
)
from app.backend.screenings_model import SINGAPORE, Venue, screening_at
from app.backend.screenings_posters import (
    FAILURE_CACHE_SECONDS,
    MAX_POSTER_BYTES,
    POSTER_CACHE_SECONDS,
    REGISTRY_SECONDS,
    PosterNotFound,
    PosterProxy,
    PosterUnavailable,
    poster_id,
    sniff_image,
)
from app.backend.screenings_venues import ShawTheatresAdapter

HOSTS = frozenset({"img.venue.example"})
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 36
GIF = b"GIF89a" + b"\x00" * 34
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 24
AVIF = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1miaf" + b"\x00" * 12
NOON = datetime(2026, 10, 16, 12, 0, tzinfo=SINGAPORE).timestamp()


class Upstream:
    """A stub image host: answers from a table and counts requests per URL."""

    def __init__(self, body: bytes = PNG, content_type: str = "image/png") -> None:
        self.answer: tuple[bytes, str] | Exception = (body, content_type)
        self.calls: dict[str, int] = {}
        self.gate: threading.Event | None = None

    def __call__(self, url: str, hosts: frozenset[str]) -> tuple[bytes, str]:
        self.calls[url] = self.calls.get(url, 0) + 1
        if self.gate is not None:
            assert self.gate.wait(10), "The test never released the upstream."
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def proxy_with(upstream: Upstream, **options) -> tuple[PosterProxy, dict]:
    clock = {"now": 1000.0}
    return PosterProxy(transport=upstream, clock=lambda: clock["now"], **options), clock


def identifier(path: str | None) -> str:
    assert path is not None and path.startswith("/api/screenings/posters/")
    return path.rsplit("/", 1)[1]


def test_poster_ids_are_short_sha256_hex_and_only_listed_hosts_register() -> None:
    proxy, _ = proxy_with(Upstream())
    url = "https://img.venue.example/poster.jpg"

    assert poster_id(url) == hashlib.sha256(url.encode()).hexdigest()[:32]
    assert proxy.register(url, HOSTS) == f"/api/screenings/posters/{poster_id(url)}"
    assert proxy.register("https://elsewhere.example/poster.jpg", HOSTS) is None
    assert proxy.register("http://img.venue.example/poster.jpg", HOSTS) is None
    assert proxy.register("https://img.venue.example:8443/poster.jpg", HOSTS) is None
    assert proxy.register(None, HOSTS) is None


def test_sniffing_recognises_only_the_accepted_image_formats() -> None:
    assert [sniff_image(body) for body in (JPEG, PNG, GIF, WEBP, AVIF)] == [
        "image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"]
    assert sniff_image(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>') is None
    assert sniff_image(b"<!doctype html><script>alert(1)</script>") is None
    assert sniff_image(b"") is None


def test_posters_are_fetched_once_cached_and_served_as_sniffed() -> None:
    upstream = Upstream(WEBP, "image/jpeg")  # A mislabelled but genuine image is served as itself.
    proxy, _ = proxy_with(upstream)
    poster = identifier(proxy.register("https://img.venue.example/a.webp", HOSTS))

    first = proxy.fetch(poster)
    second = proxy.fetch(poster)

    assert (first.content_type, first.body) == ("image/webp", WEBP)
    assert second is first
    assert upstream.calls == {"https://img.venue.example/a.webp": 1}


def test_concurrent_requests_for_one_poster_share_a_single_fetch() -> None:
    upstream = Upstream()
    upstream.gate = threading.Event()
    proxy, _ = proxy_with(upstream)
    poster = identifier(proxy.register("https://img.venue.example/a.png", HOSTS))
    results: list[bytes] = []
    workers = [threading.Thread(target=lambda: results.append(proxy.fetch(poster).body)) for _ in range(6)]
    for worker in workers:
        worker.start()
    time.sleep(0.05)
    upstream.gate.set()
    for worker in workers:
        worker.join(5)

    assert results == [PNG] * 6
    assert upstream.calls == {"https://img.venue.example/a.png": 1}


@pytest.mark.parametrize(
    ("body", "declared"),
    [
        (b'<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>', "image/svg+xml"),
        (b"<!doctype html><title>Not an image</title>", "image/jpeg"),
        (PNG, "text/html; charset=utf-8"),
        (PNG, ""),
    ],
)
def test_svg_html_and_unlabelled_responses_are_never_served(body: bytes, declared: str) -> None:
    proxy, _ = proxy_with(Upstream(body, declared))
    poster = identifier(proxy.register("https://img.venue.example/x", HOSTS))

    with pytest.raises(PosterUnavailable):
        proxy.fetch(poster)


def test_failures_are_remembered_for_ten_minutes() -> None:
    upstream = Upstream()
    upstream.answer = ScreeningError("The venue website returned HTTP 503.")
    proxy, clock = proxy_with(upstream)
    url = "https://img.venue.example/broken.png"
    poster = identifier(proxy.register(url, HOSTS))

    for _ in range(3):
        with pytest.raises(PosterUnavailable):
            proxy.fetch(poster)
    assert upstream.calls[url] == 1

    upstream.answer = (PNG, "image/png")
    clock["now"] += FAILURE_CACHE_SECONDS + 1
    assert proxy.fetch(poster).body == PNG
    assert upstream.calls[url] == 2


def test_the_byte_cache_is_size_capped_least_recently_used_and_expires() -> None:
    upstream = Upstream()
    proxy, clock = proxy_with(upstream, cache_bytes=len(PNG) * 2)
    urls = {name: f"https://img.venue.example/{name}.png" for name in "abc"}
    ids = {name: identifier(proxy.register(url, HOSTS)) for name, url in urls.items()}

    proxy.fetch(ids["a"])
    proxy.fetch(ids["b"])
    proxy.fetch(ids["a"])  # "b" is now the least recently used.
    proxy.fetch(ids["c"])
    proxy.fetch(ids["a"])
    proxy.fetch(ids["b"])
    assert [upstream.calls[urls[name]] for name in "abc"] == [1, 2, 1]
    assert proxy._image_bytes <= len(PNG) * 2

    clock["now"] += POSTER_CACHE_SECONDS + 1
    proxy.register(urls["b"], HOSTS)  # Still listed, so still known.
    proxy.fetch(ids["b"])
    assert upstream.calls[urls["b"]] == 3


def test_malformed_unknown_and_expired_ids_are_not_found() -> None:
    proxy, clock = proxy_with(Upstream())
    poster = identifier(proxy.register("https://img.venue.example/a.png", HOSTS))

    for value in ("", "../../etc/passwd", "A" * 32, poster[:31], poster + "0", "0" * 32):
        with pytest.raises(PosterNotFound):
            proxy.fetch(value)
    clock["now"] += REGISTRY_SECONDS + 1
    with pytest.raises(PosterNotFound):
        proxy.fetch(poster)


def test_poster_downloads_use_the_guarded_helper_within_tight_limits(monkeypatch) -> None:
    seen: dict = {}

    def fake_request_bytes(url, **options):
        seen.update(url=url, **options)
        return PNG, "image/png", None

    monkeypatch.setattr(screenings_posters, "request_bytes", fake_request_bytes)
    proxy = PosterProxy()
    poster = identifier(proxy.register("https://img.venue.example/a.png", HOSTS))

    assert proxy.fetch(poster).body == PNG
    assert seen["url"] == "https://img.venue.example/a.png"
    assert set(seen["allowed_hosts"]) == set(HOSTS)
    assert seen["timeout"] <= 10 and seen["total_seconds"] <= 10
    assert seen["max_bytes"] == MAX_POSTER_BYTES == 3 * 1024 * 1024
    assert "image/" in seen["accept"] and "svg" not in seen["accept"]


class PosterAdapter:
    cache_seconds = 3600
    venue = Venue("good", "Good", "independent", "https://good.example/")
    link_hosts = frozenset({"good.example"})
    poster_hosts = HOSTS

    def fetch(self, today: date):
        return [screening_at(
            title="Tomorrow", venue=self.venue, poster="https://img.venue.example/tomorrow.png",
            starts_at=datetime(2026, 10, 17, 20, 0, tzinfo=SINGAPORE))]


def poster_client(monkeypatch, upstream: Upstream) -> tuple[TestClient, str]:
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    service = ScreeningsService([PosterAdapter()], clock=lambda: NOON, posters=PosterProxy(transport=upstream))
    application = main.create_api_application(public_mode=True)
    add_screenings_routes(application, service)
    client = TestClient(application)
    listing = client.get("/api/screenings/singapore").json()
    return client, listing["screenings"][0]["poster"]


def test_poster_route_serves_listed_images_with_strict_headers(monkeypatch) -> None:
    client, path = poster_client(monkeypatch, Upstream(JPEG, "image/jpeg"))

    response = client.get(path)

    assert response.status_code == 200
    assert response.content == JPEG
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert response.headers["cross-origin-resource-policy"] == "cross-origin"


def test_poster_route_answers_404_for_unknown_ids_and_502_for_upstream_failures(monkeypatch) -> None:
    upstream = Upstream(b"<svg/>", "image/svg+xml")
    client, path = poster_client(monkeypatch, upstream)

    assert client.get("/api/screenings/posters/" + "0" * 32).status_code == 404
    assert client.get("/api/screenings/posters/NOT-AN-ID").status_code == 404
    failed = client.get(path)
    assert failed.status_code == 502
    assert failed.headers["cache-control"] == "no-store"
    assert "svg" not in failed.headers["content-type"]


def fake_upstream(monkeypatch, script: dict[str, tuple[int, dict[str, str], bytes]]) -> list:
    """Replace the guarded HTTPS handler's network step with scripted responses."""
    opened: list[tuple[str, dict[str, str]]] = []

    def https_open(self, request):
        opened.append((request.full_url, {key.casefold(): value for key, value in request.header_items()}))
        status, headers, body = script[request.full_url]
        message = email.message.Message()
        for key, value in headers.items():
            message[key] = value
        response = urllib.response.addinfourl(io.BytesIO(body), message, request.full_url, code=status)
        response.msg = "OK" if status == 200 else "Found"
        return response

    monkeypatch.setattr(screenings_http._GuardedHTTPSHandler, "https_open", https_open)
    return opened


def redirect(target: str) -> tuple[int, dict[str, str], bytes]:
    return 302, {"Location": target}, b""


@pytest.mark.parametrize("target", [
    "https://evil.example/steal",
    "http://shaw.sg/internal/get_simple_locations",
    "ftp://shaw.sg/listing",
    "https://user:secret@shaw.sg/listing",
    "https://shaw.sg:8443/listing",
])
def test_redirects_are_checked_before_they_are_followed(monkeypatch, target: str) -> None:
    opened = fake_upstream(monkeypatch, {"https://shaw.sg/start": redirect(target)})

    with pytest.raises(ScreeningError, match="redirected"):
        request_bytes("https://shaw.sg/start", allowed_hosts={"shaw.sg"}, accept="application/json")
    assert [url for url, _ in opened] == ["https://shaw.sg/start"]


def test_redirects_within_the_allow_list_are_capped_at_three(monkeypatch) -> None:
    hops = [f"https://shaw.sg/{index}" for index in range(5)]
    opened = fake_upstream(monkeypatch, {hops[index]: redirect(hops[index + 1]) for index in range(4)})

    with pytest.raises(ScreeningError, match="HTTP 302"):
        request_bytes(hops[0], allowed_hosts={"shaw.sg"}, accept="application/json")
    assert [url for url, _ in opened] == hops[:4]


def test_shaw_sends_its_header_through_the_guarded_opener_only_to_shaw(monkeypatch) -> None:
    locations = "https://shaw.sg/internal/get_simple_locations"
    opened = fake_upstream(monkeypatch, {
        locations: redirect("https://www.shaw.sg/internal/get_simple_locations"),
        "https://www.shaw.sg/internal/get_simple_locations": (
            200, {"Content-Type": "application/json"}, b'[{"id": 4, "name": "Lot One"}]'),
        "https://shaw.sg/internal/escape": redirect("https://cdn.example/internal"),
    })
    adapter = ShawTheatresAdapter()

    assert adapter._request(locations) == [{"id": 4, "name": "Lot One"}]
    with pytest.raises(ScreeningError):
        adapter._request("https://shaw.sg/internal/escape")

    assert [url for url, _ in opened] == [
        locations, "https://www.shaw.sg/internal/get_simple_locations", "https://shaw.sg/internal/escape"]
    assert all(headers["x-api-forward-to"] == "internal" for _, headers in opened)
    assert all(host_allowed(url, ShawTheatresAdapter.hosts) for url, _ in opened)


def test_responses_are_bounded_in_size_and_malformed_json_is_reported(monkeypatch) -> None:
    fake_upstream(monkeypatch, {
        "https://venue.example/big": (200, {"Content-Type": "text/html"}, b"x" * 5000),
        "https://venue.example/bad.json": (200, {"Content-Type": "application/json"}, b"{nope"),
    })

    with pytest.raises(ScreeningError, match="large"):
        request_bytes("https://venue.example/big", allowed_hosts={"venue.example"}, accept="*/*",
                      max_bytes=1000)
    with pytest.raises(ScreeningError, match="malformed"):
        request_json("https://venue.example/bad.json", allowed_hosts={"venue.example"})
    with pytest.raises(ScreeningError, match="own HTTPS"):
        request_bytes("https://other.example/", allowed_hosts={"venue.example"}, accept="*/*")


def test_only_plain_https_urls_on_listed_hosts_are_allowed() -> None:
    assert host_allowed("https://Shaw.SG/path", {"shaw.sg"})
    assert host_allowed("https://shaw.sg:443/path", {"shaw.sg"})
    for url in ("http://shaw.sg/", "https://shaw.sg.evil.example/", "https://evil.example/?shaw.sg",
                "https://user@shaw.sg/", "https://shaw.sg:8080/", "https://shaw.sg:bad/", "javascript:1"):
        assert not host_allowed(url, {"shaw.sg"}), url


class FakeSocket:
    instances: list["FakeSocket"] = []

    def __init__(self, family, kind, protocol) -> None:
        self.family = family
        self.timeouts: list = []
        self.attempts: list[str] = []
        FakeSocket.instances.append(self)

    def settimeout(self, value) -> None:
        self.timeouts.append(value)

    def connect(self, target) -> None:
        self.attempts.append(target[0])
        if self.family == socket.AF_INET6:
            raise TimeoutError()

    def close(self) -> None:
        pass


def resolve_to(monkeypatch, *addresses: str) -> None:
    def getaddrinfo(host, port, type):
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port, 0, 0)) if ":" in address
            else (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
            for address in addresses
        ]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.fixture
def fake_sockets(monkeypatch):
    FakeSocket.instances = []
    monkeypatch.setattr(socket, "socket", FakeSocket)
    return FakeSocket.instances


def test_connections_try_ipv4_before_an_unanswering_ipv6_address(monkeypatch, fake_sockets) -> None:
    resolve_to(monkeypatch, "2606:4700:4700::1111", "93.184.216.34")

    connect_public_ipv4_first(("sgiff.com", 443), 15)

    assert [attempt for sock in fake_sockets for attempt in sock.attempts] == ["93.184.216.34"]


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0",
    "224.0.0.1", "240.0.0.1", "255.255.255.255", "::1", "::", "fe80::1", "fc00::1", "ff02::1",
    "::ffff:127.0.0.1", "::ffff:10.0.0.1",
])
def test_connections_refuse_non_public_addresses(monkeypatch, fake_sockets, address: str) -> None:
    resolve_to(monkeypatch, address)

    with pytest.raises(OSError, match="public address"):
        connect_public_ipv4_first(("rebound.example", 443), 15)
    assert fake_sockets == []


def test_a_rebound_private_answer_is_skipped_for_the_public_one(monkeypatch, fake_sockets) -> None:
    resolve_to(monkeypatch, "127.0.0.1", "10.0.0.8", "93.184.216.34")

    connect_public_ipv4_first(("venue.example", 443), 15)

    assert [attempt for sock in fake_sockets for attempt in sock.attempts] == ["93.184.216.34"]


@pytest.mark.parametrize("timeout", [None, socket._GLOBAL_DEFAULT_TIMEOUT, "15", True, float("nan"),
                                     float("inf"), -1, 0])
def test_non_numeric_timeouts_never_leave_a_blocking_socket(monkeypatch, fake_sockets, timeout) -> None:
    resolve_to(monkeypatch, "93.184.216.34")

    connect_public_ipv4_first(("venue.example", 443), timeout)

    assert fake_sockets[0].timeouts == [screenings_http.CONNECT_SECONDS, float(screenings_http.READ_SECONDS)]


def test_numeric_timeouts_bound_both_the_connect_window_and_reads(monkeypatch, fake_sockets) -> None:
    resolve_to(monkeypatch, "93.184.216.34")

    connect_public_ipv4_first(("venue.example", 443), 2)
    connect_public_ipv4_first(("venue.example", 443), 30)

    assert [sock.timeouts for sock in fake_sockets] == [[2, 2.0], [5, 30.0]]


def test_slow_poster_hosts_use_their_own_four_threads(monkeypatch) -> None:
    gate = threading.Event()
    lock = threading.Lock()
    active = {"now": 0, "most": 0}

    def slow_upstream(url: str, hosts: frozenset[str]) -> tuple[bytes, str]:
        with lock:
            active["now"] += 1
            active["most"] = max(active["most"], active["now"])
        try:
            assert gate.wait(10), "The test never released the image host."
        finally:
            with lock:
                active["now"] -= 1
        return PNG, "image/png"

    posters = PosterProxy(transport=slow_upstream)
    paths = [posters.register(f"https://img.venue.example/{index}.png", HOSTS) for index in range(7)]
    service = ScreeningsService([], posters=posters)
    monkeypatch.setenv("FIRSTROLL_PUBLIC_MODE", "true")
    application = main.create_api_application(public_mode=True)
    add_screenings_routes(application, service)
    application.add_api_route("/api/health", main.health)

    async def scenario() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            requests = [asyncio.create_task(client.get(str(path))) for path in paths]
            try:
                for _ in range(500):
                    if active["now"] == POSTER_THREADS:
                        break
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.1)
                assert (await asyncio.wait_for(client.get("/api/health"), 5)).status_code == 200
                assert active["most"] == POSTER_THREADS
            finally:
                gate.set()
            return list(await asyncio.wait_for(asyncio.gather(*requests), 10))

    responses = asyncio.run(scenario())

    assert [response.status_code for response in responses] == [200] * 7
    assert active["most"] == POSTER_THREADS
