from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, urlencode
from urllib.request import Request, urlopen


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki"
WIKIMEDIA_FILE_URL = "https://commons.wikimedia.org/wiki/Special:Redirect/file"
WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"


class DiscoveryProviderError(RuntimeError):
    """Raised when a discovery provider cannot complete a request."""


@dataclass(frozen=True)
class SourceStatus:
    name: str
    kind: str
    state: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "kind": self.kind,
            "state": self.state,
            "message": self.message,
        }


DEMO_FILMS: tuple[dict[str, Any], ...] = (
    {
        "id": "demo:in-the-mood-for-love",
        "title": "In the Mood for Love",
        "original_title": "花樣年華",
        "year": 2000,
        "directors": ["Wong Kar-wai"],
        "overview": (
            "In 1960s Hong Kong, two neighbours form an intimate bond after discovering "
            "that their spouses are having an affair."
        ),
        "runtime_minutes": 98,
        "genres": ["Drama", "Romance"],
        "countries": ["Hong Kong", "France"],
        "poster_url": None,
        "backdrop_url": None,
        "release_date": "2000-09-29",
        "credits": {
            "directors": ["Wong Kar-wai"],
            "writers": ["Wong Kar-wai"],
            "cinematographers": ["Christopher Doyle", "Mark Lee Ping-bing"],
        },
    },
    {
        "id": "demo:parasite",
        "title": "Parasite",
        "original_title": "기생충",
        "year": 2019,
        "directors": ["Bong Joon Ho"],
        "overview": (
            "A cash-strapped family gradually enters the household of a wealthy family, "
            "with consequences that expose deep social divisions."
        ),
        "runtime_minutes": 133,
        "genres": ["Drama", "Thriller", "Comedy"],
        "countries": ["South Korea"],
        "poster_url": None,
        "backdrop_url": None,
        "release_date": "2019-05-30",
        "credits": {
            "directors": ["Bong Joon Ho"],
            "writers": ["Bong Joon Ho", "Han Jin-won"],
            "cinematographers": ["Hong Kyung-pyo"],
        },
    },
    {
        "id": "demo:the-godfather",
        "title": "The Godfather",
        "original_title": "The Godfather",
        "year": 1972,
        "directors": ["Francis Ford Coppola"],
        "overview": (
            "The reluctant son of a New York crime-family patriarch is drawn into the "
            "family business as power passes between generations."
        ),
        "runtime_minutes": 175,
        "genres": ["Drama", "Crime"],
        "countries": ["United States"],
        "poster_url": None,
        "backdrop_url": None,
        "release_date": "1972-03-14",
        "credits": {
            "directors": ["Francis Ford Coppola"],
            "writers": ["Mario Puzo", "Francis Ford Coppola"],
            "cinematographers": ["Gordon Willis"],
        },
    },
    {
        "id": "demo:seven-samurai",
        "title": "Seven Samurai",
        "original_title": "七人の侍",
        "year": 1954,
        "directors": ["Akira Kurosawa"],
        "overview": (
            "Farmers threatened by bandits recruit a group of masterless samurai to "
            "defend their village."
        ),
        "runtime_minutes": 207,
        "genres": ["Action", "Drama"],
        "countries": ["Japan"],
        "poster_url": None,
        "backdrop_url": None,
        "release_date": "1954-04-26",
        "credits": {
            "directors": ["Akira Kurosawa"],
            "writers": ["Akira Kurosawa", "Shinobu Hashimoto", "Hideo Oguni"],
            "cinematographers": ["Asakazu Nakai"],
        },
    },
)


JsonRequest = Callable[[dict[str, Any]], dict[str, Any]]
WikipediaRequest = Callable[[str], dict[str, Any]]


