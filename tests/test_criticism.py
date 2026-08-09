import json
import stat
import tempfile
from pathlib import Path
from typing import Any

from app.backend.criticism import (
    CriticalClaim,
    CriticismStore,
    DoubanMcpAdapter,
    LetterboxdApiAdapter,
    ReviewSource,
    build_bundle,
)
from app.backend.settings import LocalSettingsStore
from app.backend.study_service import DeepSeekStudyService


def test_douban_markdown_is_normalised_with_stable_review_urls() -> None:
    table = """| title | rating | summary | id |
| --- | --- | --- | --- |
| 空间与记忆 | 5 (有用：42人) | 医院空间像记忆一样重复。 | 12345 |
"""

    rows = DoubanMcpAdapter._markdown_table(table)

    assert rows == [
        {
            "title": "空间与记忆",
            "rating": "5 (有用：42人)",
            "summary": "医院空间像记忆一样重复。",
            "id": "12345",
        }
    ]
    assert DoubanMcpAdapter._language(rows[0]["summary"]) == "zh"


def test_douban_multiline_review_rows_are_reconstructed() -> None:
    table = """| title | rating | summary | id |
| ----- | ------ | ------- | --- |
| 我的一脸懵逼观影感受 | 4 (有用：4381人) | 第一段提到《路边野餐》。
* 2015洛迦诺国际电影节：最佳新导演
第二段包含未转义的形式术语 | 长镜头 | 和声音。 | 7507249 |
| 关于毕赣和《路边野餐》 | 4 (有用：71人) | 毕赣，1989年生，贵州凯里人。
影片最知名的是长达42分钟的长镜头。 | 7917771 |
"""

    rows = DoubanMcpAdapter._markdown_table(table)

    assert len(rows) == 2
    assert rows[0]["id"] == "7507249"
    assert "2015洛迦诺国际电影节" in rows[0]["summary"]
    assert "形式术语 | 长镜头 | 和声音" in rows[0]["summary"]
    assert rows[1]["id"] == "7917771"
    assert "42分钟的长镜头" in rows[1]["summary"]


def test_douban_match_requires_title_and_prefers_year() -> None:
    film = {"title": "Example Film", "original_title": "示例电影", "year": 2024}
    candidates = [
        {"id": "1", "title": "Example Film", "publish_date": "1990", "subtitle": ""},
        {"id": "2", "title": "Example Film", "publish_date": "2024", "subtitle": ""},
    ]

    assert DoubanMcpAdapter._choose_match(film, candidates)["id"] == "2"


