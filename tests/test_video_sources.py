import json
import os
import tempfile
from pathlib import Path

from app.backend.settings import LocalSettingsStore
from app.backend.video_sources import (
    BilibiliPublicVideoAdapter,
    FilmVideoService,
    YouTubeVideoAdapter,
)


FILM = {
    "title": "Memoria",
    "original_title": "記憶",
    "year": 2021,
    "credits": {"directors": ["Apichatpong Weerasethakul"]},
}


def test_youtube_search_keeps_only_relevant_safe_video_ids() -> None:
    previous = os.environ.pop("YOUTUBE_API_KEY", None)
    try:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalSettingsStore(Path(directory) / "settings.json")
            store.set("youtube_api_key", "local-test-key")

            def transport(url: str) -> dict:
                assert "videoEmbeddable=true" in url
                assert "key=local-test-key" in url
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
                    ]
                }

            videos = YouTubeVideoAdapter(store, transport=transport).search(FILM)

            assert len(videos) == 1
            assert videos[0].platform == "YouTube"
            assert videos[0].relevance == "title_and_director"
            assert videos[0].embed_url == "https://www.youtube-nocookie.com/embed/abcdefghijk"
    finally:
        if previous is not None:
            os.environ["YOUTUBE_API_KEY"] = previous


def test_bilibili_parses_server_rendered_public_results() -> None:
    title = json.dumps("《Memoria 记忆》(2021) 阿彼察邦映后谈", ensure_ascii=True)[1:-1]
    description = json.dumps("导演讨论声音与记忆。", ensure_ascii=True)[1:-1]
    picture = json.dumps("//i0.hdslb.com/bfs/archive/example.jpg")[1:-1]
    body = (
        '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav123",'
        f'"BV1Ab411c7De","{title}","{description}","{picture}"'
    )

    videos = BilibiliPublicVideoAdapter(transport=lambda _: body).search(FILM)

    assert len(videos) == 1
    assert videos[0].platform == "Bilibili"
    assert videos[0].video_id == "BV1Ab411c7De"
    assert videos[0].url == "https://www.bilibili.com/video/BV1Ab411c7De/"
    assert videos[0].embed_url.startswith("https://player.bilibili.com/player.html?")


def test_video_service_survives_one_provider_failure() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = LocalSettingsStore(Path(directory) / "settings.json")
        youtube = YouTubeVideoAdapter(store)
        title = json.dumps("Memoria (2021) by Apichatpong Weerasethakul", ensure_ascii=True)[1:-1]
        body = (
            '"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav42",'
            f'"BV1Ab411c7De","{title}","Film essay",""'
        )
        bilibili = BilibiliPublicVideoAdapter(transport=lambda _: body)

        bundle = FilmVideoService(youtube, bilibili).search("wikidata:Q67087116", FILM)

        assert bundle.providers == ["Bilibili"]
        assert len(bundle.videos) == 1