class DiscoveryService:
    """Key-free Wikidata discovery with a small explicit offline fallback."""

    def __init__(
        self,
        request_json: JsonRequest | None = None,
        wikipedia_summary: WikipediaRequest | None = None,
    ) -> None:
        self._request_json = request_json or self._wikidata_request
        self._wikipedia_summary = wikipedia_summary or (
            self._wikipedia_request if request_json is None else None
        )
        self._detail_cache: dict[str, dict[str, Any]] = {}

    def status(self) -> dict[str, Any]:
        return {
            "mode": "live",
            "sources": [self._wikidata_status().as_dict()],
            "optional_sources": [
                {
                    "name": "Douban MCP",
                    "state": "optional",
                    "message": "Chinese-language reviews; unofficial local adapter, not required.",
                }
            ],
        }

    def search(
        self,
        query: str,
        year: int | None = None,
        director: str | None = None,
    ) -> dict[str, Any]:
        query = query.strip()
        director = director.strip() if director else None
        if not query:
            raise ValueError("A film title is required.")

        try:
            results = self._search_wikidata(query, year, director)
            return self._search_response(
                query,
                year,
                director,
                results,
                self._wikidata_status(),
                "live",
            )
        except (DiscoveryProviderError, KeyError, TypeError, ValueError) as exc:
            fallback = self._search_demo(query, year, director)
            fallback["mode"] = "degraded"
            fallback["sources"].insert(
                0,
                SourceStatus(
                    name="Wikidata",
                    kind="open_film_identity_metadata",
                    state="unavailable",
                    message=f"Live lookup unavailable: {exc}",
                ).as_dict(),
            )
            return fallback

    def detail(self, film_id: str) -> dict[str, Any]:
        if film_id.startswith("demo:"):
            return self._demo_detail(film_id)
        qid = film_id.removeprefix("wikidata:")
        if not self._valid_qid(qid):
            raise LookupError("The film identifier is not recognised by the Wikidata adapter.")

        detail = self._detail_cache.get(qid)
        if detail is None:
            try:
                entities = self._get_entities([qid])
                entity = entities.get(qid)
                if not entity or entity.get("missing") is not None:
                    raise LookupError("Film not found on Wikidata.")
                detail = self._normalise_entity(entity)
                self._detail_cache[qid] = detail
            except DiscoveryProviderError as exc:
                raise LookupError(str(exc)) from exc

        return {
            "film": self._enrich_detail(dict(detail)),
            "mode": "live",
            "sources": [self._wikidata_status().as_dict()],
        }

    def _search_wikidata(
        self,
        query: str,
        year: int | None,
        director: str | None,
    ) -> list[dict[str, Any]]:
        payload = self._request_json(
            {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "uselang": "en",
                "type": "item",
                "limit": 16,
                "format": "json",
            }
        )
        ids = [item.get("id") for item in payload.get("search", [])]
        qids = [qid for qid in ids if self._valid_qid(qid)]
        if not qids:
            return []

        entities = self._get_entities(qids)
        results: list[dict[str, Any]] = []
        for qid in qids:
            entity = entities.get(qid)
            if not entity or not self._looks_like_film(entity):
                continue
            film = self._normalise_entity(entity)
            film_year = film.get("year")
            directors = film.get("directors", [])
            if year is not None and film_year != year:
                continue
            if director and not any(
                self._normalise_identity(director) in self._normalise_identity(name)
                for name in directors
            ):
                continue
            score = SequenceMatcher(
                None,
                query.casefold(),
                str(film.get("title", "")).casefold(),
            ).ratio()
            if year is not None and film_year == year:
                score += 0.12
            if director:
                score += 0.16
            film["match_score"] = round(min(1.0, score), 3)
            self._detail_cache[qid] = film
            results.append(self._public_live_summary(film))
        results.sort(key=lambda film: film["match_score"], reverse=True)
        return results

    def _get_entities(self, qids: list[str]) -> dict[str, dict[str, Any]]:
        if not qids:
            return {}
        payload = self._request_json(
            {
                "action": "wbgetentities",
                "ids": "|".join(qids[:50]),
                "props": "labels|descriptions|claims|sitelinks",
                "languages": "en|zh|zh-hans|zh-hant|ja|ko|fr|de|it|es",
                "languagefallback": 1,
                "format": "json",
            }
        )
        entities = payload.get("entities", {})
        if not isinstance(entities, dict):
            raise DiscoveryProviderError("Wikidata returned an unexpected response.")

        related_ids: set[str] = set()
        for entity in entities.values():
            claims = entity.get("claims", {})
            for property_id in ("P57", "P58", "P344", "P136", "P495"):
                related_ids.update(self._entity_ids(claims, property_id))
        labels = self._get_labels(sorted(related_ids))
        for entity in entities.values():
            entity["_related_labels"] = labels
        return entities

    def _get_labels(self, qids: list[str]) -> dict[str, str]:
        if not qids:
            return {}
        labels: dict[str, str] = {}
        for offset in range(0, len(qids), 50):
            payload = self._request_json(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(qids[offset : offset + 50]),
                    "props": "labels",
                    "languages": "en|zh|zh-hans|zh-hant|ja|ko|fr|de|it|es",
                    "languagefallback": 1,
                    "format": "json",
                }
            )
            for qid, entity in payload.get("entities", {}).items():
                label = self._best_text(entity.get("labels", {}))
                if label:
                    labels[qid] = label
        return labels

    def _normalise_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        qid = entity.get("id", "")
        claims = entity.get("claims", {})
        labels = entity.get("_related_labels", {})
        title = self._best_text(entity.get("labels", {})) or qid
        original_title = self._original_title(entity.get("labels", {}), title)
        release_date = self._time_value(claims, "P577")
        description = self._best_text(entity.get("descriptions", {}))
        directors = self._labelled_claims(claims, "P57", labels)
        writers = self._labelled_claims(claims, "P58", labels)
        cinematographers = self._labelled_claims(claims, "P344", labels)
        image_name = self._string_value(claims, "P18")
        imdb_id = self._string_value(claims, "P345")
        wikipedia_title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
        return {
            "id": f"wikidata:{qid}",
            "provider_id": qid,
            "title": title,
            "original_title": original_title,
            "year": self._year(release_date),
            "release_date": release_date,
            "directors": directors,
            "overview": (
                f"Wikidata description: {description}."
                if description
                else "No synopsis is supplied by this identity source."
            ),
            "runtime_minutes": self._runtime_minutes(claims),
            "genres": self._labelled_claims(claims, "P136", labels),
            "countries": self._labelled_claims(claims, "P495", labels),
            "poster_url": (
                f"{WIKIMEDIA_FILE_URL}/{quote(image_name)}?width=500"
                if image_name
                else None
            ),
            "backdrop_url": None,
            "credits": {
                "directors": directors,
                "writers": writers,
                "cinematographers": cinematographers,
            },
            "external_ids": {"imdb": imdb_id} if imdb_id else {},
            "reviews": [],
            "source": {
                "name": "Wikidata",
                "kind": "open_film_identity_metadata",
                "url": f"{WIKIDATA_ENTITY_URL}/{qid}",
                "licence": "CC0",
            },
            "evidence_notice": (
                "Wikidata establishes film identity and structured credits, not creator "
                "intentions or critical interpretation."
            ),
            "_wikipedia_title": wikipedia_title,
        }

    def _enrich_detail(self, film: dict[str, Any]) -> dict[str, Any]:
        wikipedia_title = film.pop("_wikipedia_title", None)
        wikipedia_url: str | None = None
        if wikipedia_title:
            wikipedia_url = f"https://en.wikipedia.org/wiki/{quote(str(wikipedia_title).replace(' ', '_'))}"
        if wikipedia_title and self._wikipedia_summary:
            try:
                summary = self._wikipedia_summary(str(wikipedia_title))
            except DiscoveryProviderError:
                summary = {}
            extract = summary.get("extract")
            if isinstance(extract, str) and extract.strip():
                film["overview"] = extract.strip()
                film["overview_source"] = {
                    "name": "Wikipedia",
                    "url": summary.get("content_urls", {}).get("desktop", {}).get("page")
                    or wikipedia_url,
                    "licence": "CC BY-SA",
                }
            wikipedia_url = (
                summary.get("content_urls", {}).get("desktop", {}).get("page")
                or wikipedia_url
            )

        title = str(film.get("title") or "this film")
        directors = film.get("directors") or []
        director = directors[0] if directors else "the director"
        query = f'"{title}" film {director}'
        links = [
            {
                "label": "Wikidata record",
                "kind": "identity",
                "url": film.get("source", {}).get("url"),
            }
        ]
        if wikipedia_url:
            links.append({"label": "Wikipedia article", "kind": "overview", "url": wikipedia_url})
        imdb_id = film.get("external_ids", {}).get("imdb")
        if imdb_id:
            links.append(
                {
                    "label": "IMDb record",
                    "kind": "industry_database",
                    "url": f"https://www.imdb.com/title/{imdb_id}/",
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
        film["research_links"] = [link for link in links if link.get("url")]
        film["study_questions"] = self._study_questions(film)
        return film

    @staticmethod
    def _study_questions(film: dict[str, Any]) -> list[str]:
        title = str(film.get("title") or "the film")
        directors = film.get("directors") or []
        director = directors[0] if directors else "the director"
        cinematographers = film.get("credits", {}).get("cinematographers") or []
        questions = [
            f"How does {director} organise point of view in {title}?",
            "Where do changes in cutting rhythm mark shifts in dramatic structure?",
            "Which creator interviews or production records clarify key formal choices?",
        ]
        if cinematographers:
            questions.insert(
                1,
                f"How does {cinematographers[0]}'s cinematography shape space and mood?",
            )
        return questions[:4]

    def _search_demo(
        self,
        query: str,
        year: int | None,
        director: str | None,
    ) -> dict[str, Any]:
        needle = query.casefold()
        director_needle = director.casefold() if director else None
        results: list[dict[str, Any]] = []
        for film in DEMO_FILMS:
            title_haystack = f"{film['title']} {film['original_title']}".casefold()
            title_ratio = SequenceMatcher(None, needle, film["title"].casefold()).ratio()
            contains_title = needle in title_haystack
            matches_year = year is None or film["year"] == year
            matches_director = director_needle is None or any(
                director_needle in name.casefold() for name in film["directors"]
            )
            if (contains_title or title_ratio >= 0.34) and matches_year and matches_director:
                summary = self._public_demo_summary(film)
                summary["match_score"] = round(
                    min(
                        1.0,
                        title_ratio
                        + (0.12 if matches_year and year else 0)
                        + (0.12 if director else 0),
                    ),
                    3,
                )
                results.append(summary)
        results.sort(key=lambda film: film["match_score"], reverse=True)
        return self._search_response(
            query,
            year,
            director,
            results,
            self._demo_status(),
            "offline",
        )

    def _demo_detail(self, film_id: str) -> dict[str, Any]:
        film = next((item for item in DEMO_FILMS if item["id"] == film_id), None)
        if not film:
            raise LookupError("Film not found in the offline catalogue.")
        detail = {**film}
        detail["provider_id"] = film["id"]
        detail["reviews"] = []
        detail["external_ids"] = {}
        detail["source"] = {
            "name": "Curated offline catalogue",
            "kind": "local_demo_metadata",
            "url": None,
        }
        detail["evidence_notice"] = (
            "This bundled record keeps basic discovery working without internet access. "
            "Reconnect to use key-free Wikidata search."
        )
        return {
            "film": self._enrich_detail(detail),
            "mode": "offline",
            "sources": [self._demo_status().as_dict()],
        }

    def _wikidata_request(self, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{WIKIDATA_API}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "FirstRoll/0.1 (https://github.com/Luo-Z-Y/FirstRoll)",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise DiscoveryProviderError(f"Wikidata returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DiscoveryProviderError("Wikidata could not be reached.") from exc

    @staticmethod
    def _wikipedia_request(title: str) -> dict[str, Any]:
        url = f"{WIKIPEDIA_SUMMARY_URL}/{quote(title.replace(' ', '_'), safe='')}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "FirstRoll/0.1 (https://github.com/Luo-Z-Y/FirstRoll)",
            },
        )
        try:
            with urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                return {}
            raise DiscoveryProviderError(f"Wikipedia returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DiscoveryProviderError("Wikipedia could not be reached.") from exc

    @staticmethod
    def _looks_like_film(entity: dict[str, Any]) -> bool:
        description = DiscoveryService._best_text(entity.get("descriptions", {})).casefold()
        return any(term in description for term in ("film", "movie", "motion picture"))

    @staticmethod
    def _normalise_identity(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    @staticmethod
    def _valid_qid(value: Any) -> bool:
        return isinstance(value, str) and value.startswith("Q") and value[1:].isdigit()

    @staticmethod
    def _entity_ids(claims: dict[str, Any], property_id: str) -> list[str]:
        values: list[str] = []
        for claim in claims.get(property_id, []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            qid = value.get("id") if isinstance(value, dict) else None
            if DiscoveryService._valid_qid(qid) and qid not in values:
                values.append(qid)
        return values

    @staticmethod
    def _labelled_claims(
        claims: dict[str, Any],
        property_id: str,
        labels: dict[str, str],
    ) -> list[str]:
        return [labels.get(qid, qid) for qid in DiscoveryService._entity_ids(claims, property_id)]

    @staticmethod
    def _best_text(values: dict[str, Any]) -> str:
        for language in ("en", "zh", "zh-hans", "zh-hant", "ja", "ko", "fr", "de", "it", "es"):
            value = values.get(language, {}).get("value")
            if value:
                return str(value)
        for item in values.values():
            if isinstance(item, dict) and item.get("value"):
                return str(item["value"])
        return ""

    @staticmethod
    def _original_title(labels: dict[str, Any], title: str) -> str:
        for language in ("zh", "zh-hans", "zh-hant", "ja", "ko"):
            value = labels.get(language, {}).get("value")
            if value and value != title:
                return str(value)
        return title

    @staticmethod
    def _time_value(claims: dict[str, Any], property_id: str) -> str | None:
        for claim in claims.get(property_id, []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            raw = value.get("time") if isinstance(value, dict) else None
            if isinstance(raw, str) and len(raw) >= 11:
                return raw[1:11]
        return None

    @staticmethod
    def _string_value(claims: dict[str, Any], property_id: str) -> str | None:
        for claim in claims.get(property_id, []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _runtime_minutes(claims: dict[str, Any]) -> int | None:
        for claim in claims.get("P2047", []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if not isinstance(value, dict):
                continue
            try:
                amount = float(value.get("amount"))
            except (TypeError, ValueError):
                continue
            unit = str(value.get("unit", ""))
            if unit.endswith("Q11574"):
                amount /= 60
            return round(amount)
        return None

    @staticmethod
    def _year(value: str | None) -> int | None:
        try:
            return int(value[:4]) if value else None
        except ValueError:
            return None

    @staticmethod
    def _public_live_summary(film: dict[str, Any]) -> dict[str, Any]:
        return {
            key: film.get(key)
            for key in (
                "id",
                "provider_id",
                "title",
                "original_title",
                "year",
                "directors",
                "overview",
                "poster_url",
                "backdrop_url",
                "match_score",
                "source",
            )
        }

    @staticmethod
    def _public_demo_summary(film: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": film["id"],
            "provider_id": film["id"],
            "title": film["title"],
            "original_title": film["original_title"],
            "year": film["year"],
            "directors": film["directors"],
            "overview": film["overview"],
            "poster_url": film["poster_url"],
            "backdrop_url": film["backdrop_url"],
            "source": {"name": "Curated offline catalogue", "kind": "local_demo_metadata"},
        }

    @staticmethod
    def _search_response(
        query: str,
        year: int | None,
        director: str | None,
        results: list[dict[str, Any]],
        status: SourceStatus,
        mode: str,
    ) -> dict[str, Any]:
        return {
            "query": {"title": query, "year": year, "director": director},
            "results": results,
            "result_count": len(results),
            "mode": mode,
            "sources": [status.as_dict()],
            "generated_at": date.today().isoformat(),
        }

    @staticmethod
    def _wikidata_status() -> SourceStatus:
        return SourceStatus(
            name="Wikidata",
            kind="open_film_identity_metadata",
            state="ready",
            message="Key-free title, year and director lookup. Internet connection required.",
        )

    @staticmethod
    def _demo_status() -> SourceStatus:
        return SourceStatus(
            name="Curated offline catalogue",
            kind="local_demo_metadata",
            state="offline",
            message="Bundled fallback records are available when Wikidata cannot be reached.",
        )