def test_letterboxd_official_api_reviews_are_normalised() -> None:
    calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def transport(
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> dict[str, Any]:
        calls.append((method, url, headers, body))
        if url.endswith("/auth/token"):
            return {"access_token": "official-token", "expires_in": 3600}
        if "/search?" in url:
            return {
                "items": [
                    {
                        "type": "FilmSearchItem",
                        "score": 1,
                        "film": {
                            "id": "abc123",
                            "name": "Kaili Blues",
                            "releaseYear": 2015,
                            "link": "https://letterboxd.com/film/kaili-blues/",
                        },
                    }
                ]
            }
        return {
            "items": [
                {
                    "id": "review42",
                    "name": "A cinema of memory",
                    "owner": {"username": "critic", "displayName": "Film Critic"},
                    "rating": 4.5,
                    "review": {
                        "text": "The long take <em>folds</em> space.<br>It resists certainty.",
                        "languageCode": "en",
                        "moderated": False,
                    },
                }
            ]
        }

    with tempfile.TemporaryDirectory() as directory:
        settings = LocalSettingsStore(Path(directory) / "settings.json")
        settings.set("letterboxd_client_id", "client-id")
        settings.set("letterboxd_client_secret", "client-secret")
        adapter = LetterboxdApiAdapter(settings, transport=transport)

        provider_id, provider_title, reviews = adapter.fetch_reviews(
            {"title": "Kaili Blues", "original_title": "路边野餐", "year": 2015}
        )

    assert provider_id == "abc123"
    assert provider_title == "Kaili Blues"
    assert reviews[0].provider == "Letterboxd"
    assert reviews[0].author == "Film Critic"
    assert reviews[0].summary == "The long take folds space. It resists certainty."
    assert reviews[0].url == "https://letterboxd.com/critic/film/kaili-blues/"
    assert calls[0][0] == "POST"
    assert calls[1][2]["Authorization"] == "Bearer official-token"
    assert "where=HasReview" in calls[2][1]


def test_douban_diagnostic_distinguishes_empty_review_table() -> None:
    response = """| title | rating | summary | id |
| --- | --- | --- | --- |
"""

    message = DoubanMcpAdapter._review_response_error(
        response,
        DoubanMcpAdapter._markdown_table(response),
        cookie_configured=False,
    )

    assert "valid response" in message
    assert "no long-form review summaries" in message


def test_douban_diagnostic_explains_authentication_action() -> None:
    message = DoubanMcpAdapter._review_response_error(
        "访问受限，请先登录或完成验证码。",
        [],
        cookie_configured=False,
    )

    assert "requires authentication" in message
    assert "Add your personal Douban cookie" in message


def test_douban_diagnostic_reports_schema_drift() -> None:
    rows = [{"review_id": "42", "abstract": "A useful argument."}]

    message = DoubanMcpAdapter._review_response_error(
        "table omitted from fixture",
        rows,
        cookie_configured=True,
    )

    assert "unsupported format" in message
    assert "missing columns: id, summary" in message
    assert "abstract, review_id" in message


def test_douban_diagnostic_preview_is_short_and_redacted() -> None:
    message = DoubanMcpAdapter._review_response_error(
        "Unexpected payload cookie=secret-value https://example.com/private " + "x" * 240,
        [],
        cookie_configured=True,
    )

    assert "secret-value" not in message
    assert "https://example.com" not in message
    assert "[redacted]" in message
    assert "Provider response preview" in message


def test_structured_criticism_preserves_null_missing_fields() -> None:
    review = ReviewSource(
        source_id="R1",
        provider="Douban",
        review_id="12345",
        title="空间与记忆",
        summary="医院空间像记忆一样重复。",
        url="https://movie.douban.com/review/12345/",
        language="zh",
    )
    response = {
        "claims": [
            {
                "claim_id": "C1",
                "source_id": "R1",
                "critic_claim": "The reviewer argues that the hospital space repeats like memory.",
                "scene_or_sequence": None,
                "described_observation": None,
                "techniques": [],
                "interpretation": "Spatial repetition is associated with memory.",
                "alternative_reading": None,
                "lens_tags": ["mise_en_scene"],
                "short_source_excerpt": "医院空间像记忆一样重复。",
                "evidence_status": "critic_reported",
                "extraction_confidence": "high",
                "missing_fields": [
                    "scene_or_sequence",
                    "described_observation",
                    "techniques",
                ],
            }
        ]
    }
    captured: dict[str, Any] = {}

    def transport(_: str, payload: dict[str, Any] | None, __: str) -> dict[str, Any]:
        captured["payload"] = payload
        return {"choices": [{"message": {"content": json.dumps(response)}}]}

    with tempfile.TemporaryDirectory() as directory:
        settings = LocalSettingsStore(Path(directory) / "settings.json")
        settings.set("deepseek_api_key", "test-key")
        claims = DeepSeekStudyService(settings, transport=transport).structure_reviews(
            {"title": "Example Film", "year": 2024}, [review]
        )

    assert claims[0].scene_or_sequence is None
    assert claims[0].described_observation is None
    assert claims[0].evidence_status == "critic_reported"
    assert "Do not add facts from memory" in captured["payload"]["messages"][0]["content"]


def test_criticism_cache_remains_private_and_round_trips() -> None:
    claim = CriticalClaim(
        claim_id="C1",
        source_id="R1",
        critic_claim="The reviewer links repeated institutional space with unstable memory.",
        lens_tags=["mise_en_scene"],
        extraction_confidence="medium",
        missing_fields=["scene_or_sequence"],
    )
    review = ReviewSource(
        source_id="R1",
        provider="Douban",
        review_id="12345",
        title="空间与记忆",
        summary="医院空间像记忆一样重复。",
        url="https://movie.douban.com/review/12345/",
        language="zh",
    )
    bundle = build_bundle("wikidata:Q1", "678", "Example Film", [review], [claim])

    with tempfile.TemporaryDirectory() as directory:
        store = CriticismStore(Path(directory) / "criticism")
        store.save(bundle)
        path = next((Path(directory) / "criticism").iterdir())
        loaded = store.load("wikidata:Q1")

        assert loaded is not None
        assert loaded.claims[0].evidence_status == "critic_reported"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
