from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from app.backend.settings import LocalSettingsStore


class VideoSourceError(RuntimeError):
    """Raised when a video provider cannot return safe, relevant results."""


class FilmVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["YouTube", "Bilibili"]
    video_id: str
    title: str
    creator: str | None = None
    description: str = ""
    url: str
    embed_url: str
    thumbnail_url: str | None = None
    published_at: str | None = None
    relevance: Literal["title", "director", "title_and_director"]


class FilmVideoBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    film_id: str
    query: str
    fetched_at: str
    videos: list[FilmVideo] = Field(default_factory=list, max_length=12)
    providers: list[str]
    notice: str


class YouTubeVideoAdapter:
    """Official YouTube Data API search limited to embeddable public videos."""

    api_url = "https://www.googleapis.com/youtube/v3/search"
    max_response_bytes = 2_000_000

    def __init__(
        self,
        settings: LocalSettingsStore,
        transport: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport or self._request_json

    def status(self) -> dict[str, Any]:
        configured = self.settings.secret_state("youtube").configured
        return {
            "provider": "YouTube Data API",
            "state": "ready" if configured else "credentials_required",
            "configured": configured,
            "official": True,
            "content_scope": "public embeddable film-related videos",
        }

    def test_connection(self) -> dict[str, Any]:
        key = self.settings.effective_secret("youtube")
        if not key:
            raise VideoSourceError("Add a YouTube Data API key in Settings first.")
        payload = self.transport(
            f"{self.api_url}?{urlencode({'part': 'snippet', 'q': 'film', 'type': 'video', 'maxResults': '1', 'key': key})}"
        )
        if not isinstance(payload.get("items"), list):
            raise VideoSourceError("YouTube returned an invalid search response.")
        return {"message": "YouTube Data API search succeeded."}

    def search(self, film: dict[str, Any], limit: int = 6) -> list[FilmVideo]:
        key = self.settings.effective_secret("youtube")
        if not key:
            return []
        query = _film_video_query(film)
        url = f"{self.api_url}?{urlencode({'part': 'snippet', 'q': query, 'type': 'video', 'maxResults': str(max(1, min(limit * 2, 20))), 'videoEmbeddable': 'true', 'videoSyndicated': 'true', 'safeSearch': 'moderate', 'relevanceLanguage': 'en', 'key': key})}"
        payload = self.transport(url)
        items = payload.get("items") if isinstance(payload, dict) else []
        results: list[FilmVideo] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            identifier = item.get("id")
            snippet = item.get("snippet")
            video_id = str(identifier.get("videoId") or "") if isinstance(identifier, dict) else ""
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or not isinstance(snippet, dict):
                continue
            title = html.unescape(str(snippet.get("title") or "")).strip()
            description = html.unescape(str(snippet.get("description") or "")).strip()
            relevance = _video_relevance(film, f"{title} {description}")
            if relevance is None:
                continue
            thumbnails = snippet.get("thumbnails")
            thumbnail = _youtube_thumbnail(thumbnails)
            results.append(
                FilmVideo(
                    platform="YouTube",
                    video_id=video_id,
                    title=title,
                    creator=str(snippet.get("channelTitle") or "").strip() or None,
                    description=description[:500],
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    embed_url=f"https://www.youtube-nocookie.com/embed/{video_id}",
                    thumbnail_url=thumbnail,
                    published_at=str(snippet.get("publishedAt") or "").strip() or None,
                    relevance=relevance,
                )
            )
            if len(results) >= limit:
                break
        return results

    @classmethod
    def _request_json(cls, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com":
            raise VideoSourceError("Only the official YouTube Data API may be queried.")
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read(cls.max_response_bytes + 1)
                if len(payload) > cls.max_response_bytes:
                    raise VideoSourceError("YouTube returned an unexpectedly large response.")
                value = json.loads(payload.decode("utf-8"))
        except HTTPError as exc:
            raise VideoSourceError(f"YouTube search returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise VideoSourceError(f"YouTube search failed: {exc}") from exc
        if not isinstance(value, dict):
            raise VideoSourceError("YouTube returned an invalid response.")
        return value


class BilibiliPublicVideoAdapter:
    """Bounded parser for Bilibili's public server-rendered search page."""

    search_url = "https://search.bilibili.com/video"
    max_response_bytes = 4_000_000
    _result_pattern = re.compile(
        r'"http:\\u002F\\u002Fwww\.bilibili\.com\\u002Fvideo\\u002Fav\d+",'
        r'"(?P<bvid>BV[A-Za-z0-9]{10})",'
        r'"(?P<title>(?:\\.|[^"\\])*)",'
        r'"(?P<description>(?:\\.|[^"\\])*)",'
        r'"(?P<picture>(?:\\.|[^"\\])*)"'
    )

    def __init__(self, transport: Callable[[str], str] | None = None) -> None:
        self.transport = transport or self._request_html

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Bilibili public search",
            "state": "ready",
            "configured": True,
            "official": False,
            "content_scope": "public film-related videos",
        }

    def search(self, film: dict[str, Any], limit: int = 6) -> list[FilmVideo]:
        query = _bilibili_video_query(film)
        body = self.transport(f"{self.search_url}?{urlencode({'keyword': query})}")
        results: list[FilmVideo] = []
        seen: set[str] = set()
        for match in self._result_pattern.finditer(body):
            video_id = match.group("bvid")
            if video_id in seen:
                continue
            title = _decode_javascript_string(match.group("title"))
            description = _decode_javascript_string(match.group("description"))
            relevance = _video_relevance(film, f"{title} {description}")
            if relevance is None:
                continue
            picture = _decode_javascript_string(match.group("picture"))
            if picture.startswith("//"):
                picture = f"https:{picture}"
            if not _safe_bilibili_image(picture):
                picture = ""
            seen.add(video_id)
            results.append(
                FilmVideo(
                    platform="Bilibili",
                    video_id=video_id,
                    title=re.sub(r"<[^>]+>", "", title).strip(),
                    description=re.sub(r"<[^>]+>", "", description).strip()[:500],
                    url=f"https://www.bilibili.com/video/{video_id}/",
                    embed_url=f"https://player.bilibili.com/player.html?bvid={video_id}&autoplay=0",
                    thumbnail_url=picture or None,
                    relevance=relevance,
                )
            )
            if len(results) >= limit:
                break
        return results

    @classmethod
    def _request_html(cls, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "search.bilibili.com":
            raise VideoSourceError("Only Bilibili's public HTTPS search page may be queried.")
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "User-Agent": "Mozilla/5.0 FirstRoll/0.1 local-film-study",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                final = urlparse(response.geturl())
                if final.scheme != "https" or final.hostname != "search.bilibili.com":
                    raise VideoSourceError("Bilibili redirected outside its public search host.")
                payload = response.read(cls.max_response_bytes + 1)
                if len(payload) > cls.max_response_bytes:
                    raise VideoSourceError("Bilibili returned an unexpectedly large page.")
                charset = response.headers.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        except HTTPError as exc:
            raise VideoSourceError(f"Bilibili public search returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError) as exc:
            raise VideoSourceError(f"Bilibili public search failed: {exc}") from exc


class FilmVideoService:
    def __init__(
        self,
        youtube: YouTubeVideoAdapter,
        bilibili: BilibiliPublicVideoAdapter,
    ) -> None:
        self.youtube = youtube
        self.bilibili = bilibili

    def status(self) -> dict[str, Any]:
        return {"youtube": self.youtube.status(), "bilibili": self.bilibili.status()}

    def search(self, film_id: str, film: dict[str, Any]) -> FilmVideoBundle:
        videos: list[FilmVideo] = []
        providers: list[str] = []
        failures: list[str] = []
        for name, adapter in (("YouTube", self.youtube), ("Bilibili", self.bilibili)):
            try:
                found = adapter.search(film, limit=6)
            except VideoSourceError as exc:
                failures.append(f"{name}: {exc}")
                continue
            if found:
                providers.append(name)
                videos.extend(found)
        if not videos:
            detail = f" Provider details: {'; '.join(failures)}" if failures else ""
            raise VideoSourceError(
                "No confidently matched embeddable videos were found for this film."
                f"{detail}"
            )
        return FilmVideoBundle(
            film_id=film_id,
            query=_film_video_query(film),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            videos=videos[:12],
            providers=providers,
            notice=(
                "Public videos selected by film-title and director relevance. "
                "FirstRoll does not verify every claim made in third-party videos."
            ),
        )


def _film_video_query(film: dict[str, Any]) -> str:
    title = str(film.get("title") or "").strip()
    directors = film.get("credits", {}).get("directors") or film.get("directors") or []
    director = str(directors[0]).strip() if directors else ""
    year = str(film.get("year") or "").strip()
    return " ".join(part for part in (title, director, year, "film") if part)


def _bilibili_video_query(film: dict[str, Any]) -> str:
    title = str(film.get("title") or "").strip()
    original_title = str(film.get("original_title") or "").strip()
    year = str(film.get("year") or "").strip()
    return " ".join(
        part
        for part in (title, original_title, year, "电影", "影评", "访谈")
        if part
    )


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", html.unescape(value))
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()


def _video_relevance(
    film: dict[str, Any],
    text: str,
) -> Literal["title", "director", "title_and_director"] | None:
    body = _normalise(text)
    titles = [
        _normalise(str(value))
        for value in (film.get("title"), film.get("original_title"))
        if value
    ]
    directors = film.get("credits", {}).get("directors") or film.get("directors") or []
    director_names = [_normalise(str(value)) for value in directors if value]
    title_match = any(
        title in body
        or SequenceMatcher(None, title, " ".join(body.split()[: max(1, len(title.split()) + 2)])).ratio()
        >= 0.78
        for title in titles
        if title
    )
    director_match = any(
        director in body or (director.split() and director.split()[-1] in body.split())
        for director in director_names
        if director
    )
    film_context = any(
        term in body
        for term in (
            "film",
            "cinema",
            "movie",
            "director",
            "interview",
            "review",
            "trailer",
            "essay",
            "scene",
            "电影",
            "影片",
            "导演",
            "影评",
            "访谈",
            "预告",
            "解析",
            "片段",
            "作品",
        )
    )
    year = str(film.get("year") or "").strip()
    ambiguous_title = bool(titles) and all(len(title.split()) <= 2 for title in titles)
    if ambiguous_title and title_match and not (
        director_match or (film_context and year and year in body)
    ):
        title_match = False
    if title_match and director_match:
        return "title_and_director"
    if title_match:
        return "title"
    if director_match:
        return "director"
    return None


def _youtube_thumbnail(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("high", "medium", "default"):
        item = value.get(key)
        url = str(item.get("url") or "") if isinstance(item, dict) else ""
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname in {
            "i.ytimg.com",
            "img.youtube.com",
        }:
            return url
    return None


def _decode_javascript_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def _safe_bilibili_image(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(
        parsed.hostname and parsed.hostname.endswith(".hdslb.com")
    )
