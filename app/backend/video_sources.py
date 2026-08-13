from __future__ import annotations

import gzip
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
    duration_seconds: int | None = Field(default=None, ge=0)
    category: Literal[
        "full_film",
        "interview",
        "video_essay",
        "lecture",
        "trailer",
        "scene_extract",
        "behind_the_scenes",
        "other",
    ]
    relevance: Literal["title", "director", "title_and_director"]


class FilmVideoBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    film_id: str
    query: str
    fetched_at: str
    videos: list[FilmVideo] = Field(default_factory=list, max_length=12)
    providers: list[str]
    notice: str


VIDEO_CATEGORY_PRIORITY = {
    "full_film": 0,
    "interview": 1,
    "video_essay": 2,
    "lecture": 3,
    "behind_the_scenes": 4,
    "trailer": 5,
    "scene_extract": 6,
    "other": 7,
}


class YouTubeVideoAdapter:
    """Official YouTube Data API search limited to embeddable public videos."""

    api_url = "https://www.googleapis.com/youtube/v3/search"
    videos_api_url = "https://www.googleapis.com/youtube/v3/videos"
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
        candidates: list[tuple[str, dict[str, Any], str]] = []
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
            candidates.append((video_id, snippet, relevance))
        durations = self._video_durations(
            [video_id for video_id, _, _ in candidates],
            key,
        )
        results: list[FilmVideo] = []
        for video_id, snippet, relevance in candidates:
            title = html.unescape(str(snippet.get("title") or "")).strip()
            description = html.unescape(str(snippet.get("description") or "")).strip()
            thumbnails = snippet.get("thumbnails")
            thumbnail = _youtube_thumbnail(thumbnails)
            duration_seconds = durations.get(video_id)
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
                    duration_seconds=duration_seconds,
                    category=_video_category(title, description, duration_seconds),
                    relevance=relevance,
                )
            )
            if len(results) >= limit:
                break
        return results

    def _video_durations(self, video_ids: list[str], key: str) -> dict[str, int]:
        if not video_ids:
            return {}
        url = f"{self.videos_api_url}?{urlencode({'part': 'contentDetails', 'id': ','.join(video_ids), 'key': key})}"
        payload = self.transport(url)
        items = payload.get("items") if isinstance(payload, dict) else []
        durations: dict[str, int] = {}
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            video_id = str(item.get("id") or "")
            details = item.get("contentDetails")
            duration = str(details.get("duration") or "") if isinstance(details, dict) else ""
            seconds = _iso8601_duration_seconds(duration)
            if video_id and seconds is not None:
                durations[video_id] = seconds
        return durations

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

    def __init__(
        self,
        transport: Callable[[str], str] | None = None,
        detail_transport: Callable[[str], str] | None = None,
    ) -> None:
        self.transport = transport or self._request_html
        self.detail_transport = detail_transport or self._request_video_html

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Bilibili public search",
            "state": "ready",
            "configured": True,
            "official": False,
            "content_scope": "public film-related videos",
        }

    def search(self, film: dict[str, Any], limit: int = 6) -> list[FilmVideo]:
        results: list[FilmVideo] = []
        seen: set[str] = set()
        detail_requests = 0
        queries = (_bilibili_video_query(film), _bilibili_full_film_query(film))
        for query in queries:
            body = self.transport(f"{self.search_url}?{urlencode({'keyword': query})}")
            matches = list(self._result_pattern.finditer(body))
            for index, match in enumerate(matches):
                video_id = match.group("bvid")
                if video_id in seen:
                    continue
                title = _decode_javascript_string(match.group("title"))
                description = _decode_javascript_string(match.group("description"))
                tail_end = matches[index + 1].start() if index + 1 < len(matches) else match.end() + 900
                duration_seconds, tags = _bilibili_tail_metadata(body[match.end() : tail_end])
                if (
                    duration_seconds is None
                    and detail_requests < 3
                    and _possible_full_film_candidate(film, f"{title} {description} {tags}")
                ):
                    detail_requests += 1
                    try:
                        detail_body = self.detail_transport(
                            f"https://www.bilibili.com/video/{video_id}/"
                        )
                        duration_seconds = _bilibili_detail_duration(detail_body)
                    except VideoSourceError:
                        pass
                relevance = _video_relevance(film, f"{title} {description} {tags}")
                if relevance is None and _long_film_candidate(
                    film,
                    f"{title} {description} {tags}",
                    duration_seconds,
                ):
                    relevance = "title"
                if relevance is None:
                    continue
                picture = _decode_javascript_string(match.group("picture"))
                if picture.startswith("//"):
                    picture = f"https:{picture}"
                if not _safe_bilibili_image(picture):
                    picture = ""
                clean_title = re.sub(r"<[^>]+>", "", title).strip()
                clean_description = re.sub(r"<[^>]+>", "", description).strip()
                seen.add(video_id)
                results.append(
                    FilmVideo(
                        platform="Bilibili",
                        video_id=video_id,
                        title=clean_title,
                        description=clean_description[:500],
                        url=f"https://www.bilibili.com/video/{video_id}/",
                        embed_url=f"https://player.bilibili.com/player.html?bvid={video_id}&autoplay=0",
                        thumbnail_url=picture or None,
                        duration_seconds=duration_seconds,
                        category=_video_category(
                            clean_title,
                            f"{clean_description} {tags}",
                            duration_seconds,
                        ),
                        relevance=relevance,
                    )
                )
        return sorted(
            results,
            key=lambda video: VIDEO_CATEGORY_PRIORITY[video.category],
        )[:limit]

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
                if response.headers.get("Content-Encoding", "").casefold() == "gzip":
                    payload = gzip.decompress(payload)
                    if len(payload) > cls.max_response_bytes:
                        raise VideoSourceError("Bilibili returned an unexpectedly large page.")
                charset = response.headers.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        except HTTPError as exc:
            raise VideoSourceError(f"Bilibili public search returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError, OSError) as exc:
            raise VideoSourceError(f"Bilibili public search failed: {exc}") from exc

    @classmethod
    def _request_video_html(cls, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "www.bilibili.com":
            raise VideoSourceError("Only public HTTPS video pages on Bilibili may be queried.")
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
                if final.scheme != "https" or final.hostname != "www.bilibili.com":
                    raise VideoSourceError("Bilibili redirected outside its public video host.")
                payload = response.read(cls.max_response_bytes + 1)
                if len(payload) > cls.max_response_bytes:
                    raise VideoSourceError("Bilibili returned an unexpectedly large video page.")
                if response.headers.get("Content-Encoding", "").casefold() == "gzip":
                    payload = gzip.decompress(payload)
                    if len(payload) > cls.max_response_bytes:
                        raise VideoSourceError("Bilibili returned an unexpectedly large video page.")
                charset = response.headers.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        except HTTPError as exc:
            raise VideoSourceError(f"Bilibili video page returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError, OSError) as exc:
            raise VideoSourceError(f"Bilibili video-page request failed: {exc}") from exc


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
            videos=sorted(
                videos,
                key=lambda video: VIDEO_CATEGORY_PRIORITY[video.category],
            )[:12],
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


def _bilibili_full_film_query(film: dict[str, Any]) -> str:
    title = str(film.get("title") or "").strip()
    original_title = str(film.get("original_title") or "").strip()
    year = str(film.get("year") or "").strip()
    # Bilibili search performs better when this query stays compact. Prefer the
    # original title because it often bridges Traditional and Simplified Chinese.
    query_title = original_title or title
    return " ".join(part for part in (query_title, year, "电影", "完整版") if part)


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


def _clock_duration_seconds(value: str) -> int | None:
    parts = value.split(":")
    if len(parts) not in {2, 3} or not all(part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]


def _iso8601_duration_seconds(value: str) -> int | None:
    match = re.fullmatch(
        r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        value,
    )
    if not match:
        return None
    return (
        int(match.group("hours") or 0) * 3600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )


def _bilibili_tail_metadata(value: str) -> tuple[int | None, str]:
    duration_match = re.search(r'"(\d{1,2}:\d{2}(?::\d{2})?)"', value)
    if duration_match is None:
        return None, ""
    quoted = re.findall(r'"((?:\\.|[^"\\])*)"', value[: duration_match.start()])
    tags = _decode_javascript_string(quoted[-1]) if quoted else ""
    return _clock_duration_seconds(duration_match.group(1)), tags


def _video_category(title: str, description: str, duration_seconds: int | None) -> str:
    text = _normalise(f"{title} {description}")
    markers = {
        "behind_the_scenes": ("behind the scenes", "making of", "幕后", "花絮", "制作特辑"),
        "interview": (
            "interview",
            "q a",
            "conversation",
            "press conference",
            "映后",
            "访谈",
            "对谈",
            "专访",
            "记者会",
            "发布会",
        ),
        "lecture": ("lecture", "masterclass", "keynote", "讲座", "大师课"),
        "trailer": ("trailer", "teaser", "preview", "预告"),
        "video_essay": (
            "video essay",
            "analysis",
            "review",
            "explained",
            "critique",
            "影评",
            "解析",
            "精讲",
            "漫谈",
            "看完",
            "盘点",
            "深度",
            "哲思",
            "解说",
            "推荐",
        ),
        "scene_extract": ("scene", "clip", "excerpt", "sequence", "片段", "节选", "cut"),
        "other": ("award ceremony", "颁奖典礼"),
    }
    for category, terms in markers.items():
        if any(term in text for term in terms):
            return category
    explicit_full_film = any(
        term in text
        for term in ("full film", "full movie", "complete film", "完整版", "全片", "正片")
    )
    if explicit_full_film or (duration_seconds is not None and duration_seconds >= 45 * 60):
        return "full_film"
    return "other"


def _long_film_candidate(
    film: dict[str, Any],
    text: str,
    duration_seconds: int | None,
) -> bool:
    if duration_seconds is None or duration_seconds < 45 * 60:
        return False
    body = _normalise(text)
    year = str(film.get("year") or "").strip()
    return bool(
        year
        and year in body
        and (
            any(term in body for term in ("film", "movie", "电影", "影片", "作品"))
            or _possible_full_film_candidate(film, text)
        )
    )


def _possible_full_film_candidate(film: dict[str, Any], text: str) -> bool:
    body = _normalise(text)
    year = str(film.get("year") or "").strip()
    if not year or year not in body:
        return False
    exclusion_markers = (
        "trailer",
        "interview",
        "review",
        "预告",
        "访谈",
        "影评",
        "解析",
        "片段",
        "解说",
        "盘点",
        "游戏",
        "音乐",
    )
    return not any(marker in body for marker in exclusion_markers)


def _bilibili_detail_duration(value: str) -> int | None:
    match = re.search(r'"duration"\s*:\s*(\d+)', value)
    return int(match.group(1)) if match else None
