import json
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

from app.backend.criticism import (
    CriticalClaim,
    CriticismError,
    CriticismStore,
    CrossrefResearchAdapter,
    DoubanMcpAdapter,
    GuardianPublicWebAdapter,
    LetterboxdApiAdapter,
    LetterboxdPublicWebAdapter,
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


def test_douban_platform_rating_is_normalised_to_ten() -> None:
    assert DoubanMcpAdapter._parse_platform_rating("8.7 (24567人)") == (8.7, 24567)
    assert DoubanMcpAdapter._parse_platform_rating("0 (0人)") == (None, None)


def test_letterboxd_aggregate_rating_is_read_from_public_json_ld() -> None:
    body = """
    <script type="application/ld+json">
      {"@type":"Movie","aggregateRating":{"ratingValue":4.2,"ratingCount":"12,345"}}
    </script>
    """

    assert LetterboxdPublicWebAdapter._aggregate_rating(body) == (4.2, 12345)


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


def test_douban_match_does_not_choose_near_title_from_wrong_year() -> None:
    film = {
        "title": "In the Mood for Love",
        "original_title": "花樣年華",
        "year": 2000,
    }
    candidates = [
        {
            "id": "1291557",
            "title": "花样年华",
            "publish_date": "2000",
            "subtitle": "中国香港 / 剧情 爱情 / 王家卫",
        },
        {
            "id": "35211201",
            "title": "I'm in the Mood for Love",
            "publish_date": "2010",
            "subtitle": "加拿大 / 剧情 短片",
        },
    ]

    assert DoubanMcpAdapter._choose_match(film, candidates)["id"] == "1291557"


def test_douban_match_accepts_one_exact_year_result_with_translated_title() -> None:
    film = {"title": "Memoria", "original_title": "記憶", "year": 2021}
    candidates = [
        {
            "id": "30137576",
            "title": "记忆",
            "publish_date": "2021",
            "subtitle": "哥伦比亚 / 阿彼察邦·韦拉斯哈古",
        }
    ]

    assert DoubanMcpAdapter._choose_match(film, candidates)["id"] == "30137576"


def test_douban_match_rejects_ambiguous_translated_same_year_results() -> None:
    film = {"title": "Memoria", "original_title": "記憶", "year": 2021}
    candidates = [
        {"id": "1", "title": "记忆", "publish_date": "2021", "subtitle": ""},
        {"id": "2", "title": "记录记忆", "publish_date": "2021", "subtitle": ""},
    ]

    try:
        DoubanMcpAdapter._choose_match(film, candidates)
    except CriticismError as exc:
        assert "confident film identity match" in str(exc)
    else:
        raise AssertionError("Ambiguous translated results should not be accepted")


def test_douban_unwraps_useful_error_from_task_group() -> None:
    root = CriticismError("Douban did not return a confident film identity match.")
    wrapped = ExceptionGroup("unhandled errors in a TaskGroup", [ExceptionGroup("nested", [root])])

    assert DoubanMcpAdapter._nested_criticism_error(wrapped) is root
    assert DoubanMcpAdapter._mcp_exception_detail(wrapped) == str(root)


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


def test_letterboxd_public_web_resolves_title_and_imports_attributed_reviews() -> None:
    film_page = '''<meta property="og:title" content="Syndromes and a Century (2006) directed by Apichatpong Weerasethakul">
    <a href="/critic/film/syndromes-and-a-century/">Review</a>'''
    review_page = '''<script type="application/ld+json">/* <![CDATA[ */
    {"@type":"Review","author":[{"@type":"Person","name":"Film Critic"}],
    "reviewBody":"The hospital repeats as a transformed memory, with sound carrying relations across spaces.",
    "itemReviewed":{"@type":"Movie","name":"Syndromes and a Century"},
    "reviewRating":{"ratingValue":4,"bestRating":5}}
    /* ]]> */</script>'''
    pages = {
        "https://letterboxd.com/film/syndromes-and-a-century/": film_page,
        "https://letterboxd.com/critic/film/syndromes-and-a-century/": review_page,
    }

    def transport(url: str) -> tuple[str, str]:
        if url not in pages:
            raise CriticismError("not found")
        return url, pages[url]

    adapter = LetterboxdPublicWebAdapter(transport=transport)
    provider_id, provider_title, reviews = adapter.fetch_reviews(
        {"title": "Syndromes and a Century", "year": 2006}
    )

    assert provider_id == "syndromes-and-a-century"
    assert provider_title == "Syndromes and a Century"
    assert reviews[0].author == "Film Critic"
    assert reviews[0].rating_label == "4/5"
    assert reviews[0].provider == "Letterboxd public web"
    assert reviews[0].url == "https://letterboxd.com/critic/film/syndromes-and-a-century/"


def test_letterboxd_public_web_prefers_verified_imdb_identity_for_same_title() -> None:
    imdb_url = "https://letterboxd.com/imdb/tt32186579/"
    film_url = "https://letterboxd.com/film/an-unfinished-film-2024/"
    review_url = "https://letterboxd.com/critic/film/an-unfinished-film-2024/"
    film_page = '''<meta property="og:title" content="An Unfinished Film (2024)">
    <a href="/critic/film/an-unfinished-film-2024/">Review</a>
    <script type="application/ld+json">{"@type":"Movie","name":"An Unfinished Film",
    "director":[{"@type":"Person","name":"Lou Ye"}]}</script>'''
    review_page = '''<script type="application/ld+json">
    {"@type":"Review","author":{"@type":"Person","name":"Film Critic"},
    "reviewBody":"Lou Ye combines production footage and phone screens to preserve a contested collective memory.",
    "itemReviewed":{"@type":"Movie","name":"An Unfinished Film"}}
    </script>'''
    calls: list[str] = []

    def transport(url: str) -> tuple[str, str]:
        calls.append(url)
        if url == imdb_url:
            return film_url, film_page
        if url == review_url:
            return review_url, review_page
        raise CriticismError("not found")

    adapter = LetterboxdPublicWebAdapter(transport=transport)
    provider_id, _, reviews = adapter.fetch_reviews(
        {
            "title": "An Unfinished Film",
            "year": 2024,
            "credits": {"directors": ["Lou Ye"]},
            "external_ids": {"imdb": "tt32186579"},
        }
    )

    assert calls[0] == imdb_url
    assert provider_id == "an-unfinished-film-2024"
    assert reviews[0].author == "Film Critic"
    assert reviews[0].url == review_url


def test_letterboxd_public_web_rejects_same_title_wrong_director() -> None:
    wrong_page = '''<meta property="og:title" content="An Unfinished Film (2024)">
    <script type="application/ld+json">{"@type":"Movie","name":"An Unfinished Film",
    "director":[{"@type":"Person","name":"Another Director"}]}</script>'''

    assert not LetterboxdPublicWebAdapter._film_page_matches(
        wrong_page,
        "An Unfinished Film",
        "2024",
        ["Lou Ye"],
    )


def test_letterboxd_public_web_rejects_non_letterboxd_urls() -> None:
    try:
        LetterboxdPublicWebAdapter._validate_letterboxd_url("https://example.com/review")
    except CriticismError as exc:
        assert "letterboxd.com" in str(exc)
    else:
        raise AssertionError("A non-Letterboxd URL should be rejected")


def test_guardian_public_web_imports_attributed_article_body() -> None:
    search = {
        "response": {
            "results": [
                {
                    "id": "film/2007/sep/21/example",
                    "sectionId": "film",
                    "webTitle": "Syndromes and a Century",
                    "webUrl": "https://www.theguardian.com/film/2007/sep/21/example",
                }
            ]
        }
    }
    article = '''<script type="application/ld+json">
    [{"@type":"NewsArticle","headline":"Syndromes and a Century",
    "author":[{"@type":"Person","name":"Peter Bradshaw"}]}]
    </script><main><div data-gu-name="body"><div><p>The repeated hospital spaces turn memory into architectural rhythm.</p>
    <p>Sound and duration allow apparently ordinary gestures to acquire a mysterious charge.</p></div></div></main>'''

    search_urls: list[str] = []

    def search_transport(url: str) -> dict[str, Any]:
        search_urls.append(url)
        return search

    adapter = GuardianPublicWebAdapter(
        search_transport=search_transport,
        html_transport=lambda url: (url, article),
    )
    provider_id, title, reviews = adapter.fetch_reviews(
        {"title": "Syndromes and a Century", "year": 2006}
    )

    assert provider_id == "film/2007/sep/21/example"
    assert title == "Syndromes and a Century"
    assert reviews[0].author == "Peter Bradshaw"
    assert reviews[0].provider == "The Guardian public web"
    assert "architectural rhythm" in reviews[0].summary
    assert "mysterious charge" in reviews[0].summary
    assert "query-fields=headline" in search_urls[0]
    assert "tag=tone/reviews" not in search_urls[0]


def test_guardian_public_web_rejects_redirects_outside_guardian() -> None:
    try:
        GuardianPublicWebAdapter._validate_article_url("https://example.com/film/review")
    except CriticismError as exc:
        assert "theguardian.com" in str(exc)
    else:
        raise AssertionError("A non-Guardian URL should be rejected")


def test_douban_diagnostic_distinguishes_empty_review_table() -> None:
    response = """| title | rating | summary | id |
| --- | --- | --- | --- |
"""

    message = DoubanMcpAdapter._review_response_error(
        response,
        DoubanMcpAdapter._markdown_table(response),
        cookie_configured=False,
    )

    assert "empty review table" in message
    assert "does not establish that the film has no long-form reviews" in message


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


def test_structured_criticism_repairs_invalid_json_once() -> None:
    review = ReviewSource(
        source_id="R1",
        provider="Douban",
        review_id="12345",
        title="空间与记忆",
        summary="医院空间像记忆一样重复。",
        url="https://movie.douban.com/review/12345/",
        language="zh",
    )
    valid = {
        "claims": [
            {
                "claim_id": "C1",
                "source_id": "R1",
                "critic_claim": "The reviewer relates repeated hospital space to unstable memory.",
                "scene_or_sequence": None,
                "described_observation": None,
                "techniques": [],
                "interpretation": None,
                "alternative_reading": None,
                "lens_tags": ["mise_en_scene"],
                "short_source_excerpt": None,
                "evidence_status": "critic_reported",
                "extraction_confidence": "medium",
                "missing_fields": ["scene_or_sequence", "techniques"],
            }
        ]
    }
    calls = 0

    def transport(_: str, payload: dict[str, Any] | None, __: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        content = "{not-json" if calls == 1 else json.dumps(valid)
        return {"choices": [{"message": {"content": content}}]}

    with tempfile.TemporaryDirectory() as directory:
        settings = LocalSettingsStore(Path(directory) / "settings.json")
        settings.set("deepseek_api_key", "test-key")
        claims = DeepSeekStudyService(settings, transport=transport).structure_reviews(
            {"title": "Example Film", "year": 2024}, [review]
        )

    assert calls == 2
    assert claims[0].source_id == "R1"


def test_structured_criticism_batches_reviews_and_reindexes_claims() -> None:
    reviews = [
        ReviewSource(
            source_id=f"R{index}",
            provider="Douban",
            review_id=str(index),
            title=f"Review {index}",
            summary="A substantive critical observation about recurring space and memory.",
            url=f"https://movie.douban.com/review/{index}/",
            language="en",
        )
        for index in range(1, 5)
    ]
    batches: list[list[str]] = []

    def transport(_: str, payload: dict[str, Any] | None, __: str) -> dict[str, Any]:
        assert payload is not None
        user_content = payload["messages"][1]["content"]
        source_ids = re.findall(r'"source_id": "(R\d+)"', user_content)
        batches.append(source_ids)
        response = {
            "claims": [
                {
                    "claim_id": "C1",
                    "source_id": source_ids[0],
                    "critic_claim": "The reviewer identifies a recurring relation between space and memory.",
                    "scene_or_sequence": None,
                    "described_observation": None,
                    "techniques": [],
                    "interpretation": None,
                    "alternative_reading": None,
                    "lens_tags": ["narrative"],
                    "short_source_excerpt": None,
                    "evidence_status": "critic_reported",
                    "extraction_confidence": "medium",
                    "missing_fields": ["scene_or_sequence", "techniques"],
                }
            ]
        }
        return {"choices": [{"message": {"content": json.dumps(response)}}]}

    with tempfile.TemporaryDirectory() as directory:
        settings = LocalSettingsStore(Path(directory) / "settings.json")
        settings.set("deepseek_api_key", "test-key")
        claims = DeepSeekStudyService(settings, transport=transport).structure_reviews(
            {"title": "Example Film", "year": 2024}, reviews
        )

    assert batches == [["R1", "R2", "R3"], ["R4"]]
    assert [claim.claim_id for claim in claims] == ["C1", "C2"]


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
def test_crossref_research_imports_only_matched_attributed_abstracts() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1234/mood.2000",
                    "title": ["The Architecture of Desire in In the Mood for Love"],
                    "abstract": "<jats:p>Wong Kar-wai uses corridors, repetition, and withheld reverse shots to organise desire through constrained space.</jats:p>",
                    "author": [{"given": "Mei", "family": "Lin"}],
                    "container-title": ["Journal of Film Studies"],
                    "published": {"date-parts": [[2021, 4, 1]]},
                    "type": "journal-article",
                    "language": "en",
                },
                {
                    "DOI": "10.1234/biology.1",
                    "title": ["Parasites in love"],
                    "abstract": "<p>This unrelated biological abstract studies parasite reproduction in a laboratory.</p>",
                    "author": [{"given": "A", "family": "Biologist"}],
                    "container-title": ["Biology"],
                },
            ]
        }
    }
    adapter = CrossrefResearchAdapter(transport=lambda _: payload)

    provider_id, title, reviews = adapter.fetch_reviews(
        {
            "title": "In the Mood for Love",
            "year": 2000,
            "credits": {"directors": ["Wong Kar-wai"]},
        }
    )

    assert provider_id == "crossref:in-the-mood-for-love"
    assert title == "In the Mood for Love"
    assert len(reviews) == 1
    assert reviews[0].author == "Mei Lin"
    assert reviews[0].provider == "Crossref scholarship"
    assert reviews[0].url == "https://doi.org/10.1234/mood.2000"
    assert "Journal of Film Studies" in (reviews[0].rating_label or "")
