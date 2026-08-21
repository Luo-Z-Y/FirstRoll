import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.backend.settings import LocalSettingsStore
from app.backend.video_sources import (
    BilibiliPublicVideoAdapter,
    FilmVideo,
    FilmVideoBundle,
    FilmVideoService,
    FilmVideoStore,
    PublicVideoTextExtractor,
    YouTubeVideoAdapter,
    _bilibili_video_queries,
    _video_category,
)


FILM = {
    "title": "Memoria",
    "original_title": "記憶",
    "alternative_titles": ["记忆"],
    "year": 2021,
    "credits": {"directors": ["Apichatpong Weerasethakul"]},
}

CHECKED_AT = datetime.now(timezone.utc).isoformat()


def test_youtube_search_keeps_only_relevant_safe_video_ids() -> None:
    previous = os.environ.pop("YOUTUBE_API_KEY", None)
    try:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalSettingsStore(Path(directory) / "settings.json")
            store.set("youtube_api_key", "local-test-key")

            def transport(url: str) -> dict:
                assert "key=local-test-key" in url
                if "/videos?" in url:
                    return {
                        "items": [
                            {
                                "id": "abcdefghijk",
                                "contentDetails": {"duration": "PT48M12S"},
                                "status": {
                                    "uploadStatus": "processed",
                                    "privacyStatus": "public",
                                    "embeddable": True,
                                },
                            }
                        ]
                    }
                assert "videoEmbeddable=true" in url
                return {
                    "items": [
                        {
                            "id": {"videoId": "abcdefghijk"},
                            "snippet": {
                                "title": "Memoria — interview with Apichatpong Weerasethakul",
                                "description": "The director discusses the 2021 film.",
                                "channelTitle": "Cinema Archive",
                                "publishedAt": "2022-01-02T00:00:00Z",
                                "thumbnails": {
                                    "high": {"url": "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg"}
                                },
                            },
                        },
                        {
                            "id": {"videoId": "invalid"},
                            "snippet": {"title": "Memoria", "description": ""},
                        },
                        {
                            "id": {"videoId": "zyxwvutsrqp"},
                            "snippet": {"title": "Unrelated cooking lesson", "description": ""},
                        },
                        {
                            "id": {"videoId": "lmnopqrstuv"},
                            "snippet": {
                                "title": "Memoria 2021 official trailer",
                                "description": "Film trailer",
                            },
                        },
                    ]
                }

            videos = YouTubeVideoAdapter(store, transport=transport).search(FILM)

            assert len(videos) == 1
            assert videos[0].platform == "YouTube"
            assert videos[0].relevance == "title_and_director"
            assert videos[0].duration_seconds == 2892
            assert videos[0].category == "interview"
            assert videos[0].embed_url == "https://www.youtube-nocookie.com/embed/abcdefghijk"
            assert videos[0].availability_checked_at
    finally:
        if previous is not None:
            os.environ["YOUTUBE_API_KEY"] = previous


def test_youtube_search_can_use_a_request_scoped_key_without_storing_it() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        requested = []

        def transport(url: str) -> dict:
            requested.append(url)
            return {"items": []}

        adapter = YouTubeVideoAdapter(store, transport=transport)
        adapter.search(FILM, api_key="personal-youtube-key-12345")

        assert requested
        assert all("key=personal-youtube-key-12345" in url for url in requested)
        assert store.secret_state("youtube").configured is False


def test_bilibili_parses_server_rendered_public_results() -> None:
    title = json.dumps("《Memoria 记忆》(2021) 阿彼察邦映后谈", ensure_ascii=True)[1:-1]
    description = json.dumps("导演讨论声音与记忆。", ensure_ascii=True)[1:-1]
    picture = json.dumps("//i0.hdslb.com/bfs/archive/example.jpg")[1:-1]
    body = (
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav123",'
        f'"BV1Ab411c7De","{title}","{description}","{picture}",42,'
        '"电影,阿彼察邦,访谈","1:02:03"'
    )

    videos = BilibiliPublicVideoAdapter(transport=lambda _: body).search(FILM)

    assert len(videos) == 1
    assert videos[0].platform == "Bilibili"
    assert videos[0].video_id == "BV1Ab411c7De"
    assert videos[0].url == "https://www.bilibili.com/video/BV1Ab411c7De/"
    assert videos[0].embed_url.startswith("https://player.bilibili.com/player.html?")
    assert videos[0].duration_seconds == 3723
    assert videos[0].category == "interview"


