from __future__ import annotations

import html
import json
import re
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
        wikipedia_summary: WikipediaRequest | None = None,
        wikipedia_infobox: WikipediaRequest | None = None,
        sparql_json: SparqlRequest | None = None,
        poster_request: PosterRequest | None = None,
    ) -> None:
        self._request_json = request_json or self._wikidata_request
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
        self._detail_cache: dict[str, dict[str, Any]] = {}

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
        public_detail.pop("_director_ids", None)
        return {
            "film": self._enrich_detail(public_detail),
            "mode": "live",
            "sources": [self._wikidata_status().as_dict(), self._wikipedia_status().as_dict()],
        }

    def related(self, film_id: str, limit: int = 12) -> dict[str, Any]:
        """Return verified films by the primary director for the discovery closet."""
        limit = max(1, min(limit, 18))
        if film_id.startswith("demo:"):
            return self._demo_related(film_id, limit)

        qid = film_id.removeprefix("wikidata:")
        if not self._valid_qid(qid):
            raise LookupError("The film identifier is not recognised by the Wikidata adapter.")
        if qid not in self._detail_cache:
            self.detail(film_id)
        film = self._detail_cache.get(qid) or {}
        director_ids = film.get("_director_ids") or []
        director_names = film.get("directors") or []
        director = director_names[0] if director_names else None
        response = {
            "film_id": film_id,
            "director": director,
            "same_director": [],
            "state": "ready",
        }
        if not director_ids or self._sparql_json is None:
            response["state"] = "unavailable"
            return response

        director_id = director_ids[0]
        query = f"""
SELECT DISTINCT ?film WHERE {{
  ?film wdt:P57 wd:{director_id} .
  FILTER(?film != wd:{qid})
}}
LIMIT {limit * 3}
""".strip()
        try:
            payload = self._sparql_json(query)
            candidate_ids = self._sparql_entity_ids(payload, "film")
            entities = self._get_entities(candidate_ids[:50])
        except (DiscoveryProviderError, KeyError, TypeError, ValueError):
            response["state"] = "unavailable"
            return response

        related: list[dict[str, Any]] = []
        for candidate_id in candidate_ids:
            entity = entities.get(candidate_id)
            if not entity or not self._looks_like_film(entity):
                continue
            candidate = self._normalise_entity(entity)
            self._detail_cache[candidate_id] = candidate
            self._enrich_poster(candidate)
            summary = self._public_live_summary(candidate)
            summary["relation"] = "same_director"
            related.append(summary)
        related.sort(key=lambda item: (item.get("year") is None, -(item.get("year") or 0)))
        response["same_director"] = related[:limit]
        return response

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
            results.append(film)
        results.sort(key=lambda film: film["match_score"], reverse=True)
        for index, film in enumerate(results[:8]):
            self._enrich_poster(film, external_fallback=index == 0)
        return [self._public_live_summary(film) for film in results]

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
            for property_id in (
                "P57", "P58", "P162", "P344", "P1040", "P136", "P495", "P166"
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
        release_date = self._time_value(claims, "P577")
        description = self._best_text(entity.get("descriptions", {}))
        directors = self._labelled_claims(claims, "P57", labels)
        writers = self._labelled_claims(claims, "P58", labels)
        producers = self._labelled_claims(claims, "P162", labels)
        cinematographers = self._labelled_claims(claims, "P344", labels)
        editors = self._labelled_claims(claims, "P1040", labels)
        image_name = self._string_value(claims, "P18")
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
                "producers": producers,
                "cinematographers": cinematographers,
                "editors": editors,
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
        if not film.get("poster_url"):
            self._enrich_letterboxd_poster(film)

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
        if external_fallback and not film.get("poster_url"):
            self._enrich_letterboxd_poster(film)

    def _enrich_letterboxd_poster(self, film: dict[str, Any]) -> None:
        imdb_id = str(film.get("external_ids", {}).get("imdb") or "").strip()
        if film.get("poster_url") or not self._poster_request or not imdb_id:
            return
        try:
            poster = self._poster_request(imdb_id)
        except DiscoveryProviderError:
            return
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
            "url": poster.get("url") or f"{LETTERBOXD_WEB}/imdb/{quote(imdb_id)}/",
        }

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

    def _demo_related(self, film_id: str, limit: int) -> dict[str, Any]:
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
            "relevant": relevant,
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
                "alternative_titles",
                "year",
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
