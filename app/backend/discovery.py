from __future__ import annotations

import html
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, urlencode
from urllib.request import Request, urlopen


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki"
WIKIMEDIA_FILE_URL = "https://commons.wikimedia.org/wiki/Special:Redirect/file"
WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
LETTERBOXD_WEB = "https://letterboxd.com"
RELATED_POSTER_FALLBACK_LIMIT = 8


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
SparqlRequest = Callable[[str], dict[str, Any]]
PosterRequest = Callable[[str], dict[str, Any] | None]
IdentityPosterRequest = Callable[[str, int | None, str], dict[str, Any] | None]


def _clean_infobox_text(value: str, preserve_lines: bool = False) -> str:
    value = re.sub(r"\[[^\]]*\]", "", value)
    if preserve_lines:
        lines = [re.sub(r"\s+", " ", line).strip(" ,;\n") for line in value.splitlines()]
        return "\n".join(line for line in lines if line)
    return re.sub(r"\s+", " ", value).strip()


def _infobox_people(value: str) -> list[str]:
    people: list[str] = []
    for item in re.split(r"\n+|\s*;\s*", value):
        name = re.sub(r"^(?:and|with)\s+", "", item.strip(), flags=re.IGNORECASE)
        if _valid_credit_name(name) and name not in people:
            people.append(name)
    return people


def _valid_credit_name(value: str) -> bool:
    """Reject page machinery and malformed tokens before they become visible credits."""
    if not 2 <= len(value) <= 120 or not any(character.isalpha() for character in value):
        return False
    lowered = value.casefold()
    forbidden = (
        ".mw-",
        "mw-parser-output",
        "line-height",
        "list-style",
        "margin:",
        "padding:",
        "display:",
        "font-size:",
        "@media",
        "!important",
        "var(",
        "<style",
        "<script",
    )
    if any(marker in lowered for marker in forbidden):
        return False
    if any(character in value for character in "{}<>"):
        return False
    return len(re.findall(r"[,:;]", value)) <= 2


def _infobox_runtime_minutes(value: str) -> int | None:
    hours = re.search(r"(\d+)\s*(?:hours?|hrs?|h)\b", value, flags=re.IGNORECASE)
    minutes = re.search(r"(\d+)\s*(?:minutes?|mins?|m)\b", value, flags=re.IGNORECASE)
    if hours:
        return int(hours.group(1)) * 60 + (int(minutes.group(1)) if minutes else 0)
    return int(minutes.group(1)) if minutes else None


