from __future__ import annotations

import gzip
import html
import json
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from app.backend.settings import LocalSettingsStore


class VideoSourceError(RuntimeError):
    """Raised when a video provider cannot return safe, relevant results."""


class VideoTextTrack(BaseModel):
    """Public textual material attached to a video, retained with its provenance."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["captions", "auto_captions"]
    language: str = "und"
    text: str = Field(min_length=1, max_length=12_000)
    source_url: str
    speaker_verified: bool = False


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
    text_tracks: list[VideoTextTrack] = Field(default_factory=list, max_length=3)
    text_checked_at: str | None = None
    availability_checked_at: str | None = None


class FilmVideoBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    film_id: str
    query: str
    fetched_at: str
    videos: list[FilmVideo] = Field(default_factory=list, max_length=48)
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

VIDEO_AVAILABILITY_TTL = timedelta(hours=6)


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

    def search(
        self,
        film: dict[str, Any],
        limit: int = 6,
        api_key: str | None = None,
    ) -> list[FilmVideo]:
        key = api_key or self.settings.effective_secret("youtube")
        if not key:
            return []
        query = _film_video_query(film)
        url = f"{self.api_url}?{urlencode({'part': 'snippet', 'q': query, 'type': 'video', 'maxResults': str(max(1, min(limit * 2, 25))), 'videoEmbeddable': 'true', 'videoSyndicated': 'true', 'safeSearch': 'moderate', 'relevanceLanguage': 'en', 'key': key})}"
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
        details = self._video_details(
            [video_id for video_id, _, _ in candidates],
            key,
        )
        checked_at = datetime.now(timezone.utc).isoformat()
        results: list[FilmVideo] = []
        for video_id, snippet, relevance in candidates:
            video_details = details.get(video_id)
            if video_details is None:
                continue
            title = html.unescape(str(snippet.get("title") or "")).strip()
            description = html.unescape(str(snippet.get("description") or "")).strip()
            thumbnails = snippet.get("thumbnails")
            thumbnail = _youtube_thumbnail(thumbnails)
            duration_seconds = video_details["duration_seconds"]
            results.append(
                FilmVideo(
                    platform="YouTube",
                    video_id=video_id,
                    title=title,
                    creator=str(snippet.get("channelTitle") or "").strip() or None,
                    description=description[:4000],
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    embed_url=f"https://www.youtube-nocookie.com/embed/{video_id}",
                    thumbnail_url=thumbnail,
                    published_at=str(snippet.get("publishedAt") or "").strip() or None,
                    duration_seconds=duration_seconds,
                    category=_video_category(title, description, duration_seconds),
                    relevance=relevance,
                    availability_checked_at=checked_at,
                )
            )
            if len(results) >= limit:
                break
        return results

    def _video_details(self, video_ids: list[str], key: str) -> dict[str, dict[str, Any]]:
        if not video_ids:
            return {}
        url = f"{self.videos_api_url}?{urlencode({'part': 'contentDetails,status', 'id': ','.join(video_ids), 'key': key})}"
        payload = self.transport(url)
        items = payload.get("items") if isinstance(payload, dict) else []
        details_by_id: dict[str, dict[str, Any]] = {}
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            video_id = str(item.get("id") or "")
            content_details = item.get("contentDetails")
            status = item.get("status")
            if not _youtube_status_is_playable(status):
                continue
            duration = (
                str(content_details.get("duration") or "")
                if isinstance(content_details, dict)
                else ""
            )
            seconds = _iso8601_duration_seconds(duration)
            if video_id:
                details_by_id[video_id] = {"duration_seconds": seconds}
        return details_by_id

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
        # Unit callers can inject only search HTML to test parsing. Production
        # and callers that provide a detail transport validate every accepted
        # result against its current public video page.
        self.validate_results = transport is None or detail_transport is not None

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
        detail_pages: dict[str, str] = {}
        queries = _bilibili_video_queries(film)
        for query in queries:
            body = self.transport(f"{self.search_url}?{urlencode({'keyword': query})}")
            matches = list(self._result_pattern.finditer(body))
            for index, match in enumerate(matches):
                video_id = match.group("bvid")
                if video_id in seen:
                    continue
                seen.add(video_id)
                title = _decode_javascript_string(match.group("title"))
                description = _decode_javascript_string(match.group("description"))
                tail_end = matches[index + 1].start() if index + 1 < len(matches) else match.end() + 900
                duration_seconds, tags = _bilibili_tail_metadata(body[match.end() : tail_end])
                detail_body: str | None = None
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
                        detail_pages[video_id] = detail_body
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
                if not _bilibili_result_matches_film(
                    film,
                    f"{title} {description} {tags}",
                ):
                    continue
                picture = _decode_javascript_string(match.group("picture"))
                if picture.startswith("//"):
                    picture = f"https:{picture}"
                if not _safe_bilibili_image(picture):
                    picture = ""
                clean_title = re.sub(r"<[^>]+>", "", title).strip()
                clean_description = re.sub(r"<[^>]+>", "", description).strip()
                results.append(
                    FilmVideo(
                        platform="Bilibili",
                        video_id=video_id,
                        title=clean_title,
                        description=clean_description[:4000],
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
        ordered = sorted(
            results,
            key=lambda video: VIDEO_CATEGORY_PRIORITY[video.category],
        )
        if self.validate_results:
            ordered = self._available_results(
                ordered[: max(limit * 2, 16)],
                detail_pages,
            )
        return ordered[:limit]

    def _available_results(
        self,
        videos: list[FilmVideo],
        detail_pages: dict[str, str],
    ) -> list[FilmVideo]:
        checked_at = datetime.now(timezone.utc).isoformat()

        def validate(video: FilmVideo) -> FilmVideo | None:
            try:
                body = detail_pages.get(video.video_id) or self.detail_transport(video.url)
            except VideoSourceError:
                return None
            if not _bilibili_page_is_available(body, video.video_id):
                return None
            return video.model_copy(update={"availability_checked_at": checked_at})

        # Detail pages are independent and slow provider requests. A small
        # fixed worker pool keeps the endpoint bounded without hammering the
        # public host or making visitors wait for every check serially.
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="bilibili-check") as pool:
            return [video for video in pool.map(validate, videos) if video is not None]

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
            with urlopen(request, timeout=8) as response:
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


class PublicVideoTextExtractor:
    """Best-effort extraction of public caption tracks without user session credentials."""

    max_page_bytes = 4_000_000
    max_caption_bytes = 2_000_000

    def __init__(
        self,
        page_transport: Callable[[str], str] | None = None,
        caption_transport: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.page_transport = page_transport or self._request_page
        self.caption_transport = caption_transport or self._request_caption_json

    def enrich(self, videos: list[FilmVideo], limit: int = 6) -> list[FilmVideo]:
        enriched: list[FilmVideo] = []
        requests = 0
        eligible = {"interview", "video_essay", "lecture", "behind_the_scenes"}
        for video in videos:
            if (
                video.platform == "YouTube"
                and video.category in eligible
                and not video.text_tracks
                and not video.text_checked_at
                and requests < limit
            ):
                requests += 1
                try:
                    tracks = self._youtube_tracks(video)
                except (VideoSourceError, ValueError, TypeError, json.JSONDecodeError):
                    tracks = []
                video = video.model_copy(
                    update={
                        "text_tracks": tracks,
                        "text_checked_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            enriched.append(video)
        return enriched

    def _youtube_tracks(self, video: FilmVideo) -> list[VideoTextTrack]:
        page_url = f"https://www.youtube.com/watch?{urlencode({'v': video.video_id})}"
        body = self.page_transport(page_url)
        raw_tracks = _json_array_after_key(body, '"captionTracks":')
        if not raw_tracks:
            return []
        candidates = json.loads(raw_tracks)
        if not isinstance(candidates, list):
            return []
        ordered = sorted(
            (item for item in candidates if isinstance(item, dict) and item.get("baseUrl")),
            key=lambda item: (item.get("kind") == "asr", item.get("languageCode") != "en"),
        )
        tracks: list[VideoTextTrack] = []
        for item in ordered[:2]:
            try:
                base_url = html.unescape(str(item.get("baseUrl") or ""))
                caption_url = _caption_json_url(base_url)
                payload = self.caption_transport(caption_url)
                text = _youtube_caption_text(payload)
            except (VideoSourceError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if len(text) < 40:
                continue
            tracks.append(
                VideoTextTrack(
                    kind="auto_captions" if item.get("kind") == "asr" else "captions",
                    language=str(item.get("languageCode") or "und"),
                    text=text[:12_000],
                    source_url=video.url,
                )
            )
        return tracks

    @classmethod
    def _request_page(cls, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"youtube.com", "www.youtube.com"}:
            raise VideoSourceError("Only public YouTube watch pages may be queried for captions.")
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-GB,en;q=0.8",
                "User-Agent": "Mozilla/5.0 FirstRoll/0.1 public-caption-import",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                final = urlparse(response.geturl())
                if final.scheme != "https" or final.hostname not in {
                    "youtube.com",
                    "www.youtube.com",
                }:
                    raise VideoSourceError("YouTube redirected outside its public watch host.")
                payload = response.read(cls.max_page_bytes + 1)
                if len(payload) > cls.max_page_bytes:
                    raise VideoSourceError("YouTube returned an unexpectedly large watch page.")
                return payload.decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise VideoSourceError(f"YouTube caption discovery failed: {exc}") from exc

    @classmethod
    def _request_caption_json(cls, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        allowed = {"youtube.com", "www.youtube.com", "video.google.com", "www.youtube-nocookie.com"}
        if parsed.scheme != "https" or parsed.hostname not in allowed:
            raise VideoSourceError("YouTube returned an unsupported caption host.")
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=20) as response:
                final = urlparse(response.geturl())
                if final.scheme != "https" or final.hostname not in allowed:
                    raise VideoSourceError("YouTube redirected outside its caption hosts.")
                payload = response.read(cls.max_caption_bytes + 1)
                if len(payload) > cls.max_caption_bytes:
                    raise VideoSourceError("YouTube returned an unexpectedly large caption track.")
                value = json.loads(payload.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise VideoSourceError(f"YouTube caption retrieval failed: {exc}") from exc
        return value if isinstance(value, dict) else {}


class FilmVideoService:
    def __init__(
        self,
        youtube: YouTubeVideoAdapter,
        bilibili: BilibiliPublicVideoAdapter,
        store: FilmVideoStore | None = None,
        text_extractor: PublicVideoTextExtractor | None = None,
    ) -> None:
        self.youtube = youtube
        self.bilibili = bilibili
        self.store = store or FilmVideoStore()
        self.text_extractor = text_extractor or PublicVideoTextExtractor()

    def status(self) -> dict[str, Any]:
        return {"youtube": self.youtube.status(), "bilibili": self.bilibili.status()}

    def search(
        self,
        film_id: str,
        film: dict[str, Any],
        youtube_api_key: str | None = None,
    ) -> FilmVideoBundle:
        existing = self.store.load(film_id)
        existing_videos = [
            video
            for video in (existing.videos if existing else [])
            if _availability_is_fresh(video)
        ]
        expired_count = len(existing.videos if existing else []) - len(existing_videos)
        fresh_videos: list[FilmVideo] = []
        providers: list[str] = []
        failures: list[str] = []
        for name, adapter in (("YouTube", self.youtube), ("Bilibili", self.bilibili)):
            try:
                if name == "YouTube" and youtube_api_key:
                    found = adapter.search(film, limit=12, api_key=youtube_api_key)
                else:
                    found = adapter.search(film, limit=12)
            except VideoSourceError as exc:
                failures.append(f"{name}: {exc}")
                continue
            if found:
                providers.append(name)
                fresh_videos.extend(found)
        videos = _merge_videos(existing_videos, fresh_videos)
        videos = _revalidate_videos(film, videos)
        videos = self.text_extractor.enrich(videos)
        if not videos:
            detail = f" Provider details: {'; '.join(failures)}" if failures else ""
            raise VideoSourceError(
                "No confidently matched embeddable videos were found for this film."
                f"{detail}"
            )
        provider_names = list(existing.providers) if existing else []
        provider_names.extend(name for name in providers if name not in provider_names)
        added_count = len(videos) - len(existing_videos)
        bundle = FilmVideoBundle(
            film_id=film_id,
            query=_film_video_query(film),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            videos=videos,
            providers=provider_names,
            notice=(
                f"Verified catalogue: {len(videos)} video{'s' if len(videos) != 1 else ''}; "
                f"{max(0, added_count)} added by this search; "
                f"{expired_count} expired result{'s' if expired_count != 1 else ''} removed. "
                "Availability is checked before display and expires after six hours. "
                "FirstRoll does not verify every claim made in third-party videos."
            ),
        )
        self.store.save(bundle)
        return bundle

    def cached_for_display(self, film_id: str) -> FilmVideoBundle | None:
        """Return only recently availability-checked cached embeds."""
        bundle = self.store.load(film_id)
        if bundle is None:
            return None
        videos = [video for video in bundle.videos if _availability_is_fresh(video)]
        if not videos:
            return None
        if videos != bundle.videos:
            bundle = bundle.model_copy(update={"videos": videos})
            self.store.save(bundle)
        return bundle

    def enrich_cached(self, film_id: str) -> FilmVideoBundle | None:
        """Materialise public caption text for an existing catalogue before synthesis."""
        bundle = self.store.load(film_id)
        if bundle is None:
            return None
        videos = self.text_extractor.enrich(bundle.videos)
        if videos != bundle.videos:
            bundle = bundle.model_copy(update={"videos": videos})
            self.store.save(bundle)
        return bundle


class FilmVideoStore:
    """Private persistent catalogue of accepted viewing resources."""

    def __init__(self, directory: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.directory = directory or project_root / ".firstroll" / "videos"

    def save(self, bundle: FilmVideoBundle) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(bundle.film_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)

    def load(self, film_id: str) -> FilmVideoBundle | None:
        path = self._path(film_id)
        if not path.is_file():
            return None
        try:
            return FilmVideoBundle.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _path(self, film_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", film_id).strip("-") or "film"
        return self.directory / f"{safe}.json"


def _json_array_after_key(body: str, key: str) -> str | None:
    """Return one balanced JSON array following a known page-state key."""
    key_index = body.find(key)
    if key_index < 0:
        return None
    start = body.find("[", key_index + len(key))
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, min(len(body), start + 500_000)):
        character = body[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                return body[start : index + 1]
    return None


def _caption_json_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    allowed = {"youtube.com", "www.youtube.com", "video.google.com", "www.youtube-nocookie.com"}
    if parsed.scheme != "https" or parsed.hostname not in allowed:
        raise VideoSourceError("YouTube returned an unsupported caption host.")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["fmt"] = "json3"
    return urlunparse(parsed._replace(query=urlencode(query)))


def _youtube_caption_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for event in payload.get("events", []):
        if not isinstance(event, dict):
            continue
        segments = event.get("segs")
        if not isinstance(segments, list):
            continue
        line = "".join(
            str(segment.get("utf8") or "")
            for segment in segments
            if isinstance(segment, dict)
        )
        line = re.sub(r"\s+", " ", html.unescape(line)).strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return "\n".join(lines)


def _film_video_query(film: dict[str, Any]) -> str:
    title = str(film.get("title") or "").strip()
    directors = film.get("credits", {}).get("directors") or film.get("directors") or []
    director = str(directors[0]).strip() if directors else ""
    year = str(film.get("year") or "").strip()
    return " ".join(part for part in (title, director, year, "film") if part)


def _bilibili_video_queries(film: dict[str, Any]) -> tuple[str, ...]:
    titles = _film_titles(film)
    title = titles[0] if titles else ""
    year = str(film.get("year") or "").strip()
    provider_titles = _unique_titles(
        [
            *(film.get("alternative_titles") or []),
            film.get("original_title"),
            film.get("title"),
        ]
    )
    cjk_titles = [value for value in provider_titles if re.search(r"[\u3400-\u9fff]", value)]
    exact_titles = [*cjk_titles, *provider_titles]
    primary = exact_titles[0] if exact_titles else title
    bases = [
        *exact_titles,
        " ".join(part for part in (primary, "完整无删减") if part),
        " ".join(part for part in (primary, "完整版") if part),
        " ".join(part for part in (title, year, "影评 解析") if part),
        " ".join(part for part in (title, year, "访谈 映后") if part),
        " ".join(part for part in (title, year, "幕后 片段") if part),
    ]
    return tuple(dict.fromkeys(query for query in bases if query))[:10]


def _availability_is_fresh(
    video: FilmVideo,
    now: datetime | None = None,
) -> bool:
    if not video.availability_checked_at:
        return False
    try:
        checked_at = datetime.fromisoformat(video.availability_checked_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return timedelta(0) <= current - checked_at <= VIDEO_AVAILABILITY_TTL


def _merge_videos(
    existing: list[FilmVideo],
    fresh: list[FilmVideo],
) -> list[FilmVideo]:
    keys: list[tuple[str, str]] = []
    videos_by_key: dict[tuple[str, str], FilmVideo] = {}
    for video in [*existing, *fresh]:
        key = (video.platform, video.video_id)
        if key not in videos_by_key:
            keys.append(key)
        elif previous := videos_by_key.get(key):
            video = video.model_copy(
                update={
                    "text_tracks": video.text_tracks or previous.text_tracks,
                    "text_checked_at": video.text_checked_at or previous.text_checked_at,
                    "availability_checked_at": (
                        video.availability_checked_at
                        or previous.availability_checked_at
                    ),
                }
            )
        videos_by_key[key] = video
    ordered = [videos_by_key[key] for key in keys]
    return sorted(
        ordered,
        key=lambda video: VIDEO_CATEGORY_PRIORITY[video.category],
    )[:48]


def _revalidate_videos(film: dict[str, Any], videos: list[FilmVideo]) -> list[FilmVideo]:
    """Apply current classification and identity rules to fresh and persisted results."""
    accepted: list[FilmVideo] = []
    for video in videos:
        category = (
            _video_category(video.title, video.description, video.duration_seconds)
            if video.category == "full_film"
            else video.category
        )
        video = video.model_copy(update={"category": category})
        if video.platform == "Bilibili" and not _bilibili_result_matches_film(
            film,
            f"{video.title} {video.description}",
        ):
            continue
        accepted.append(video)
    return sorted(
        accepted,
        key=lambda video: VIDEO_CATEGORY_PRIORITY[video.category],
    )[:48]


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", html.unescape(value))
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()


def _video_relevance(
    film: dict[str, Any],
    text: str,
) -> Literal["title", "director", "title_and_director"] | None:
    body = _normalise(text)
    titles = [_normalise(value) for value in _film_titles(film)]
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
            "reaction",
            "analysis",
            "trailer",
            "essay",
            "scene",
            "电影",
            "影片",
            "导演",
            "影评",
            "解说",
            "闲聊",
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


def _youtube_status_is_playable(value: Any) -> bool:
    """Accept only processed, public videos whose owner permits embedding."""
    if not isinstance(value, dict):
        return False
    return (
        value.get("uploadStatus") == "processed"
        and value.get("privacyStatus") == "public"
        and value.get("embeddable") is True
    )


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
            "reaction",
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
        for term in (
            "full film",
            "full movie",
            "complete film",
            "完整版",
            "完整无删",
            "完整无删减",
            "无删减",
            "未删减",
            "全片",
            "正片",
        )
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
    strong_title = _strong_film_title_match(film, text)
    return bool(
        strong_title
        and (
            (
                year
                and year in body
                and (
                    any(term in body for term in ("film", "movie", "电影", "影片", "作品"))
                    or _possible_full_film_candidate(film, text)
                )
            )
            or _explicit_full_film_marker(body)
        )
    )


def _possible_full_film_candidate(film: dict[str, Any], text: str) -> bool:
    body = _normalise(text)
    year = str(film.get("year") or "").strip()
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
    if any(marker in body for marker in exclusion_markers):
        return False
    return bool(
        _strong_film_title_match(film, text)
        and (
            (year and year in body)
            or _explicit_full_film_marker(body)
        )
    )


def _film_titles(film: dict[str, Any]) -> list[str]:
    raw = [film.get("title"), film.get("original_title"), *(film.get("alternative_titles") or [])]
    return _unique_titles(raw)


def _unique_titles(raw: list[Any]) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for value in raw:
        title = str(value or "").strip()
        identity = _normalise(title)
        if title and identity and identity not in seen:
            titles.append(title)
            seen.add(identity)
    return titles


def _strong_film_title_match(film: dict[str, Any], text: str) -> bool:
    body = _normalise(text)
    return any(
        (len(title) >= 4 or (len(title) >= 2 and re.search(r"[\u3400-\u9fff]", title)))
        and title in body
        for title in (_normalise(value) for value in _film_titles(film))
    )


def _bilibili_result_matches_film(film: dict[str, Any], text: str) -> bool:
    """Reject short-title collisions unless the result carries film identity context."""
    if not _strong_film_title_match(film, text):
        return False
    body = _normalise(text)
    year = str(film.get("year") or "").strip()
    directors = film.get("credits", {}).get("directors") or film.get("directors") or []
    director_match = any(
        name and name in body
        for name in (_normalise(str(value)) for value in directors if value)
    )
    film_context = any(
        marker in body
        for marker in (
            "film",
            "cinema",
            "movie",
            "director",
            "interview",
            "review",
            "reaction",
            "analysis",
            "trailer",
            "scene",
            "电影",
            "影片",
            "导演",
            "影评",
            "解说",
            "闲聊",
            "访谈",
            "预告",
            "解析",
            "片段",
            "幕后",
            "完整版",
            "完整无删",
            "正片",
        )
    )
    non_film_collision = any(
        marker in body
        for marker in (
            "bts",
            "防弹少年团",
            "专辑",
            "音源",
            "广播剧",
            "有声小说",
            "有声书",
            "音声",
            "舞蹈",
            "编舞",
        )
    )
    identity_context = bool(director_match or (year and year in body) or film_context)
    return identity_context and not (non_film_collision and not director_match)


def _explicit_full_film_marker(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "full film",
            "full movie",
            "complete film",
            "完整版",
            "完整无删",
            "完整无删减",
            "无删减",
            "未删减",
            "全片",
            "正片",
        )
    )


def _bilibili_page_is_available(value: str, video_id: str) -> bool:
    body = html.unescape(value)
    unavailable_markers = (
        "本视频可能由于以下原因导致无法正常播放",
        "视频链接失效",
        "视频内容不和谐",
        "up主自主删除",
        "侵犯他人著作权",
        "视频不见了哟",
        "稿件不可见",
        "视频已失效",
        "视频已删除",
    )
    lowered = body.casefold()
    if any(marker in lowered for marker in unavailable_markers):
        return False
    error = re.search(r'"error"\s*:\s*\{[^{}]{0,300}"code"\s*:\s*(-?\d+)', body)
    if error and error.group(1) != "0":
        return False
    return video_id in body


def _bilibili_detail_duration(value: str) -> int | None:
    match = re.search(r'"duration"\s*:\s*(\d+)', value)
    return int(match.group(1)) if match else None