def test_bilibili_rejects_a_search_result_whose_video_page_is_unavailable() -> None:
    title = json.dumps("《Memoria 记忆》(2021) 预告", ensure_ascii=True)[1:-1]
    body = (
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav123",'
        f'"BV1Ab411c7De","{title}","电影预告","",42,"电影","2:10"'
    )
    detail_urls: list[str] = []

    def detail_transport(url: str) -> str:
        detail_urls.append(url)
        return "非常抱歉，本视频可能由于以下原因导致无法正常播放：视频链接失效"

    videos = BilibiliPublicVideoAdapter(
        transport=lambda _: body,
        detail_transport=detail_transport,
    ).search(FILM)

    assert videos == []
    assert detail_urls == ["https://www.bilibili.com/video/BV1Ab411c7De/"]


def test_video_service_survives_one_provider_failure() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        youtube = YouTubeVideoAdapter(store)
        title = json.dumps("Memoria (2021) by Apichatpong Weerasethakul", ensure_ascii=True)[1:-1]
        body = (
            '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav42",'
            f'"BV1Ab411c7De","{title}","Film essay","",42,"电影","12:00"'
        )
        bilibili = BilibiliPublicVideoAdapter(transport=lambda _: body)

        video_store = FilmVideoStore(Path(directory) / "videos")
        bundle = FilmVideoService(youtube, bilibili, video_store).search(
            "wikidata:Q67087116", FILM
        )

        assert bundle.providers == ["Bilibili"]
        assert len(bundle.videos) == 1


def test_public_youtube_captions_are_extracted_and_normalised() -> None:
    page = (
        '<script>{"captions":{"playerCaptionsTracklistRenderer":'
        '{"captionTracks":[{"baseUrl":"https://www.youtube.com/api/timedtext?v=abcdefghijk&lang=en",'
        '"languageCode":"en","name":{"simpleText":"English"}}]}}}</script>'
    )
    caption_payload = {
        "events": [
            {"segs": [{"utf8": "The director discusses "}, {"utf8": "rehearsal."}]},
            {"segs": [{"utf8": "The director discusses rehearsal."}]},
            {"segs": [{"utf8": "Blocking changed during production."}]},
        ]
    }
    requested: list[str] = []
    pages: list[str] = []

    def captions(url: str) -> dict[str, Any]:
        requested.append(url)
        return caption_payload

    extractor = PublicVideoTextExtractor(
        page_transport=lambda url: pages.append(url) or page,
        caption_transport=captions,
    )
    video = FilmVideo(
        platform="YouTube",
        video_id="abcdefghijk",
        title="Example director interview",
        url="https://www.youtube.com/watch?v=abcdefghijk",
        embed_url="https://www.youtube-nocookie.com/embed/abcdefghijk",
        category="interview",
        relevance="title_and_director",
    )

    enriched = extractor.enrich([video])

    assert len(enriched[0].text_tracks) == 1
    assert enriched[0].text_tracks[0].kind == "captions"
    assert enriched[0].text_tracks[0].text == (
        "The director discusses rehearsal.\nBlocking changed during production."
    )
    assert "fmt=json3" in requested[0]
    assert "timedtext" not in enriched[0].text_tracks[0].source_url
    assert enriched[0].text_checked_at
    assert extractor.enrich(enriched) == enriched
    assert len(pages) == 1


def test_duration_classifies_a_minimally_labelled_complete_film() -> None:
    title = json.dumps("记忆（2021）", ensure_ascii=True)[1:-1]
    description = json.dumps("阿彼察邦·韦拉斯哈古", ensure_ascii=True)[1:-1]
    body = (
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav99",'
        f'"BV1Ab411c7Df","{title}","{description}","",99,'
        '"电影,阿彼察邦","2:16:00"'
    )

    videos = BilibiliPublicVideoAdapter(transport=lambda _: body).search(FILM)

    assert len(videos) == 1
    assert videos[0].duration_seconds == 8160
    assert videos[0].category == "full_film"


def test_missing_search_duration_uses_bounded_public_detail_metadata() -> None:
    title = json.dumps("记忆（2021）", ensure_ascii=True)[1:-1]
    body = (
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav99",'
        f'"BV1Ab411c7Df","{title}","",""'
    )
    detail_urls: list[str] = []

    def detail_transport(url: str) -> str:
        detail_urls.append(url)
        return '<script>window.__INITIAL_STATE__={"bvid":"BV1Ab411c7Df","duration":8160}</script>'

    videos = BilibiliPublicVideoAdapter(
        transport=lambda _: body,
        detail_transport=detail_transport,
    ).search(FILM)

    assert detail_urls == ["https://www.bilibili.com/video/BV1Ab411c7Df/"]
    assert len(videos) == 1
    assert videos[0].duration_seconds == 8160
    assert videos[0].category == "full_film"


