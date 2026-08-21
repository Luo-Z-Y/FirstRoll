from __future__ import annotations

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from app.backend.discovery import DiscoveryProviderError, DiscoveryService
from app.backend.settings import LocalSettingsStore


TMDB_API = "https://api.themoviedb.org/3"
TMDB_WEB = "https://www.themoviedb.org"
TMDB_IMAGE = "https://image.tmdb.org/t/p"
TMDB_SEARCH_CANDIDATES = 8
TMDB_RESPONSE_LIMIT = 4_000_000

TmdbRequest = Callable[[str, dict[str, Any]], dict[str, Any]]


class TmdbDiscoveryService:
    """Official TMDb catalogue adapter with bounded parallel candidate hydration."""

    def __init__(
        self,
        settings: LocalSettingsStore,
        request_json: TmdbRequest | None = None,
    ) -> None:
        self.settings = settings
        self._request_json = request_json or self._http_request
        self._detail_cache: dict[int, dict[str, Any]] = {}
        self._related_cache: dict[tuple[int, int, bool], dict[str, Any]] = {}

    @property
    def configured(self) -> bool:
        return self.settings.secret_state("tmdb").configured

    def status(self) -> dict[str, Any]:
        state = "ready" if self.configured else "credentials_required"
        message = (
            "Official, poster-rich film search and verified crew metadata."
            if self.configured
            else "Add a TMDb Read Access Token to use the primary catalogue."
        )
        return {
            "name": "TMDb",
            "kind": "official_film_catalogue",
            "state": state,
            "message": message,
        }

    def test_connection(self) -> dict[str, Any]:
        self._require_configuration()
        payload = self._request_json("/configuration", {})
        if not isinstance(payload.get("images"), dict):
            raise DiscoveryProviderError("TMDb returned an unexpected configuration response.")
        return {"ok": True, "message": "TMDb catalogue access is working."}

    def search(
        self,
        query: str,
        year: int | None = None,
        director: str | None = None,
    ) -> dict[str, Any]:
        self._require_configuration()
        query = query.strip()
        director = director.strip() if director else None
        if not query:
            raise ValueError("A film title is required.")

        params: dict[str, Any] = {
            "query": query,
            "include_adult": "false",
            "language": "en-GB",
            "page": 1,
        }
        if year is not None:
            params["year"] = year
            params["primary_release_year"] = year
        payload = self._request_json("/search/movie", params)
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise DiscoveryProviderError("TMDb returned an unexpected search response.")

        candidates = [item for item in raw_results if self._valid_id(item.get("id"))]
        candidates = candidates[:TMDB_SEARCH_CANDIDATES]
        films = self._hydrate_candidates(candidates)
        results: list[dict[str, Any]] = []
        for film in films:
            release_years = film.get("release_years") or []
            if year is not None and year not in release_years:
                continue
            if director and not any(
                self._identity_contains(name, director) for name in film.get("directors") or []
            ):
                continue
            film["match_score"] = self._match_score(film, query, year, director)
            results.append(self._public_summary(film))

        results.sort(
            key=lambda item: (
                item.get("match_score") or 0,
                item.get("year") or 0,
            ),
            reverse=True,
        )
        return {
            "query": {"title": query, "year": year, "director": director},
            "results": results,
            "result_count": len(results),
            "mode": "live",
            "sources": [self.status()],
            "generated_at": date.today().isoformat(),
        }

    def detail(self, film_id: str) -> dict[str, Any]:
        self._require_configuration()
        tmdb_id = self._film_id(film_id)
        film = self._detail_cache.get(tmdb_id)
        if film is None:
            film = self._fetch_detail(tmdb_id)
        return {
            "film": self._public_detail(film),
            "mode": "live",
            "sources": [self.status()],
        }

    def related(
        self,
        film_id: str,
        limit: int = 12,
        *,
        fast: bool = False,
        director_only: bool = False,
    ) -> dict[str, Any]:
        del fast  # TMDb shelf responses already contain poster paths.
        self._require_configuration()
        tmdb_id = self._film_id(film_id)
        limit = max(1, min(limit, 60))
        cache_key = (tmdb_id, limit, director_only)
        if cache_key in self._related_cache:
            return self._related_cache[cache_key]

        film = self._detail_cache.get(tmdb_id) or self._fetch_detail(tmdb_id)
        director_ids = film.get("_director_ids") or []
        same_director: list[dict[str, Any]] = []
        seen = {tmdb_id}
        director_names = film.get("directors") or []
        for director_index, director_id in enumerate(director_ids[:2]):
            payload = self._request_json(f"/person/{director_id}/movie_credits", {"language": "en-GB"})
            for credit in payload.get("crew") or []:
                candidate_id = credit.get("id")
                if (
                    credit.get("job") != "Director"
                    or not self._valid_id(candidate_id)
                    or candidate_id in seen
                ):
                    continue
                seen.add(candidate_id)
                summary = self._related_summary(credit, "same_director")
                if summary:
                    summary["directors"] = [
                        director_names[director_index]
                        if director_index < len(director_names)
                        else "Verified TMDb director"
                    ]
                    same_director.append(summary)
                if len(same_director) >= limit:
                    break
            if len(same_director) >= limit:
                break
        same_director.sort(key=lambda item: item.get("year") or 0, reverse=True)

        recommended: list[dict[str, Any]] = []
        if not director_only:
            payload = self._request_json(
                f"/movie/{tmdb_id}/recommendations",
                {"language": "en-GB", "page": 1},
            )
            for item in payload.get("results") or []:
                candidate_id = item.get("id")
                if not self._valid_id(candidate_id) or candidate_id in seen:
                    continue
                seen.add(candidate_id)
                summary = self._related_summary(item, "recommended")
                if summary:
                    recommended.append(summary)
                if len(recommended) >= limit:
                    break

        directors = film.get("directors") or []
        response = {
            "film_id": film_id,
            "director": directors[0] if directors else None,
            "same_director": same_director,
            "shared_cast": [],
            "same_country": [],
            "recommended": recommended,
            "category_labels": {"cast": [], "countries": film.get("countries") or []},
            "state": "ready" if director_ids else "unavailable",
        }
        self._related_cache[cache_key] = response
        return response

    def _hydrate_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not candidates:
            return []
        films_by_id: dict[int, dict[str, Any]] = {}
        pending = [int(item["id"]) for item in candidates if int(item["id"]) not in self._detail_cache]
        for tmdb_id in (int(item["id"]) for item in candidates):
            if tmdb_id in self._detail_cache:
                films_by_id[tmdb_id] = self._detail_cache[tmdb_id]
        if pending:
            with ThreadPoolExecutor(max_workers=min(4, len(pending))) as executor:
                futures = {executor.submit(self._fetch_detail, tmdb_id): tmdb_id for tmdb_id in pending}
                for future in as_completed(futures):
                    tmdb_id = futures[future]
                    try:
                        films_by_id[tmdb_id] = future.result()
                    except (DiscoveryProviderError, LookupError):
                        continue
        if candidates and not films_by_id:
            raise DiscoveryProviderError("TMDb candidate details were unavailable.")
        return [films_by_id[int(item["id"])] for item in candidates if int(item["id"]) in films_by_id]

    def _fetch_detail(self, tmdb_id: int) -> dict[str, Any]:
        payload = self._request_json(
            f"/movie/{tmdb_id}",
            {
                "language": "en-GB",
                "append_to_response": "credits,external_ids,alternative_titles,release_dates",
            },
        )
        if not self._valid_id(payload.get("id")):
            raise LookupError("Film not found in TMDb.")
        film = self._normalise_detail(payload)
        self._detail_cache[tmdb_id] = film
        return film

    def _normalise_detail(self, payload: dict[str, Any]) -> dict[str, Any]:
        tmdb_id = int(payload["id"])
        credits_payload = payload.get("credits") or {}
        crew = credits_payload.get("crew") or []
        cast_payload = sorted(
            (item for item in credits_payload.get("cast") or [] if isinstance(item, dict)),
            key=lambda item: item.get("order", 10_000),
        )
        directors = self._crew_names(crew, {"Director"})
        writers = self._crew_names(crew, {"Screenplay", "Writer", "Story", "Adaptation"})
        producers = self._crew_names(crew, {"Producer", "Executive Producer", "Co-Producer"})
        cinematographers = self._crew_names(crew, {"Director of Photography", "Cinematography"})
        editors = self._crew_names(crew, {"Editor"})
        cast = self._unique_names(cast_payload, limit=16)
        release_dates = [str(payload.get("release_date") or "").strip()]
        for country in (payload.get("release_dates") or {}).get("results") or []:
            for release in country.get("release_dates") or []:
                value = str(release.get("release_date") or "")[:10]
                if value:
                    release_dates.append(value)
        release_dates = list(dict.fromkeys(value for value in release_dates if value))
        release_years = list(
            dict.fromkeys(
                int(value[:4]) for value in release_dates if re.match(r"^\d{4}", value)
            )
        )
        external_payload = payload.get("external_ids") or {}
        external_ids = {
            key: value
            for key, value in {
                "imdb": external_payload.get("imdb_id"),
                "wikidata": external_payload.get("wikidata_id"),
            }.items()
            if value
        }
        title = str(payload.get("title") or payload.get("original_title") or f"TMDb {tmdb_id}")
        alternatives = [
            str(item.get("title") or "").strip()
            for item in (payload.get("alternative_titles") or {}).get("titles") or []
            if isinstance(item, dict)
        ]
        alternatives = list(
            dict.fromkeys(value for value in alternatives if value and value != title)
        )[:60]
        tmdb_url = f"{TMDB_WEB}/movie/{tmdb_id}"
        source = {
            "name": "TMDb",
            "kind": "official_film_catalogue",
            "url": tmdb_url,
            "licence": "TMDb API terms",
        }
        poster_path = payload.get("poster_path")
        backdrop_path = payload.get("backdrop_path")
        return {
            "id": f"tmdb:{tmdb_id}",
            "provider_id": str(tmdb_id),
            "title": title,
            "original_title": str(payload.get("original_title") or title),
            "alternative_titles": alternatives,
            "year": release_years[0] if release_years else None,
            "release_years": release_years,
            "release_date": release_dates[0] if release_dates else None,
            "directors": directors,
            "overview": str(payload.get("overview") or "No synopsis is supplied by TMDb.").strip(),
            "overview_source": {"name": "TMDb", "url": tmdb_url, "licence": "TMDb API terms"},
            "runtime_minutes": payload.get("runtime") if isinstance(payload.get("runtime"), int) else None,
            "genres": self._unique_names(payload.get("genres") or []),
            "countries": self._unique_names(payload.get("production_countries") or []),
            "original_language": payload.get("original_language"),
            "cast": cast,
            "poster_url": f"{TMDB_IMAGE}/w500{poster_path}" if poster_path else None,
            "backdrop_url": f"{TMDB_IMAGE}/w1280{backdrop_path}" if backdrop_path else None,
            "poster_source": {"name": "TMDb poster", "url": tmdb_url} if poster_path else None,
            "credits": {
                "directors": directors,
                "writers": writers,
                "producers": producers,
                "cinematographers": cinematographers,
                "editors": editors,
                "cast": cast,
            },
            "crew_sources": [
                {
                    "name": "TMDb credits",
                    "url": f"{tmdb_url}/cast",
                    "licence": "TMDb API terms",
                    "fields": [
                        field
                        for field, values in (
                            ("directors", directors),
                            ("writers", writers),
                            ("producers", producers),
                            ("cinematographers", cinematographers),
                            ("editors", editors),
                        )
                        if values
                    ],
                }
            ],
            "external_ids": external_ids,
            "awards": [],
            "reviews": [],
            "source": source,
            "evidence_notice": (
                "TMDb establishes film identity and attributed catalogue credits, not creator "
                "intentions or critical interpretation."
            ),
            "_director_ids": [
                int(item["id"])
                for item in crew
                if item.get("job") == "Director" and self._valid_id(item.get("id"))
            ],
        }

    def _public_detail(self, film: dict[str, Any]) -> dict[str, Any]:
        result = {key: value for key, value in film.items() if not key.startswith("_")}
        title = str(result.get("title") or "this film")
        directors = result.get("directors") or []
        director = directors[0] if directors else "the director"
        query = f'"{title}" film {director}'
        links = [
            {"label": "TMDb record", "kind": "identity", "url": result["source"]["url"]}
        ]
        imdb_id = (result.get("external_ids") or {}).get("imdb")
        wikidata_id = (result.get("external_ids") or {}).get("wikidata")
        if imdb_id:
            links.append(
                {
                    "label": "IMDb record",
                    "kind": "industry_database",
                    "url": f"https://www.imdb.com/title/{imdb_id}/",
                }
            )
        if wikidata_id:
            links.append(
                {
                    "label": "Wikidata record",
                    "kind": "open_identity",
                    "url": f"https://www.wikidata.org/wiki/{wikidata_id}",
                }
            )
        links.extend(
            [
                {
                    "label": "Search Google Scholar",
                    "kind": "scholarship_search",
                    "url": f"https://scholar.google.com/scholar?q={quote_plus(query)}",
                },
                {
                    "label": "Search OpenAlex",
                    "kind": "scholarship_search",
                    "url": f"https://openalex.org/works?search={quote_plus(query)}",
                },
            ]
        )
        result["research_links"] = links
        result["study_questions"] = DiscoveryService._study_questions(result)
        return result

    @staticmethod
    def _public_summary(film: dict[str, Any]) -> dict[str, Any]:
        return {
            key: film.get(key)
            for key in (
                "id",
                "provider_id",
                "title",
                "original_title",
                "alternative_titles",
                "year",
                "release_years",
                "runtime_minutes",
                "directors",
                "overview",
                "poster_url",
                "poster_source",
                "backdrop_url",
                "match_score",
                "source",
                "external_ids",
            )
        }

    @staticmethod
    def _related_summary(item: dict[str, Any], relation: str) -> dict[str, Any] | None:
        tmdb_id = item.get("id")
        if not TmdbDiscoveryService._valid_id(tmdb_id):
            return None
        release_date = str(item.get("release_date") or "")
        year = int(release_date[:4]) if re.match(r"^\d{4}", release_date) else None
        poster_path = item.get("poster_path")
        return {
            "id": f"tmdb:{tmdb_id}",
            "provider_id": str(tmdb_id),
            "title": str(item.get("title") or item.get("original_title") or "Untitled"),
            "original_title": str(item.get("original_title") or item.get("title") or "Untitled"),
            "year": year,
            "release_years": [year] if year else [],
            "runtime_minutes": None,
            "directors": [],
            "overview": str(item.get("overview") or ""),
            "poster_url": f"{TMDB_IMAGE}/w500{poster_path}" if poster_path else None,
            "poster_source": (
                {"name": "TMDb poster", "url": f"{TMDB_WEB}/movie/{tmdb_id}"}
                if poster_path
                else None
            ),
            "backdrop_url": None,
            "source": {
                "name": "TMDb",
                "kind": "official_film_catalogue",
                "url": f"{TMDB_WEB}/movie/{tmdb_id}",
                "licence": "TMDb API terms",
            },
            "relation": relation,
        }

    def _http_request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self._require_configuration()
        if not re.fullmatch(r"/[a-z0-9_/-]+", path):
            raise DiscoveryProviderError("The TMDb request path was rejected.")
        url = f"{TMDB_API}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.settings.effective_secret('tmdb')}",
                "User-Agent": "FirstRoll/0.1 (+https://github.com/Luo-Z-Y/FirstRoll)",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                raw = response.read(TMDB_RESPONSE_LIMIT + 1)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise DiscoveryProviderError("TMDb rejected the configured access token.") from exc
            if exc.code == 404:
                raise LookupError("Film not found in TMDb.") from exc
            raise DiscoveryProviderError(f"TMDb returned HTTP {exc.code}.") from exc
        except (TimeoutError, URLError, OSError) as exc:
            raise DiscoveryProviderError("TMDb did not respond within the catalogue deadline.") from exc
        if len(raw) > TMDB_RESPONSE_LIMIT:
            raise DiscoveryProviderError("TMDb returned an unexpectedly large response.")
        try:
            import json

            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise DiscoveryProviderError("TMDb returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise DiscoveryProviderError("TMDb returned an unexpected response.")
        return payload

    def _require_configuration(self) -> None:
        if not self.configured:
            raise DiscoveryProviderError("TMDb is not configured.")

    @staticmethod
    def _film_id(film_id: str) -> int:
        value = film_id.removeprefix("tmdb:")
        if not value.isdigit() or int(value) <= 0:
            raise LookupError("The film identifier is not recognised by the TMDb adapter.")
        return int(value)

    @staticmethod
    def _valid_id(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _crew_names(crew: list[dict[str, Any]], jobs: set[str]) -> list[str]:
        return TmdbDiscoveryService._unique_names(
            [item for item in crew if item.get("job") in jobs]
        )

    @staticmethod
    def _unique_names(items: list[dict[str, Any]], limit: int | None = None) -> list[str]:
        names: list[str] = []
        for item in items:
            name = str(item.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
            if limit is not None and len(names) >= limit:
                break
        return names

    @classmethod
    def _identity_contains(cls, candidate: str, requested: str) -> bool:
        candidate_identity = cls._normalise_identity(candidate)
        requested_identity = cls._normalise_identity(requested)
        return bool(
            candidate_identity
            and requested_identity
            and (candidate_identity in requested_identity or requested_identity in candidate_identity)
        )

    @staticmethod
    def _normalise_identity(value: str) -> str:
        folded = unicodedata.normalize("NFKD", str(value)).casefold()
        return "".join(character for character in folded if character.isalnum())

    @classmethod
    def _match_score(
        cls,
        film: dict[str, Any],
        query: str,
        year: int | None,
        director: str | None,
    ) -> float:
        query_identity = cls._normalise_identity(query)
        titles = [
            film.get("title"),
            film.get("original_title"),
            *(film.get("alternative_titles") or []),
        ]
        similarity = max(
            (
                SequenceMatcher(None, query_identity, cls._normalise_identity(title)).ratio()
                for title in titles
                if title
            ),
            default=0.0,
        )
        score = similarity * 0.78
        if year is not None and year in (film.get("release_years") or []):
            score += 0.12
        if director and any(cls._identity_contains(name, director) for name in film.get("directors") or []):
            score += 0.10
        return round(min(1.0, score), 3)


class HybridDiscoveryService:
    """Route provider-qualified identities and degrade to the open catalogue safely."""

    def __init__(self, primary: TmdbDiscoveryService, fallback: DiscoveryService) -> None:
        self.primary = primary
        self.fallback = fallback

    def status(self) -> dict[str, Any]:
        fallback_status = self.fallback.status()
        return {
            **fallback_status,
            "mode": "live",
            "sources": [self.primary.status(), *fallback_status.get("sources", [])],
            "provider_policy": {
                "primary": "TMDb" if self.primary.configured else "Wikidata",
                "fallback": "Wikidata and Wikipedia",
                "identity_bridge": "IMDb and Wikidata external IDs",
            },
        }

    def search(
        self,
        query: str,
        year: int | None = None,
        director: str | None = None,
    ) -> dict[str, Any]:
        if not self.primary.configured:
            result = self.fallback.search(query, year=year, director=director)
            result["sources"].insert(0, self.primary.status())
            result["provider_policy"] = "key_free_fallback"
            return result
        try:
            result = self.primary.search(query, year=year, director=director)
            result["provider_policy"] = "tmdb_primary"
            return result
        except DiscoveryProviderError as exc:
            result = self.fallback.search(query, year=year, director=director)
            result["mode"] = "degraded"
            result["sources"].insert(
                0,
                {
                    **self.primary.status(),
                    "state": "unavailable",
                    "message": f"Primary catalogue unavailable; open fallback used: {exc}",
                },
            )
            result["provider_policy"] = "wikidata_failover"
            return result

    def detail(self, film_id: str) -> dict[str, Any]:
        if film_id.startswith("tmdb:"):
            try:
                return self.primary.detail(film_id)
            except DiscoveryProviderError as exc:
                raise LookupError(str(exc)) from exc
        return self.fallback.detail(film_id)

    def related(
        self,
        film_id: str,
        limit: int = 12,
        *,
        fast: bool = False,
        director_only: bool = False,
    ) -> dict[str, Any]:
        if film_id.startswith("tmdb:"):
            try:
                return self.primary.related(
                    film_id,
                    limit,
                    fast=fast,
                    director_only=director_only,
                )
            except DiscoveryProviderError:
                return {
                    "film_id": film_id,
                    "director": None,
                    "same_director": [],
                    "shared_cast": [],
                    "same_country": [],
                    "recommended": [],
                    "category_labels": {"cast": [], "countries": []},
                    "state": "unavailable",
                }
        return self.fallback.related(
            film_id,
            limit,
            fast=fast,
            director_only=director_only,
        )