class WikipediaInfoboxParser(HTMLParser):
    """Extract labelled cells from the first Wikipedia infobox table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: dict[str, str] = {}
        self._table_depth = 0
        self._cell: str | None = None
        self._label: list[str] = []
        self._value: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = str(attributes.get("class") or "").split()
        if tag == "table":
            if self._table_depth:
                self._table_depth += 1
            elif "infobox" in classes:
                self._table_depth = 1
            return
        if not self._table_depth:
            return
        if self._ignored_depth:
            self._ignored_depth += 1
            return
        if tag in {"style", "script", "template", "noscript"}:
            self._ignored_depth = 1
            return
        if tag == "th" and "infobox-label" in classes:
            self._cell = "label"
            self._label = []
        elif tag == "td" and "infobox-data" in classes:
            self._cell = "value"
            self._value = []
        elif tag in {"br", "li"} and self._cell == "value":
            self._value.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self._table_depth:
            return
        if self._ignored_depth:
            self._ignored_depth -= 1
            return
        if tag == "table":
            self._table_depth -= 1
            return
        if tag == "th" and self._cell == "label":
            self._cell = None
        elif tag == "td" and self._cell == "value":
            label = _clean_infobox_text("".join(self._label))
            value = _clean_infobox_text("".join(self._value), preserve_lines=True)
            if label and value:
                self.rows[label.casefold()] = value
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._cell == "label":
            self._label.append(data)
        elif self._cell == "value":
            self._value.append(data)


class DiscoveryService:
    """Key-free Wikidata discovery with a small explicit offline fallback."""

    def __init__(
        self,
        request_json: JsonRequest | None = None,
        wikipedia_search: JsonRequest | None = None,
        wikipedia_summary: WikipediaRequest | None = None,
        wikipedia_infobox: WikipediaRequest | None = None,
        sparql_json: SparqlRequest | None = None,
        poster_request: PosterRequest | None = None,
        identity_poster_request: IdentityPosterRequest | None = None,
    ) -> None:
        self._request_json = request_json or self._wikidata_request
        self._wikipedia_search = wikipedia_search or (
            self._wikipedia_search_request if request_json is None else None
        )
        self._wikipedia_summary = wikipedia_summary or (
            self._wikipedia_request if request_json is None else None
        )
        self._wikipedia_infobox = wikipedia_infobox or (
            self._wikipedia_infobox_request if request_json is None else None
        )
        self._sparql_json = sparql_json or (
            self._wikidata_sparql_request if request_json is None else None
        )
        self._poster_request = poster_request or (
            self._letterboxd_poster_request if request_json is None else None
        )
        self._identity_poster_request = identity_poster_request or (
            self._letterboxd_identity_poster_request if request_json is None else None
        )
        self._detail_cache: dict[str, dict[str, Any]] = {}
        self._related_cache: dict[tuple[str, int, bool, bool], dict[str, Any]] = {}

    def status(self) -> dict[str, Any]:
        return {
            "mode": "live",
            "sources": [self._wikidata_status().as_dict(), self._wikipedia_status().as_dict()],
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

        public_detail = dict(detail)
        for internal_key in ("_director_ids", "_cast_ids", "_country_ids", "_genre_ids"):
            public_detail.pop(internal_key, None)
        return {
            "film": self._enrich_detail(public_detail),
            "mode": "live",
            "sources": [self._wikidata_status().as_dict(), self._wikipedia_status().as_dict()],
        }

    def related(
        self,
        film_id: str,
        limit: int = 12,
        *,
        fast: bool = False,
        director_only: bool = False,
    ) -> dict[str, Any]:
        """Return director films, optionally with broader relation groups."""
        limit = max(1, min(limit, 60))
        if film_id.startswith("demo:"):
            return self._demo_related(film_id, limit, director_only=director_only)

        qid = film_id.removeprefix("wikidata:")
        if not self._valid_qid(qid):
            raise LookupError("The film identifier is not recognised by the Wikidata adapter.")
        cache_key = (qid, limit, director_only, fast)
        if cache_key in self._related_cache:
            return self._related_cache[cache_key]
        if qid not in self._detail_cache:
            self.detail(film_id)
        film = self._detail_cache.get(qid) or {}
        director_ids = film.get("_director_ids") or []
        cast_ids = (film.get("_cast_ids") or [])[:3]
        country_ids = (film.get("_country_ids") or [])[:3]
        genre_ids = (film.get("_genre_ids") or [])[:2]
        director_names = film.get("directors") or []
        cast_names = film.get("cast") or []
        country_names = film.get("countries") or []
        director = director_names[0] if director_names else None
        response = {
            "film_id": film_id,
            "director": director,
            "same_director": [],
            "shared_cast": [],
            "same_country": [],
            "recommended": [],
            "category_labels": {
                "cast": cast_names[:3],
                "countries": country_names[:3],
            },
            "state": "ready",
        }
        if not director_ids or self._sparql_json is None:
            response["state"] = "unavailable"
            return response

        director_id = director_ids[0]
        unions = [f"""{{
  {{ SELECT DISTINCT ?film WHERE {{ ?film wdt:P57 wd:{director_id} . }} LIMIT 48 }}
  BIND(4 AS ?rank)
  BIND(\"same_director\" AS ?relation)
  BIND(wd:{director_id} AS ?shared)
}}"""]
        if cast_ids and not director_only:
            unions.append(f"""{{
  {{ SELECT DISTINCT ?film ?shared WHERE {{
    VALUES ?shared {{ {' '.join(f'wd:{value}' for value in cast_ids)} }}
    ?film wdt:P161 ?shared .
  }} LIMIT 30 }}
  BIND(3 AS ?rank)
  BIND(\"shared_cast\" AS ?relation)
}}""")
        if country_ids and not director_only:
            unions.append(f"""{{
  {{ SELECT DISTINCT ?film ?shared WHERE {{
    VALUES ?shared {{ {' '.join(f'wd:{value}' for value in country_ids)} }}
    ?film wdt:P495 ?shared .
  }} LIMIT 30 }}
  BIND(2 AS ?rank)
  BIND(\"same_country\" AS ?relation)
}}""")
        if genre_ids and not director_only:
            unions.append(f"""{{
  {{ SELECT DISTINCT ?film ?shared WHERE {{
    VALUES ?shared {{ {' '.join(f'wd:{value}' for value in genre_ids)} }}
    ?film wdt:P136 ?shared .
  }} LIMIT 60 }}
  BIND(1 AS ?rank)
  BIND(\"shared_genre\" AS ?relation)
}}""")
        if director_only:
            candidate_cap = min(48, max(limit * 2, limit))
            query_limit = min(48, max(candidate_cap, limit * 3))
        else:
            candidate_cap = min(168, max(40, limit * 5)) if fast else 168
            query_limit = min(168, max(candidate_cap, limit * 8))
        query = f"""
SELECT DISTINCT ?film ?relation ?shared ?rank WHERE {{
  {' UNION '.join(unions)}
  FILTER(?film != wd:{qid})
}}
ORDER BY DESC(?rank)
LIMIT {query_limit}
""".strip()
        try:
            payload = self._sparql_json(query)
            candidate_ids = self._sparql_entity_ids(payload, "film")
            selected_ids = candidate_ids[:candidate_cap]
            entities = (
                self._get_shelf_entities(selected_ids)
                if fast or director_only
                else self._get_entities(selected_ids)
            )
        except (DiscoveryProviderError, KeyError, TypeError, ValueError):
            response["state"] = "unavailable"
            return response

        relations: dict[str, list[tuple[str, str | None]]] = {}
        for binding in payload.get("results", {}).get("bindings", []):
            if not isinstance(binding, dict):
                continue
            raw_film = binding.get("film", {}).get("value")
            candidate_id = str(raw_film or "").rsplit("/", 1)[-1]
            if not self._valid_qid(candidate_id):
                continue
            relation = str(binding.get("relation", {}).get("value") or "same_director")
            raw_shared = binding.get("shared", {}).get("value")
            shared_id = str(raw_shared or "").rsplit("/", 1)[-1]
            relations.setdefault(candidate_id, []).append(
                (relation, shared_id if self._valid_qid(shared_id) else None)
            )

        prepared_director_candidates: dict[str, dict[str, Any]] = {}
        if director_only and not fast:
            for candidate_id in candidate_ids:
                entity = entities.get(candidate_id)
                if not entity or not self._looks_like_film(entity):
                    continue
                candidate = self._normalise_entity(entity)
                cached_candidate = self._detail_cache.get(candidate_id) or {}
                if not candidate.get("poster_url") and cached_candidate.get("poster_url"):
                    candidate["poster_url"] = cached_candidate["poster_url"]
                    candidate["poster_source"] = cached_candidate.get("poster_source")
                self._detail_cache[candidate_id] = candidate
                prepared_director_candidates[candidate_id] = candidate
                if len(prepared_director_candidates) >= limit:
                    break
            self._enrich_director_posters(list(prepared_director_candidates.values()))

        labels_by_id = {
            **dict(zip(cast_ids, cast_names, strict=False)),
            **dict(zip(country_ids, country_names, strict=False)),
        }
        groups: dict[str, list[dict[str, Any]]] = {
            "same_director": [],
            "shared_cast": [],
            "same_country": [],
            "recommended": [],
        }
        assigned_by_group: dict[str, set[str]] = {name: set() for name in groups}
        poster_fallbacks_remaining = RELATED_POSTER_FALLBACK_LIMIT
        for candidate_id in candidate_ids:
            entity = entities.get(candidate_id)
            if not entity or not self._looks_like_film(entity):
                continue
            candidate_relations = list(relations.get(candidate_id, [("same_director", None)]))
            claims = entity.get("claims", {})
            candidate_country_ids = self._entity_ids(claims, "P495")
            candidate_genre_ids = self._entity_ids(claims, "P136")
            if not director_only:
                if shared_country := next(
                    (value for value in country_ids if value in candidate_country_ids),
                    None,
                ):
                    candidate_relations.append(("same_country", shared_country))
                if shared_genre := next(
                    (value for value in genre_ids if value in candidate_genre_ids),
                    None,
                ):
                    candidate_relations.append(("shared_genre", shared_genre))
            if director_only and not fast:
                candidate = prepared_director_candidates.get(candidate_id)
                if not candidate:
                    continue
            else:
                candidate = self._normalise_entity(entity)
                if fast:
                    if any(relation == "same_director" for relation, _ in candidate_relations):
                        candidate["directors"] = [director] if director else []
                else:
                    cached_candidate = self._detail_cache.get(candidate_id) or {}
                    if not candidate.get("poster_url") and cached_candidate.get("poster_url"):
                        candidate["poster_url"] = cached_candidate["poster_url"]
                        candidate["poster_source"] = cached_candidate.get("poster_source")
                    self._detail_cache[candidate_id] = candidate
                    self._enrich_poster(candidate)
                    if poster_fallbacks_remaining > 0 and not candidate.get("poster_url"):
                        self._enrich_letterboxd_poster(candidate)
                        poster_fallbacks_remaining -= 1
            summary = self._public_live_summary(candidate)
            for relation, shared_id in candidate_relations:
                group = "recommended" if relation == "shared_genre" else relation
                if group not in groups or candidate_id in assigned_by_group[group]:
                    continue
                if (fast or group != "same_director") and len(groups[group]) >= limit:
                    continue
                related_summary = dict(summary)
                related_summary["relation"] = relation
                related_summary["relation_label"] = labels_by_id.get(shared_id or "")
                groups[group].append(related_summary)
                assigned_by_group[group].add(candidate_id)
        for films in groups.values():
            films.sort(key=lambda item: (item.get("year") is None, -(item.get("year") or 0)))
        response.update(groups)
        self._related_cache[cache_key] = response
        return response

    def _get_shelf_entities(self, qids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch only the entity fields needed to build shelf summaries."""
        entities: dict[str, dict[str, Any]] = {}
        for offset in range(0, len(qids), 50):
            payload = self._request_json(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(qids[offset : offset + 50]),
                    "props": "labels|descriptions|claims|sitelinks",
                    "languages": "en|zh|zh-hans|zh-hant|ja|ko|fr|de|it|es",
                    "languagefallback": 1,
                    "format": "json",
                }
            )
            batch = payload.get("entities", {})
            if not isinstance(batch, dict):
                raise DiscoveryProviderError("Wikidata returned an unexpected response.")
            entities.update(batch)
        director_ids = {
            director_id
            for entity in entities.values()
            for director_id in self._entity_ids(entity.get("claims", {}), "P57")
        }
        director_labels = self._get_labels(sorted(director_ids))
        for entity in entities.values():
            entity["_related_labels"] = director_labels
        return entities

    def _enrich_director_posters(self, films: list[dict[str, Any]]) -> None:
        """Hydrate shelf covers with one Wikipedia request and bounded fallbacks."""
        if not films:
            return
        for film in films:
            self._discard_unverified_poster(film)

        wikipedia_titles = [
            str(film.get("_wikipedia_title") or "").strip()
            for film in films
            if not film.get("poster_url") and film.get("_wikipedia_title")
        ]
        used_wikipedia_batch = False
        if wikipedia_titles and self._wikipedia_search:
            try:
                payload = self._wikipedia_search(
                    {
                        "action": "query",
                        "titles": "|".join(wikipedia_titles),
                        "prop": "pageimages|info",
                        "piprop": "original|thumbnail|name",
                        "pilicense": "any",
                        "pithumbsize": 500,
                        "inprop": "url",
                        "redirects": 1,
                        "format": "json",
                        "formatversion": 2,
                    }
                )
                pages = payload.get("query", {}).get("pages", [])
                if isinstance(pages, dict):
                    pages = list(pages.values())
                if not isinstance(pages, list):
                    raise TypeError("Wikipedia returned an unexpected page-image response.")
                films_by_title = {
                    self._normalise_identity(str(film.get("_wikipedia_title") or "")): film
                    for film in films
                    if film.get("_wikipedia_title")
                }
                for alias_group in ("normalized", "redirects"):
                    for alias in payload.get("query", {}).get(alias_group, []):
                        source = self._normalise_identity(str(alias.get("from") or ""))
                        target = self._normalise_identity(str(alias.get("to") or ""))
                        if source in films_by_title and target:
                            films_by_title[target] = films_by_title[source]
                for page in pages:
                    if not isinstance(page, dict):
                        continue
                    film = films_by_title.get(
                        self._normalise_identity(str(page.get("title") or ""))
                    )
                    if not film:
                        continue
                    self._apply_wikipedia_image(
                        film,
                        {
                            "originalimage": page.get("original"),
                            "thumbnail": page.get("thumbnail"),
                            "content_urls": {"desktop": {"page": page.get("fullurl")}},
                        },
                        str(page.get("fullurl") or "") or None,
                    )
                used_wikipedia_batch = True
            except (DiscoveryProviderError, KeyError, TypeError, ValueError):
                used_wikipedia_batch = False

        if not used_wikipedia_batch:
            for film in films:
                if not film.get("poster_url"):
                    self._enrich_poster(film)

        missing = [film for film in films if not film.get("poster_url")]
        if not missing:
            return
        worker_count = min(4, len(missing))
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="filmography-poster",
        ) as pool:
            list(pool.map(self._enrich_letterboxd_poster, missing))

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
        for qid in self._wikipedia_search_qids(query, year, director):
            if qid not in qids:
                qids.append(qid)
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
            release_years = film.get("release_years") or ([film_year] if film_year else [])
            directors = film.get("directors", [])
            if year is not None and year not in release_years:
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
            elif year is not None and year in release_years:
                score += 0.1
                film["matched_year"] = year
            if director:
                score += 0.16
            film["match_score"] = round(min(1.0, score), 3)
            self._detail_cache[qid] = film
            results.append(film)
        results.sort(key=lambda film: film["match_score"], reverse=True)
        for index, film in enumerate(results[:8]):
            self._enrich_poster(film, external_fallback=index == 0)
        return [self._public_live_summary(film) for film in results]

    def _wikipedia_search_qids(
        self,
        query: str,
        year: int | None,
        director: str | None,
    ) -> list[str]:
        """Supplement Wikidata's lagging title index with Wikipedia film identities."""
        if not self._wikipedia_search:
            return []
        search = " ".join(
            part for part in (query, str(year) if year else None, director, "film") if part
        )
        try:
            payload = self._wikipedia_search(
                {
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": search,
                    "gsrnamespace": 0,
                    "gsrlimit": 12,
                    "prop": "pageprops",
                    "ppprop": "wikibase_item",
                    "format": "json",
                    "formatversion": 2,
                }
            )
        except DiscoveryProviderError:
            return []
        pages = payload.get("query", {}).get("pages", [])
        if isinstance(pages, dict):
            pages = list(pages.values())
        if not isinstance(pages, list):
            return []
        pages.sort(key=lambda page: page.get("index", 10_000) if isinstance(page, dict) else 10_000)
        qids: list[str] = []
        for page in pages:
            qid = page.get("pageprops", {}).get("wikibase_item") if isinstance(page, dict) else None
            if self._valid_qid(qid) and qid not in qids:
                qids.append(qid)
        return qids

    def _get_entities(self, qids: list[str]) -> dict[str, dict[str, Any]]:
        if not qids:
            return {}
        entities: dict[str, dict[str, Any]] = {}
        for offset in range(0, len(qids), 50):
            payload = self._request_json(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(qids[offset : offset + 50]),
                    "props": "labels|descriptions|claims|sitelinks",
                    "languages": "en|zh|zh-hans|zh-hant|ja|ko|fr|de|it|es",
                    "languagefallback": 1,
                    "format": "json",
                }
            )
            batch = payload.get("entities", {})
            if not isinstance(batch, dict):
                raise DiscoveryProviderError("Wikidata returned an unexpected response.")
            entities.update(batch)

        related_ids: set[str] = set()
        for entity in entities.values():
            claims = entity.get("claims", {})
            for property_id in (
                "P57", "P58", "P161", "P162", "P344", "P1040", "P136", "P495", "P166"
            ):
                related_ids.update(self._entity_ids(claims, property_id))
        labels = self._get_labels(sorted(related_ids))
        award_ids = {
            award_id
            for entity in entities.values()
            for award_id in self._entity_ids(entity.get("claims", {}), "P166")
        }
        award_descriptions = self._get_descriptions(sorted(award_ids))
        for entity in entities.values():
            entity["_related_labels"] = labels
            entity["_related_descriptions"] = award_descriptions
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

    def _get_descriptions(self, qids: list[str]) -> dict[str, str]:
        if not qids:
            return {}
        descriptions: dict[str, str] = {}
        for offset in range(0, len(qids), 50):
            payload = self._request_json(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(qids[offset : offset + 50]),
                    "props": "descriptions",
                    "languages": "en",
                    "languagefallback": 1,
                    "format": "json",
                }
            )
            for qid, entity in payload.get("entities", {}).items():
                description = self._best_text(entity.get("descriptions", {}))
                if description:
                    descriptions[qid] = description
        return descriptions

    def _normalise_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        qid = entity.get("id", "")
        claims = entity.get("claims", {})
        labels = entity.get("_related_labels", {})
        descriptions = entity.get("_related_descriptions", {})
        title = self._best_text(entity.get("labels", {})) or qid
        original_title = self._original_title(entity.get("labels", {}), title)
        alternative_titles = self._alternative_titles(entity.get("labels", {}), title)
        release_dates = self._time_values(claims, "P577")
        release_date = release_dates[0] if release_dates else None
        release_years = list(dict.fromkeys(self._year(value) for value in release_dates))
        release_years = [value for value in release_years if value is not None]
        description = self._best_text(entity.get("descriptions", {}))
        directors = self._labelled_claims(claims, "P57", labels)
        writers = self._labelled_claims(claims, "P58", labels)
        producers = self._labelled_claims(claims, "P162", labels)
        cinematographers = self._labelled_claims(claims, "P344", labels)
        editors = self._labelled_claims(claims, "P1040", labels)
        cast = self._labelled_claims(claims, "P161", labels)
        poster_name = self._string_value(claims, "P3383")
        imdb_id = self._string_value(claims, "P345")
        wikipedia_title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
        awards = self._significant_awards(claims, labels, descriptions)
        return {
            "id": f"wikidata:{qid}",
            "provider_id": qid,
            "title": title,
            "original_title": original_title,
            "alternative_titles": alternative_titles,
            "year": self._year(release_date),
            "release_years": release_years,
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
            "cast": cast,
            "poster_url": (
                f"{WIKIMEDIA_FILE_URL}/{quote(poster_name)}?width=500"
                if poster_name
                else None
            ),
            "poster_source": (
                {
                    "name": "Wikidata film poster",
                    "url": f"{WIKIDATA_ENTITY_URL}/{qid}",
                }
                if poster_name
                else None
            ),
            "backdrop_url": None,
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
                    "name": "Wikidata",
                    "url": f"{WIKIDATA_ENTITY_URL}/{qid}",
                    "licence": "CC0",
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
            "external_ids": {"imdb": imdb_id} if imdb_id else {},
            "awards": awards,
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
            "_director_ids": self._entity_ids(claims, "P57"),
            "_cast_ids": self._entity_ids(claims, "P161"),
            "_country_ids": self._entity_ids(claims, "P495"),
            "_genre_ids": self._entity_ids(claims, "P136"),
        }

    @classmethod
    def _significant_awards(
        cls,
        claims: dict[str, Any],
        labels: dict[str, str],
        descriptions: dict[str, str],
        limit: int = 3,
    ) -> list[dict[str, str]]:
        awards: list[dict[str, str]] = []
        for qid in cls._entity_ids(claims, "P166"):
            name = labels.get(qid)
            if not name:
                continue
            awards.append(
                {
                    "id": qid,
                    "name": name,
                    "description": descriptions.get(qid) or cls._award_introduction(name),
                    "url": f"{WIKIDATA_ENTITY_URL}/{qid}",
                }
            )
        awards.sort(key=lambda award: cls._award_significance(award["name"]), reverse=True)
        return awards[:limit]

    @staticmethod
    def _award_significance(name: str) -> int:
        folded = name.casefold()
        tiers = (
            (100, ("academy award", "palme d'or", "golden lion", "golden bear")),
            (90, ("grand prix", "bafta", "golden globe", "césar", "cesar")),
            (80, ("best picture", "best film", "best director", "jury prize")),
            (70, ("film festival", "international film", "critics'", "critics award")),
        )
        return next((score for score, terms in tiers if any(term in folded for term in terms)), 50)

    @staticmethod
    def _award_introduction(name: str) -> str:
        folded = name.casefold()
        if "palme d'or" in folded:
            return "The highest prize awarded in the Cannes Film Festival competition."
        if "academy award" in folded:
            return "An Academy of Motion Picture Arts and Sciences film honour."
        if "golden lion" in folded:
            return "The top competition prize at the Venice International Film Festival."
        if "golden bear" in folded:
            return "The highest prize in the Berlin International Film Festival competition."
        if "bafta" in folded:
            return "A film honour presented by the British Academy of Film and Television Arts."
        return f"A film honour recorded for the film: {name}."

    def _enrich_detail(self, film: dict[str, Any]) -> dict[str, Any]:
        wikipedia_title = film.pop("_wikipedia_title", None)
        wikipedia_url: str | None = None
        if wikipedia_title:
            wikipedia_url = f"https://en.wikipedia.org/wiki/{quote(str(wikipedia_title).replace(' ', '_'))}"
        self._discard_unverified_poster(film)
        poster_source = film.get("poster_source") or {}
        self._enrich_letterboxd_poster(
            film,
            replace_existing=poster_source.get("name") == "Wikipedia article image",
        )
        if wikipedia_title and self._wikipedia_summary:
            try:
                summary = self._wikipedia_summary(str(wikipedia_title))
            except DiscoveryProviderError:
                summary = {}
            self._apply_wikipedia_image(film, summary, wikipedia_url)
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
        if wikipedia_title and self._wikipedia_infobox:
            try:
                infobox = self._wikipedia_infobox(str(wikipedia_title))
            except DiscoveryProviderError:
                infobox = {}
            self._apply_wikipedia_infobox(film, infobox, wikipedia_url)
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
        film["evidence_notice"] = (
            "Wikidata establishes film identity; attributed Wikidata claims and Wikipedia "
            "infobox fields are reconciled for factual credits, not creator intentions or "
            "critical interpretation."
        )
        return film

    @staticmethod
    def _apply_wikipedia_infobox(
        film: dict[str, Any],
        payload: dict[str, Any],
        wikipedia_url: str | None,
    ) -> None:
        source_html = payload.get("parse", {}).get("text")
        if not isinstance(source_html, str) or not source_html:
            return
        parser = WikipediaInfoboxParser()
        parser.feed(source_html)
        mappings = {
            "directors": ("directed by",),
            "writers": ("written by", "screenplay by"),
            "producers": ("produced by",),
            "cinematographers": ("cinematography",),
            "editors": ("edited by",),
        }
        credits = {
            field: list(values)
            for field, values in (film.get("credits") or {}).items()
            if isinstance(values, list)
        }
        wikipedia_fields: list[str] = []
        for field, labels in mappings.items():
            values: list[str] = []
            for label in labels:
                values.extend(_infobox_people(parser.rows.get(label, "")))
            if not values:
                continue
            current = credits.setdefault(field, [])
            known = {DiscoveryService._normalise_identity(value) for value in current}
            for value in values:
                identity = DiscoveryService._normalise_identity(value)
                if identity and identity not in known:
                    current.append(value)
                    known.add(identity)
            wikipedia_fields.append(field)
        runtime = _infobox_runtime_minutes(parser.rows.get("running time", ""))
        if film.get("runtime_minutes") is None and runtime is not None:
            film["runtime_minutes"] = runtime
            wikipedia_fields.append("runtime_minutes")
        film["credits"] = credits
        film["directors"] = credits.get("directors") or film.get("directors") or []
        if wikipedia_fields:
            sources = list(film.get("crew_sources") or [])
            sources.append(
                {
                    "name": "Wikipedia infobox",
                    "url": wikipedia_url,
                    "licence": "CC BY-SA",
                    "fields": wikipedia_fields,
                }
            )
            film["crew_sources"] = sources

    def _enrich_poster(
        self,
        film: dict[str, Any],
        *,
        external_fallback: bool = False,
    ) -> None:
        self._discard_unverified_poster(film)
        if film.get("poster_url"):
            return
        if external_fallback:
            self._enrich_letterboxd_poster(film)
        if film.get("poster_url"):
            return
        wikipedia_title = film.get("_wikipedia_title")
        if wikipedia_title and self._wikipedia_summary:
            wikipedia_url = (
                f"https://en.wikipedia.org/wiki/"
                f"{quote(str(wikipedia_title).replace(' ', '_'))}"
            )
            try:
                summary = self._wikipedia_summary(str(wikipedia_title))
            except DiscoveryProviderError:
                summary = {}
            self._apply_wikipedia_image(film, summary, wikipedia_url)

    @staticmethod
    def _discard_unverified_poster(film: dict[str, Any]) -> None:
        """Remove legacy generic images that were cached before poster provenance existed."""
        if not film.get("poster_url"):
            return
        source = film.get("poster_source")
        if isinstance(source, dict) and str(source.get("name") or "").strip():
            return
        film["poster_url"] = None
        film["poster_source"] = None

    def _enrich_letterboxd_poster(
        self,
        film: dict[str, Any],
        *,
        replace_existing: bool = False,
    ) -> None:
        if film.get("poster_url") and not replace_existing:
            return

        imdb_id = str(film.get("external_ids", {}).get("imdb") or "").strip()
        poster: dict[str, Any] | None = None
        if self._poster_request and imdb_id:
            try:
                poster = self._poster_request(imdb_id)
            except DiscoveryProviderError:
                poster = None
        if poster and not str(poster.get("image") or "").startswith(
            "https://a.ltrbxd.com/resized/film-poster/"
        ):
            poster = None

        title = str(film.get("title") or "").strip()
        year = film.get("year") if isinstance(film.get("year"), int) else None
        directors = film.get("directors") or []
        director = str(directors[0] if directors else "").strip()
        if not poster and self._identity_poster_request and title and director:
            try:
                candidate = self._identity_poster_request(title, year, director)
            except DiscoveryProviderError:
                candidate = None
            if candidate and self._letterboxd_identity_matches(
                candidate,
                title=title,
                year=year,
                director=director,
            ):
                poster = candidate

        if not poster:
            return
        source = str(poster.get("image") or "").strip()
        if not source.startswith("https://a.ltrbxd.com/resized/film-poster/"):
            return
        film["poster_url"] = source
        runtime = poster.get("runtime_minutes")
        if film.get("runtime_minutes") is None and isinstance(runtime, int) and runtime > 0:
            film["runtime_minutes"] = runtime
        film["poster_source"] = {
            "name": "Letterboxd public film page",
            "url": poster.get("url")
            or (f"{LETTERBOXD_WEB}/imdb/{quote(imdb_id)}/" if imdb_id else LETTERBOXD_WEB),
        }

    @classmethod
    def _letterboxd_identity_matches(
        cls,
        poster: dict[str, Any],
        *,
        title: str,
        year: int | None,
        director: str,
    ) -> bool:
        candidate_title = str(poster.get("title") or "").strip()
        candidate_year = poster.get("year")
        candidate_directors = poster.get("directors") or []
        if not candidate_title or year is None or candidate_year != year:
            return False
        expected_director = cls._normalise_identity(director)
        if not expected_director or not any(
            cls._normalise_identity(str(name)) == expected_director
            for name in candidate_directors
        ):
            return False

        def title_words(value: str) -> list[str]:
            ascii_value = unicodedata.normalize("NFKD", value).encode(
                "ascii", "ignore"
            ).decode("ascii")
            return [
                word
                for word in re.findall(r"[a-z0-9]+", ascii_value.casefold())
                if word not in {"a", "an", "the"}
            ]

        expected_title = "".join(title_words(title))
        actual_title = "".join(title_words(candidate_title))
        return bool(
            expected_title
            and actual_title
            and (
                expected_title == actual_title
                or SequenceMatcher(None, expected_title, actual_title).ratio() >= 0.94
            )
        )

    @staticmethod
    def _apply_wikipedia_image(
        film: dict[str, Any],
        summary: dict[str, Any],
        wikipedia_url: str | None,
    ) -> None:
        if film.get("poster_url"):
            return
        image = summary.get("originalimage") or summary.get("thumbnail")
        if not isinstance(image, dict):
            return
        source = str(image.get("source") or "").strip()
        width = image.get("width")
        height = image.get("height")
        if not source.startswith("https://upload.wikimedia.org/"):
            return
        if isinstance(width, (int, float)) and isinstance(height, (int, float)):
            if width <= 0 or height / width < 1.12:
                return
        film["poster_url"] = source
        film["poster_source"] = {
            "name": "Wikipedia article image",
            "url": summary.get("content_urls", {}).get("desktop", {}).get("page")
            or wikipedia_url,
        }

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

    def _demo_related(
        self,
        film_id: str,
        limit: int,
        *,
        director_only: bool = False,
    ) -> dict[str, Any]:
        film = next((item for item in DEMO_FILMS if item["id"] == film_id), None)
        if not film:
            raise LookupError("Film not found in the offline catalogue.")
        directors = set(film.get("directors") or [])
        genres = set(film.get("genres") or [])
        same_director = [
            {**self._public_demo_summary(item), "relation": "same_director"}
            for item in DEMO_FILMS
            if item["id"] != film_id and directors.intersection(item.get("directors") or [])
        ][:limit]
        same_director_ids = {item["id"] for item in same_director}
        relevant = [
            {**self._public_demo_summary(item), "relation": "shared_genre"}
            for item in DEMO_FILMS
            if item["id"] != film_id
            and item["id"] not in same_director_ids
            and genres.intersection(item.get("genres") or [])
        ][:limit]
        return {
            "film_id": film_id,
            "director": next(iter(directors), None),
            "same_director": same_director,
            "shared_cast": [],
            "same_country": [] if director_only else relevant,
            "recommended": [] if director_only else relevant,
            "relevant": [] if director_only else relevant,
            "category_labels": {
                "cast": [],
                "countries": (film.get("countries") or [])[:3],
            },
            "state": "offline",
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
    def _wikidata_sparql_request(query: str) -> dict[str, Any]:
        url = f"{WIKIDATA_SPARQL}?{urlencode({'query': query, 'format': 'json'})}"
        request = Request(
            url,
            headers={
                "Accept": "application/sparql-results+json",
                "User-Agent": "FirstRoll/0.1 (https://github.com/Luo-Z-Y/FirstRoll)",
            },
        )
        try:
            with urlopen(request, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise DiscoveryProviderError(
                f"Wikidata Query Service returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DiscoveryProviderError("Wikidata Query Service could not be reached.") from exc

    @staticmethod
    def _wikipedia_search_request(params: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{WIKIPEDIA_API}?{urlencode(params)}",
            headers={
                "Accept": "application/json",
                "User-Agent": "FirstRoll/0.1 (https://github.com/Luo-Z-Y/FirstRoll)",
            },
        )
        try:
            with urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise DiscoveryProviderError(f"Wikipedia returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DiscoveryProviderError("Wikipedia could not be reached.") from exc

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
    def _wikipedia_infobox_request(title: str) -> dict[str, Any]:
        params = urlencode(
            {
                "action": "parse",
                "page": title,
                "prop": "text",
                "format": "json",
                "formatversion": "2",
            }
        )
        request = Request(
            f"{WIKIPEDIA_API}?{params}",
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
    def _letterboxd_poster_request(imdb_id: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"tt\d+", imdb_id):
            return None
        request = Request(
            f"{LETTERBOXD_WEB}/imdb/{quote(imdb_id)}/",
            headers={
                "Accept": "text/html",
                "User-Agent": "FirstRoll/0.1 (https://github.com/Luo-Z-Y/FirstRoll)",
            },
        )
        try:
            with urlopen(request, timeout=8) as response:
                page_url = response.geturl()
                page = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise DiscoveryProviderError(f"Letterboxd returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError) as exc:
            raise DiscoveryProviderError("Letterboxd could not be reached.") from exc
        return DiscoveryService._parse_letterboxd_poster(page, page_url)

    @classmethod
    def _letterboxd_identity_poster_request(
        cls,
        title: str,
        year: int | None,
        director: str,
    ) -> dict[str, Any] | None:
        ascii_title = unicodedata.normalize("NFKD", title).encode(
            "ascii", "ignore"
        ).decode("ascii")
        base_slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.casefold()).strip("-")
        if not base_slug or year is None or not director:
            return None
        slugs = [base_slug]
        for original, replacement in (("-and-the-", "-and-"), ("-of-the-", "-of-")):
            variant = base_slug.replace(original, replacement)
            if variant not in slugs:
                slugs.append(variant)
        for slug in list(slugs):
            dated = f"{slug}-{year}"
            if dated not in slugs:
                slugs.append(dated)

        for slug in slugs[:4]:
            request = Request(
                f"{LETTERBOXD_WEB}/film/{quote(slug, safe='-')}/",
                headers={
                    "Accept": "text/html",
                    "User-Agent": "FirstRoll/0.1 (https://github.com/Luo-Z-Y/FirstRoll)",
                },
            )
            try:
                with urlopen(request, timeout=8) as response:
                    page_url = response.geturl()
                    page = response.read().decode("utf-8", errors="replace")
            except HTTPError as exc:
                if exc.code == 404:
                    continue
                raise DiscoveryProviderError(
                    f"Letterboxd returned HTTP {exc.code}."
                ) from exc
            except (URLError, TimeoutError) as exc:
                raise DiscoveryProviderError("Letterboxd could not be reached.") from exc
            poster = cls._parse_letterboxd_poster(page, page_url)
            if poster and cls._letterboxd_identity_matches(
                poster,
                title=title,
                year=year,
                director=director,
            ):
                return poster
        return None

    @staticmethod
    def _parse_letterboxd_poster(page: str, page_url: str) -> dict[str, Any] | None:
        scripts = re.findall(
            r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
            page,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for script in scripts:
            raw = html.unescape(script).strip()
            raw = re.sub(r"^/\*.*?\*/\s*", "", raw, flags=re.DOTALL)
            raw = re.sub(r"\s*/\*.*?\*/$", "", raw, flags=re.DOTALL)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or payload.get("@type") != "Movie":
                continue
            image = str(payload.get("image") or "").strip()
            if image.startswith("https://a.ltrbxd.com/resized/film-poster/"):
                result: dict[str, Any] = {
                    "image": image,
                    "url": str(payload.get("url") or page_url),
                }
                title = str(payload.get("name") or "").strip()
                if title:
                    result["title"] = title
                published = str(
                    payload.get("dateCreated") or payload.get("datePublished") or ""
                )
                if published_year := re.match(r"(\d{4})", published):
                    result["year"] = int(published_year.group(1))
                raw_directors = payload.get("director") or []
                if isinstance(raw_directors, dict):
                    raw_directors = [raw_directors]
                directors = [
                    str(person.get("name") or "").strip()
                    for person in raw_directors
                    if isinstance(person, dict) and str(person.get("name") or "").strip()
                ]
                if directors:
                    result["directors"] = directors
                duration = re.fullmatch(
                    r"PT(?:(\d+)H)?(?:(\d+)M)?",
                    str(payload.get("duration") or ""),
                )
                if duration:
                    result["runtime_minutes"] = (
                        int(duration.group(1) or 0) * 60 + int(duration.group(2) or 0)
                    )
                return result
        return None

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
    def _sparql_entity_ids(payload: dict[str, Any], variable: str) -> list[str]:
        values: list[str] = []
        bindings = payload.get("results", {}).get("bindings", [])
        if not isinstance(bindings, list):
            return values
        for binding in bindings:
            raw = binding.get(variable, {}).get("value") if isinstance(binding, dict) else None
            qid = str(raw or "").rsplit("/", 1)[-1]
            if DiscoveryService._valid_qid(qid) and qid not in values:
                values.append(qid)
        return values

    @staticmethod
    def _labelled_claims(
        claims: dict[str, Any],
        property_id: str,
        labels: dict[str, str],
    ) -> list[str]:
        return [
            labels[qid]
            for qid in DiscoveryService._entity_ids(claims, property_id)
            if labels.get(qid)
        ]

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
    def _alternative_titles(labels: dict[str, Any], title: str) -> list[str]:
        """Retain multilingual identity labels for provider-specific exact-title searches."""
        values: list[str] = []
        seen = {DiscoveryService._normalise_identity(title)}
        for language in ("zh-hans", "zh-hant", "zh", "ko", "ja", "en"):
            value = str(labels.get(language, {}).get("value") or "").strip()
            identity = DiscoveryService._normalise_identity(value)
            if value and identity and identity not in seen:
                values.append(value)
                seen.add(identity)
        return values

    @staticmethod
    def _time_value(claims: dict[str, Any], property_id: str) -> str | None:
        values = DiscoveryService._time_values(claims, property_id)
        return values[0] if values else None

    @staticmethod
    def _time_values(claims: dict[str, Any], property_id: str) -> list[str]:
        values: list[str] = []
        for claim in claims.get(property_id, []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            raw = value.get("time") if isinstance(value, dict) else None
            if isinstance(raw, str) and len(raw) >= 11:
                date_value = raw[1:11]
                if date_value not in values:
                    values.append(date_value)
        return values

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
                "alternative_titles",
                "year",
                "release_years",
                "matched_year",
                "runtime_minutes",
                "directors",
                "overview",
                "poster_url",
                "poster_source",
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
            "runtime_minutes": film["runtime_minutes"],
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
    def _wikipedia_status() -> SourceStatus:
        return SourceStatus(
            name="Wikipedia",
            kind="attributed_overview_and_crew_enrichment",
            state="ready",
            message="Article overview, poster and infobox crew fields after identity resolution.",
        )

    @staticmethod
    def _demo_status() -> SourceStatus:
        return SourceStatus(
            name="Curated offline catalogue",
            kind="local_demo_metadata",
            state="offline",
            message="Bundled fallback records are available when Wikidata cannot be reached.",
        )