def test_exact_localised_title_finds_full_film_despite_distribution_year_label() -> None:
    film = {
        "title": "The World of Love",
        "original_title": "若問世界誰無傷",
        "alternative_titles": ["世界的主人", "세계의 주인"],
        "year": 2025,
        "credits": {"directors": ["Yoon Ga-eun"]},
    }
    result_title = json.dumps(
        "2026韩国青春电影【世界的主人】蓝光中字（完整无删）",
        ensure_ascii=True,
    )[1:-1]
    body = (
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav99",'
        f'"BV1iHZcBgEzm","{result_title}","蓝光中字",""'
    )
    queries: list[str] = []
    details: list[str] = []

    def search_transport(url: str) -> str:
        queries.append(url)
        return body if "%E4%B8%96%E7%95%8C%E7%9A%84%E4%B8%BB%E4%BA%BA" in url else ""

    def detail_transport(url: str) -> str:
        details.append(url)
        return '<title>世界的主人</title><script>{"bvid":"BV1iHZcBgEzm","duration":10294}</script>'

    videos = BilibiliPublicVideoAdapter(
        transport=search_transport,
        detail_transport=detail_transport,
    ).search(film)

    assert _bilibili_video_queries(film)[0] == "世界的主人"
    assert details == ["https://www.bilibili.com/video/BV1iHZcBgEzm/"]
    assert len(videos) == 1
    assert videos[0].video_id == "BV1iHZcBgEzm"
    assert videos[0].duration_seconds == 10294
    assert videos[0].category == "full_film"


def test_content_markers_override_long_duration() -> None:
    assert _video_category("Memoria 记者会", "Cannes 2021", 3600) == "interview"
    assert _video_category("2021年度十大佳片盘点", "电影最TOP", 3600) == "video_essay"
    assert _video_category("戛纳电影节颁奖典礼", "全记录", 7200) == "other"
    assert _video_category("【闲聊Reaction】世界的主人", "", 7171) == "video_essay"


def test_unrelated_long_result_cannot_pass_on_year_and_generic_context() -> None:
    film = {
        "title": "The World of Love",
        "alternative_titles": ["世界的主人", "세계의 주인"],
        "year": 2025,
        "credits": {"directors": ["Yoon Ga-eun"]},
    }
    title = json.dumps("EBiDAN THE LIVE 2025【Day1-Day3】", ensure_ascii=True)[1:-1]
    description = json.dumps("EBiDAN THE LIVE 2025 HOTEL NINE STAR", ensure_ascii=True)[1:-1]
    body = (
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav77",'
        f'"BV1j2YizYEFU","{title}","{description}","",77,'
        '"电影","19:15:22"'
    )

    assert BilibiliPublicVideoAdapter(transport=lambda _: body).search(film) == []


def test_short_localised_title_rejects_music_and_audio_collisions() -> None:
    film = {
        "title": "In the Mood for Love",
        "original_title": "花樣年華",
        "alternative_titles": ["花样年华"],
        "year": 2000,
        "credits": {"directors": ["Wong Kar-wai"]},
    }
    music_title = json.dumps("BTS防弹少年团《花樣年華 pt.1》全专音源", ensure_ascii=True)[1:-1]
    audio_title = json.dumps("粤语广播剧《花樣年華》多人有声小说", ensure_ascii=True)[1:-1]
    body = (
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav10",'
        f'"BV1Ab411c7Dg","{music_title}","专辑歌曲","",10,"音乐","1:05:00"'
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav11",'
        f'"BV1Ab411c7Dh","{audio_title}","广播剧","",11,"有声书","1:20:00"'
    )

    assert BilibiliPublicVideoAdapter(transport=lambda _: body).search(film) == []


def _fixture_video(video_id: str, title: str) -> FilmVideo:
    return FilmVideo(
        platform="YouTube",
        video_id=video_id,
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        embed_url=f"https://www.youtube-nocookie.com/embed/{video_id}",
        category="video_essay",
        relevance="title",
        availability_checked_at=CHECKED_AT,
    )


