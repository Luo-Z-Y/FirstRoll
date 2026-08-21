from __future__ import annotations

from pathlib import Path
from typing import Any

from app.backend.discovery import DiscoveryProviderError
from app.backend.settings import LocalSettingsStore
from app.backend.tmdb_discovery import HybridDiscoveryService, TmdbDiscoveryService


def tmdb_film(
    tmdb_id: int,
    title: str,
    year: int,
    director: str,
    *,
    imdb_id: str | None = None,
    wikidata_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": title,
        "overview": f"A catalogue synopsis for {title}.",
        "release_date": f"{year}-05-20",
        "runtime": 101,
        "poster_path": f"/{tmdb_id}.jpg",
        "backdrop_path": f"/{tmdb_id}-wide.jpg",
        "original_language": "en",
        "genres": [{"id": 18, "name": "Drama"}],
        "production_countries": [{"iso_3166_1": "GB", "name": "United Kingdom"}],
        "credits": {
            "crew": [
                {"id": 900, "name": director, "job": "Director"},
                {"id": 901, "name": "Example Writer", "job": "Screenplay"},
                {"id": 902, "name": "Example DP", "job": "Director of Photography"},
            ],
            "cast": [{"id": 903, "name": "Example Actor", "order": 0}],
        },
        "external_ids": {"imdb_id": imdb_id, "wikidata_id": wikidata_id},
        "alternative_titles": {"titles": [{"iso_3166_1": "FR", "title": f"{title} FR"}]},
        "release_dates": {
            "results": [
                {
                    "iso_3166_1": "GB",
                    "release_dates": [{"release_date": f"{year}-05-20T00:00:00.000Z"}],
                }
            ]
        },
    }


def configured_settings(tmp_path: Path) -> LocalSettingsStore:
    settings = LocalSettingsStore(tmp_path / "settings.json")
    settings.set("tmdb_bearer_token", "test-token")
    return settings


def test_tmdb_search_hydrates_bounded_candidates_and_verifies_identity(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    films = {
        10: tmdb_film(10, "Shared Title", 2024, "Correct Director", imdb_id="tt1234567", wikidata_id="Q10"),
        11: tmdb_film(11, "Shared Title", 1999, "Other Director", imdb_id="tt7654321"),
    }

    def request(path: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((path, params))
        if path == "/search/movie":
            return {"results": [{"id": 10}, {"id": 11}]}
        return films[int(path.rsplit("/", 1)[-1])]

    service = TmdbDiscoveryService(configured_settings(tmp_path), request)

    result = service.search("Shared Title", year=2024, director="Correct")

    assert result["mode"] == "live"
    assert [item["id"] for item in result["results"]] == ["tmdb:10"]
    film = result["results"][0]
    assert film["directors"] == ["Correct Director"]
    assert film["external_ids"] == {"imdb": "tt1234567", "wikidata": "Q10"}
    assert film["poster_url"].endswith("/w500/10.jpg")
    assert calls[0][0] == "/search/movie"
    assert calls[0][1]["primary_release_year"] == 2024
    assert sorted(path for path, _ in calls[1:]) == ["/movie/10", "/movie/11"]


def test_tmdb_detail_exposes_credits_provenance_and_identity_links(tmp_path: Path) -> None:
    payload = tmdb_film(
        10,
        "Example Film",
        2024,
        "Example Director",
        imdb_id="tt1234567",
        wikidata_id="Q10",
    )
    service = TmdbDiscoveryService(
        configured_settings(tmp_path),
        lambda path, _params: payload if path == "/movie/10" else {},
    )

    result = service.detail("tmdb:10")

    film = result["film"]
    assert film["credits"]["cinematographers"] == ["Example DP"]
    assert film["crew_sources"][0]["name"] == "TMDb credits"
    assert {link["label"] for link in film["research_links"]} >= {
        "TMDb record",
        "IMDb record",
        "Wikidata record",
    }
    assert not any(key.startswith("_") for key in film)


def test_tmdb_related_uses_director_filmography_without_detail_n_plus_one(tmp_path: Path) -> None:
    payload = tmdb_film(10, "Example Film", 2024, "Example Director")

    def request(path: str, _params: dict[str, Any]) -> dict[str, Any]:
        if path == "/movie/10":
            return payload
        if path == "/person/900/movie_credits":
            return {
                "crew": [
                    {"id": 10, "job": "Director", "title": "Example Film", "release_date": "2024-05-20"},
                    {
                        "id": 12,
                        "job": "Director",
                        "title": "Earlier Film",
                        "original_title": "Earlier Film",
                        "release_date": "2018-01-03",
                        "poster_path": "/12.jpg",
                    },
                ]
            }
        raise AssertionError(path)

    service = TmdbDiscoveryService(configured_settings(tmp_path), request)

    result = service.related("tmdb:10", director_only=True)

    assert result["state"] == "ready"
    assert [item["title"] for item in result["same_director"]] == ["Earlier Film"]
    assert result["same_director"][0]["directors"] == ["Example Director"]
    assert result["same_director"][0]["poster_url"].endswith("/w500/12.jpg")


class FakeFallback:
    def status(self) -> dict[str, Any]:
        return {"mode": "live", "sources": [{"name": "Wikidata", "state": "ready"}]}

    def search(self, query: str, year: int | None = None, director: str | None = None) -> dict[str, Any]:
        return {
            "query": {"title": query, "year": year, "director": director},
            "results": [{"id": "wikidata:Q1"}],
            "result_count": 1,
            "mode": "live",
            "sources": [{"name": "Wikidata", "state": "ready"}],
        }

    def detail(self, film_id: str) -> dict[str, Any]:
        return {"film": {"id": film_id}}

    def related(self, film_id: str, limit: int, **_kwargs: Any) -> dict[str, Any]:
        return {"film_id": film_id, "limit": limit}


def test_hybrid_uses_key_free_fallback_when_tmdb_is_not_configured(tmp_path: Path) -> None:
    settings = LocalSettingsStore(tmp_path / "settings.json")
    service = HybridDiscoveryService(TmdbDiscoveryService(settings), FakeFallback())  # type: ignore[arg-type]

    result = service.search("Example Film")

    assert result["results"][0]["id"] == "wikidata:Q1"
    assert result["provider_policy"] == "key_free_fallback"
    assert result["sources"][0]["state"] == "credentials_required"


def test_hybrid_fails_over_when_tmdb_times_out(tmp_path: Path) -> None:
    def unavailable(_path: str, _params: dict[str, Any]) -> dict[str, Any]:
        raise DiscoveryProviderError("timeout")

    primary = TmdbDiscoveryService(configured_settings(tmp_path), unavailable)
    service = HybridDiscoveryService(primary, FakeFallback())  # type: ignore[arg-type]

    result = service.search("Example Film")

    assert result["mode"] == "degraded"
    assert result["provider_policy"] == "wikidata_failover"
    assert result["results"][0]["id"] == "wikidata:Q1"
    assert result["sources"][0]["state"] == "unavailable"
