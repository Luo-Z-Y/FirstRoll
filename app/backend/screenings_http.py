"""Guarded HTTPS transport for Singapore screening listings and poster images.

Every request goes only to HTTPS hosts on the calling source's allow-list. Redirects are
checked before they are followed and capped, connections refuse private and other
non-public addresses (so a rebound DNS answer cannot reach internal services),
environment proxies are not consulted, and every response is bounded in size and time.

The time bound covers the whole request, redirects included: a watchdog shuts the request's
connections down once ``total_seconds`` have passed, so a host that trickles its status line,
headers or body cannot hold a thread past it. Only DNS lookups, which the system resolver
performs, fall outside it.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import threading
import time
from functools import lru_cache
from http.client import HTTPException, HTTPSConnection
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    HTTPDefaultErrorHandler,
    HTTPErrorProcessor,
    HTTPRedirectHandler,
    HTTPSHandler,
    OpenerDirector,
    Request,
    UnknownHandler,
)

USER_AGENT = "Mozilla/5.0 (compatible; FirstRoll/0.1; +https://firstroll.app) screening-listings"
CONNECT_SECONDS = 5
READ_SECONDS = 15
TOTAL_SECONDS = 30
MAX_RESPONSE_BYTES = 4_000_000
MAX_REDIRECTS = 3
CHUNK_BYTES = 64 * 1024
TOO_SLOW_MESSAGE = "The venue website took too long to answer."
UNREACHABLE_MESSAGE = "The venue website could not be reached."

logger = logging.getLogger("firstroll.screenings")


class ScreeningError(RuntimeError):
    """Raised when a venue's public listings cannot be read or understood.

    Messages are FirstRoll's own fixed sentences, never text copied from a venue.
    """


class _WithheldError(Exception):
    """Stands in for a failure whose own message might quote retrieved content."""


def log_source_failure(source: str, exc: BaseException) -> None:
    """Log one failed read with its traceback, withholding any retrieved content.

    A parser bug's exception message can quote the page it choked on, so only FirstRoll's
    own ``ScreeningError`` sentences are logged verbatim; anything else is reduced to its
    type. The traceback shows code locations only.
    """
    summary = str(exc) if isinstance(exc, ScreeningError) else type(exc).__name__
    stand_in = _WithheldError(f"{type(exc).__name__} (message withheld)")
    logger.warning(
        "Screening source %s failed: %s",
        source,
        summary,
        exc_info=(_WithheldError, stand_in, exc.__traceback__),
    )


def normalise_hosts(hosts: Iterable[str]) -> frozenset[str]:
    return frozenset(str(host).casefold() for host in hosts)


def host_allowed(url: str, allowed_hosts: Iterable[str]) -> bool:
    """Whether ``url`` is plain HTTPS on the default port to an allow-listed host."""
    try:
        parsed = urlparse(str(url))
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        return False
    return (parsed.hostname or "").casefold() in normalise_hosts(allowed_hosts)


def require_host(url: str, allowed_hosts: Iterable[str]) -> None:
    if not host_allowed(url, allowed_hosts):
        raise ScreeningError("Listings may be read only from the venue's own HTTPS website.")


def public_address(raw: str) -> bool:
    """Whether a resolved address is a public unicast address worth connecting to."""
    try:
        address = ipaddress.ip_address(str(raw).split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _shut(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


class _Watchdog:
    """Shuts down every connection one request opened once its total time is spent.

    Socket timeouts bound each receive, not the request, so without this a host sending a
    byte now and then could hold a read indefinitely. The watchdog keeps duplicates of the
    connected sockets (wrapping a socket in TLS detaches the original) and shuts them down
    with a plain ``socket.shutdown``. That wakes a read blocked on another thread with an
    end of stream, without touching the TLS object the reading thread is using.
    """

    def __init__(self, seconds: float) -> None:
        self.deadline = time.monotonic() + seconds
        self._expired = threading.Event()
        self._lock = threading.Lock()
        self._sockets: list[socket.socket] = []
        self._closed = False
        self._timer = threading.Timer(max(0.0, seconds), self._cut)
        self._timer.daemon = True
        self._timer.start()

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def spent(self) -> bool:
        return self._expired.is_set() or self.remaining() <= 0

    def add(self, sock: socket.socket) -> None:
        copy = sock.dup()
        with self._lock:
            if self._closed:
                copy.close()
                return
            self._sockets.append(copy)
            if self._expired.is_set():
                _shut(copy)

    def _cut(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._expired.set()
            for copy in self._sockets:
                _shut(copy)

    def close(self) -> None:
        self._timer.cancel()
        with self._lock:
            self._closed = True
            copies, self._sockets = self._sockets, []
        for copy in copies:
            copy.close()


# The watchdog of the request running on this thread, which its connections register with.
_watch = threading.local()


def _timeout_seconds(timeout: Any) -> float:
    """A finite positive timeout; anything else (including the socket sentinel) gets the default."""
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        return float(READ_SECONDS)
    if not 0 < timeout < float("inf"):
        return float(READ_SECONDS)
    return float(timeout)


def connect_public_ipv4_first(
    address: tuple[str, int], timeout: Any = None, source_address: Any = None
) -> socket.socket:
    """Connect to a public address, IPv4 before IPv6, with a short window per address.

    Some venues publish an AAAA record that does not answer, and a plain sequential
    connect would spend the whole request timeout there before trying IPv4. Resolution
    and connection happen here together, so the address checked is the address used.
    Inside ``request_bytes`` each connect window also stays within the request's remaining
    time, and the connected socket is handed to its watchdog.
    """
    host, port = address
    limit = _timeout_seconds(timeout)
    watchdog: _Watchdog | None = getattr(_watch, "current", None)
    candidates = [
        candidate
        for candidate in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if public_address(str(candidate[4][0]))
    ]
    if not candidates:
        raise OSError(f"{host} does not resolve to a public address.")
    candidates.sort(key=lambda candidate: candidate[0] != socket.AF_INET)
    failure: OSError | None = None
    for family, kind, protocol, _, target in candidates:
        window = min(limit, CONNECT_SECONDS)
        if watchdog is not None:
            window = min(window, watchdog.remaining())
            if window <= 0:
                raise TimeoutError(f"The time allowed for {host} ran out.")
        sock = socket.socket(family, kind, protocol)
        try:
            sock.settimeout(window)
            if source_address:
                sock.bind(source_address)
            sock.connect(target)
            sock.settimeout(limit)
            if watchdog is not None:
                watchdog.add(sock)
            return sock
        except OSError as exc:
            failure = exc
            sock.close()
    raise failure or OSError(f"No address found for {host}.")


class _GuardedConnection(HTTPSConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = connect_public_ipv4_first


class _GuardedHTTPSHandler(HTTPSHandler):
    def https_open(self, req: Request) -> Any:
        return self.do_open(_GuardedConnection, req, context=self._context)  # type: ignore[attr-defined]


class GuardedRedirectHandler(HTTPRedirectHandler):
    """Follow at most three redirects, each checked against the allow-list first."""

    max_redirections = MAX_REDIRECTS

    def __init__(self, allowed_hosts: Iterable[str]) -> None:
        super().__init__()
        self.allowed_hosts = normalise_hosts(allowed_hosts)

    def redirect_request(  # type: ignore[override]
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Request | None:
        if not host_allowed(newurl, self.allowed_hosts):
            fp.close()
            raise ScreeningError("The venue redirected to a website FirstRoll does not read.")
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        # The standard handler reads the whole redirect body before following it, outside
        # the size and time limits. Closed first, that read finds nothing to buffer; every
        # request sends ``Connection: close``, so the connection is never reused anyway.
        fp.close()
        return new


@lru_cache(maxsize=64)
def guarded_opener(allowed_hosts: frozenset[str]) -> OpenerDirector:
    """An opener with HTTPS only, guarded connections and guarded redirects.

    It is assembled by hand rather than with ``build_opener`` so that no plain HTTP, FTP,
    file or data handler, and no environment proxy, is ever available to it.
    """
    opener = OpenerDirector()
    for handler in (
        UnknownHandler(),
        _GuardedHTTPSHandler(),
        HTTPDefaultErrorHandler(),
        GuardedRedirectHandler(allowed_hosts),
        HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


def request_bytes(
    url: str,
    *,
    allowed_hosts: Iterable[str],
    accept: str,
    headers: dict[str, str] | None = None,
    timeout: float = READ_SECONDS,
    max_bytes: int = MAX_RESPONSE_BYTES,
    total_seconds: float = TOTAL_SECONDS,
) -> tuple[bytes, str, str | None]:
    """Fetch one bounded HTTPS response; returns its body, media type and charset.

    ``timeout`` bounds each connection attempt and each receive; ``total_seconds`` bounds
    the whole request, redirects included (DNS lookups aside).
    """
    hosts = normalise_hosts(allowed_hosts)
    require_host(url, hosts)
    request = Request(
        url,
        headers={
            "Accept": accept,
            "Accept-Language": "en-GB,en;q=0.8",
            "User-Agent": USER_AGENT,
            **(headers or {}),
        },
        method="GET",
    )
    watchdog = _Watchdog(total_seconds)
    outer = getattr(_watch, "current", None)
    _watch.current = watchdog
    try:
        with guarded_opener(hosts).open(request, timeout=timeout) as response:
            require_host(response.geturl(), hosts)
            chunks: list[bytes] = []
            size = 0
            # ``read1`` returns after at most one receive, so the limits are checked after
            # every network read rather than once per 64 KiB.
            while chunk := response.read1(CHUNK_BYTES):
                size += len(chunk)
                if size > max_bytes:
                    raise ScreeningError("The venue returned an unexpectedly large response.")
                if watchdog.spent():
                    raise ScreeningError(TOO_SLOW_MESSAGE)
                chunks.append(chunk)
            # A connection the watchdog shut down ends like a short, clean response.
            if watchdog.spent():
                raise ScreeningError(TOO_SLOW_MESSAGE)
            return (
                b"".join(chunks),
                str(response.headers.get_content_type()),
                response.headers.get_content_charset(),
            )
    except HTTPError as exc:
        exc.close()
        if watchdog.spent():
            raise ScreeningError(TOO_SLOW_MESSAGE) from exc
        raise ScreeningError(f"The venue website returned HTTP {exc.code}.") from exc
    # ValueError covers a URL http.client cannot encode, such as one with raw non-ASCII text.
    except (URLError, HTTPException, TimeoutError, OSError, ValueError) as exc:
        if watchdog.spent():
            raise ScreeningError(TOO_SLOW_MESSAGE) from exc
        raise ScreeningError(UNREACHABLE_MESSAGE) from exc
    finally:
        _watch.current = outer
        watchdog.close()


def request_text(
    url: str,
    *,
    allowed_hosts: Iterable[str],
    accept: str = "text/html",
    headers: dict[str, str] | None = None,
) -> str:
    """Fetch one bounded public HTTPS document from an expected host."""
    body, _, charset = request_bytes(url, allowed_hosts=allowed_hosts, accept=accept, headers=headers)
    try:
        return body.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def request_json(
    url: str, *, allowed_hosts: Iterable[str], headers: dict[str, str] | None = None
) -> Any:
    body = request_text(url, allowed_hosts=allowed_hosts, accept="application/json", headers=headers)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ScreeningError("The venue returned malformed listing data.") from exc