def test_refresh_merges_new_results_into_private_catalogue() -> None:
    class SequencedAdapter:
        def __init__(self, batches: list[list[FilmVideo]]) -> None:
            self.batches = batches
            self.calls = 0

        def search(self, film: dict, limit: int = 12) -> list[FilmVideo]:
            batch = self.batches[min(self.calls, len(self.batches) - 1)]
            self.calls += 1
            return batch[:limit]

        def status(self) -> dict:
            return {"state": "ready"}

    first = _fixture_video("abcdefghijk", "Memoria film essay")
    second = _fixture_video("zyxwvutsrqp", "Memoria sound analysis")
    youtube = SequencedAdapter([[first], [second]])
    bilibili = SequencedAdapter([[], []])

    with tempfile.TemporaryDirectory() as directory:
        store = FilmVideoStore(Path(directory) / "videos")
        service = FilmVideoService(youtube, bilibili, store)  # type: ignore[arg-type]

        initial = service.search("wikidata:Q67087116", FILM)
        expanded = service.search("wikidata:Q67087116", FILM)
        cached = store.load("wikidata:Q67087116")

        assert [video.video_id for video in initial.videos] == ["abcdefghijk"]
        assert [video.video_id for video in expanded.videos] == [
            "abcdefghijk",
            "zyxwvutsrqp",
        ]
        assert cached == expanded
        assert "1 added by this search" in expanded.notice


def test_refresh_deduplicates_existing_platform_video_id() -> None:
    video = _fixture_video("abcdefghijk", "Memoria film essay")

    class FixedAdapter:
        def search(self, film: dict, limit: int = 12) -> list[FilmVideo]:
            return [video]

        def status(self) -> dict:
            return {"state": "ready"}

    with tempfile.TemporaryDirectory() as directory:
        store = FilmVideoStore(Path(directory) / "videos")
        adapter = FixedAdapter()
        service = FilmVideoService(adapter, adapter, store)  # type: ignore[arg-type]

        service.search("wikidata:Q67087116", FILM)
        refreshed = service.search("wikidata:Q67087116", FILM)

        assert len(refreshed.videos) == 1
        assert "0 added by this search" in refreshed.notice


def test_cached_video_is_hidden_after_availability_check_expires() -> None:
    stale = _fixture_video("abcdefghijk", "Memoria film essay").model_copy(
        update={
            "availability_checked_at": (
                datetime.now(timezone.utc) - timedelta(hours=7)
            ).isoformat()
        }
    )

    class EmptyAdapter:
        def status(self) -> dict:
            return {"state": "ready"}

    with tempfile.TemporaryDirectory() as directory:
        store = FilmVideoStore(Path(directory) / "videos")
        store.save(
            FilmVideoBundle(
                film_id="wikidata:Q67087116",
                query="Memoria",
                fetched_at=CHECKED_AT,
                videos=[stale],
                providers=["YouTube"],
                notice="fixture",
            )
        )
        service = FilmVideoService(EmptyAdapter(), EmptyAdapter(), store)  # type: ignore[arg-type]

        assert service.cached_for_display("wikidata:Q67087116") is None


def test_refresh_revalidates_persisted_bilibili_full_film_cards() -> None:
    class EmptyAdapter:
        def search(self, film: dict, limit: int = 12) -> list[FilmVideo]:
            return []

        def status(self) -> dict:
            return {"state": "ready"}

    film = {
        "title": "The World of Love",
        "alternative_titles": ["世界的主人"],
        "year": 2025,
    }
    unrelated = FilmVideo(
        platform="Bilibili",
        video_id="BV1j2YizYEFU",
        title="EBiDAN THE LIVE 2025【Day1-Day3】",
        description="EBiDAN HOTEL NINE STAR",
        url="https://www.bilibili.com/video/BV1j2YizYEFU/",
        embed_url="https://player.bilibili.com/player.html?bvid=BV1j2YizYEFU&autoplay=0",
        duration_seconds=69322,
        category="full_film",
        relevance="title",
        availability_checked_at=CHECKED_AT,
    )
    reaction = FilmVideo(
        platform="Bilibili",
        video_id="BV1UTodB5EVY",
        title="【闲聊Reaction】世界的主人",
        url="https://www.bilibili.com/video/BV1UTodB5EVY/",
        embed_url="https://player.bilibili.com/player.html?bvid=BV1UTodB5EVY&autoplay=0",
        duration_seconds=7171,
        category="full_film",
        relevance="title",
        availability_checked_at=CHECKED_AT,
    )

    with tempfile.TemporaryDirectory() as directory:
        store = FilmVideoStore(Path(directory) / "videos")
        store.save(
            FilmVideoBundle(
                film_id="wikidata:Q135488622",
                query="The World of Love",
                fetched_at="2026-08-13T00:00:00+00:00",
                videos=[unrelated, reaction],
                providers=["Bilibili"],
                notice="fixture",
            )
        )
        adapter = EmptyAdapter()
        refreshed = FilmVideoService(adapter, adapter, store).search(
            "wikidata:Q135488622", film
        )  # type: ignore[arg-type]

    assert [video.video_id for video in refreshed.videos] == ["BV1UTodB5EVY"]
    assert refreshed.videos[0].category == "video_essay"
