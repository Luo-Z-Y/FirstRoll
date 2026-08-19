from typing import Any

from app.backend.discovery import DiscoveryProviderError, DiscoveryService


def fake_wikidata(params: dict[str, Any]) -> dict[str, Any]:
    if params["action"] == "wbsearchentities":
        return {"search": [{"id": "Q100"}]}
    if params["action"] == "wbgetentities" and params["props"] == "labels":
        return {
            "entities": {
                "Q200": {"id": "Q200", "labels": {"en": {"value": "Example Director"}}},
                "Q300": {"id": "Q300", "labels": {"en": {"value": "Drama"}}},
                "Q400": {"id": "Q400", "labels": {"en": {"value": "Singapore"}}},
                "Q500": {"id": "Q500", "labels": {"en": {"value": "Example Actor"}}},
            }
        }
    return {
        "entities": {
            "Q100": {
                "id": "Q100",
                "labels": {"en": {"value": "Example Film"}},
                "descriptions": {"en": {"value": "2024 film"}},
                "sitelinks": {"enwiki": {"title": "Example Film"}},
                "claims": {
                    "P57": [claim_entity("Q200")],
                    "P577": [claim_time("+2024-05-01T00:00:00Z")],
                    "P136": [claim_entity("Q300")],
                    "P495": [claim_entity("Q400")],
                    "P161": [claim_entity("Q500")],
                    "P2047": [claim_quantity("101")],
                    "P345": [claim_string("tt1234567")],
                },
            }
        }
    }


def fake_wikidata_with_related(params: dict[str, Any]) -> dict[str, Any]:
    requested_ids = set(str(params.get("ids") or "").split("|"))
    related_ids = requested_ids.intersection({"Q101", "Q102", "Q103", "Q104"})
    if params.get("action") == "wbgetentities" and related_ids and params.get("props") != "labels":
        definitions = {
            "Q101": (
                "Earlier Example",
                {
                    "P57": [claim_entity("Q200")],
                    "P345": [claim_string("tt7654321")],
                },
            ),
            "Q102": ("Actor Reunion", {"P161": [claim_entity("Q500")]}),
            "Q103": ("Singapore Story", {"P495": [claim_entity("Q400")]}),
            "Q104": ("Another Drama", {"P136": [claim_entity("Q300")]}),
        }
        return {
            "entities": {
                qid: {
                    "id": qid,
                    "labels": {"en": {"value": definitions[qid][0]}},
                    "descriptions": {"en": {"value": "2020 drama film"}},
                    "claims": {
                        **definitions[qid][1],
                        "P577": [claim_time(f"+20{20 + int(qid[-1]):02d}-02-01T00:00:00Z")],
                        "P136": [claim_entity("Q300")],
                    },
                }
                for qid in related_ids
            }
        }
    return fake_wikidata(params)


def claim_entity(qid: str) -> dict[str, Any]:
    return {"mainsnak": {"datavalue": {"value": {"id": qid}}}}


def claim_time(value: str) -> dict[str, Any]:
    return {"mainsnak": {"datavalue": {"value": {"time": value}}}}


def claim_quantity(amount: str) -> dict[str, Any]:
    return {
        "mainsnak": {
            "datavalue": {
                "value": {
                    "amount": amount,
                    "unit": "http://www.wikidata.org/entity/Q7727",
                }
            }
        }
    }


def claim_string(value: str) -> dict[str, Any]:
    return {"mainsnak": {"datavalue": {"value": value}}}


def unavailable(_: dict[str, Any]) -> dict[str, Any]:
    raise DiscoveryProviderError("offline")


def test_wikidata_search_matches_title_year_and_director_without_api_key() -> None:
    service = DiscoveryService(request_json=fake_wikidata)

    result = service.search("Example Film", year=2024, director="Example")

    assert result["mode"] == "live"
    assert result["result_count"] == 1
    assert result["results"][0]["id"] == "wikidata:Q100"
    assert result["results"][0]["directors"] == ["Example Director"]
    assert result["results"][0]["runtime_minutes"] == 101


def test_related_films_are_resolved_from_the_verified_director_identity() -> None:
    service = DiscoveryService(
        request_json=fake_wikidata_with_related,
        sparql_json=lambda _: {
            "results": {
                "bindings": [
                    {"film": {"value": "http://www.wikidata.org/entity/Q101"}},
                ]
            }
        },
    )
    service.search("Example Film")

    result = service.related("wikidata:Q100")

    assert result["director"] == "Example Director"
    assert result["state"] == "ready"
    assert [film["title"] for film in result["same_director"]] == ["Earlier Example"]
    assert result["same_director"][0]["relation"] == "same_director"
    assert "_director_ids" not in service.detail("wikidata:Q100")["film"]


def test_related_films_use_a_bounded_public_poster_fallback() -> None:
    requested_imdb_ids: list[str] = []

    def poster_request(imdb_id: str) -> dict[str, str]:
        requested_imdb_ids.append(imdb_id)
        return {
            "image": (
                "https://a.ltrbxd.com/resized/film-poster/7/6/5/"
                "7654321-earlier-example-0-600-0-900-crop.jpg"
            ),
            "url": f"https://letterboxd.com/imdb/{imdb_id}/",
        }

    service = DiscoveryService(
        request_json=fake_wikidata_with_related,
        sparql_json=lambda _: {
            "results": {
                "bindings": [sparql_relation("Q101", "same_director", "Q200")]
            }
        },
        poster_request=poster_request,
    )
    service.search("Example Film")
    requested_imdb_ids.clear()

    result = service.related("wikidata:Q100")

    assert requested_imdb_ids == ["tt7654321"]
    assert "/resized/film-poster/" in result["same_director"][0]["poster_url"]
    assert result["same_director"][0]["poster_source"]["name"] == (
        "Letterboxd public film page"
    )


def test_related_films_are_grouped_by_cast_country_and_genre() -> None:
    service = DiscoveryService(
        request_json=fake_wikidata_with_related,
        sparql_json=lambda _: {
            "results": {
                "bindings": [
                    sparql_relation("Q101", "same_director", "Q200"),
                    sparql_relation("Q102", "shared_cast", "Q500"),
                    sparql_relation("Q103", "same_country", "Q400"),
                    sparql_relation("Q104", "shared_genre", "Q300"),
                ]
            }
        },
    )
    service.search("Example Film")

    result = service.related("wikidata:Q100")

    assert [film["title"] for film in result["same_director"]] == ["Earlier Example"]
    assert result["shared_cast"][0]["relation_label"] == "Example Actor"
    assert result["same_country"][0]["relation_label"] == "Singapore"
    assert result["recommended"][0]["relation"] == "shared_genre"
    assert result["category_labels"] == {
        "cast": ["Example Actor"],
        "countries": ["Singapore"],
    }


def test_fast_related_films_skip_secondary_enrichment_and_are_cached() -> None:
    entity_requests: list[dict[str, Any]] = []
    poster_requests: list[str] = []

    def tracked_request(params: dict[str, Any]) -> dict[str, Any]:
        entity_requests.append(params)
        return fake_wikidata_with_related(params)

    service = DiscoveryService(
        request_json=tracked_request,
        sparql_json=lambda _: {
            "results": {
                "bindings": [sparql_relation("Q101", "same_director", "Q200")]
            }
        },
        poster_request=lambda imdb_id: poster_requests.append(imdb_id) or None,
    )
    service.search("Example Film")
    entity_requests.clear()
    poster_requests.clear()

    first = service.related("wikidata:Q100", limit=12, fast=True)
    requests_after_first = len(entity_requests)
    second = service.related("wikidata:Q100", limit=12, fast=True)

    assert first is second
    assert requests_after_first == 1
    assert len(entity_requests) == requests_after_first
    assert poster_requests == []
    assert first["same_director"][0]["directors"] == ["Example Director"]
    assert "Q101" not in service._detail_cache


def sparql_relation(film: str, relation: str, shared: str) -> dict[str, dict[str, str]]:
    return {
        "film": {"value": f"http://www.wikidata.org/entity/{film}"},
        "relation": {"value": relation},
        "shared": {"value": f"http://www.wikidata.org/entity/{shared}"},
    }


def test_search_uses_portrait_wikipedia_image_when_wikidata_has_no_poster() -> None:
    service = DiscoveryService(
        request_json=fake_wikidata,
        wikipedia_summary=lambda _: {
            "originalimage": {
                "source": "https://upload.wikimedia.org/wikipedia/en/a/ab/Example.jpg",
                "width": 265,
                "height": 376,
            },
            "content_urls": {
                "desktop": {"page": "https://en.wikipedia.org/wiki/Example_Film"}
            },
        },
    )

    result = service.search("Example Film", year=2024)

    assert result["results"][0]["poster_url"].endswith("/Example.jpg")
    assert result["results"][0]["poster_source"]["name"] == "Wikipedia article image"


def test_search_falls_back_to_public_letterboxd_poster_by_imdb_identity() -> None:
    service = DiscoveryService(
        request_json=fake_wikidata,
        wikipedia_summary=lambda _: {
            "originalimage": {
                "source": "https://upload.wikimedia.org/example-landscape.jpg",
                "width": 1200,
                "height": 675,
            }
        },
        poster_request=lambda imdb_id: {
            "image": (
                "https://a.ltrbxd.com/resized/film-poster/1/2/3/"
                "123-example-film-0-600-0-900-crop.jpg"
            ),
            "url": f"https://letterboxd.com/imdb/{imdb_id}/",
            "runtime_minutes": 157,
        },
    )

    result = service.search("Example Film", year=2024)

    poster = result["results"][0]
    assert "/resized/film-poster/" in poster["poster_url"]
    assert poster["poster_source"]["name"] == "Letterboxd public film page"
    assert poster["runtime_minutes"] == 101  # Wikidata remains authoritative when supplied.

    missing_runtime = {
        "poster_url": None,
        "runtime_minutes": None,
        "external_ids": {"imdb": "tt1234567"},
    }
    service._enrich_letterboxd_poster(missing_runtime)
    assert missing_runtime["runtime_minutes"] == 157


def test_letterboxd_poster_parser_uses_movie_json_ld_image() -> None:
    page = """
    <script type="application/ld+json">
      {"@type":"Movie","name":"Example Film",
       "image":"https://a.ltrbxd.com/resized/film-poster/1/example.jpg",
       "url":"https://letterboxd.com/film/example-film/","duration":"PT2H37M"}
    </script>
    """

    result = DiscoveryService._parse_letterboxd_poster(
        page,
        "https://letterboxd.com/imdb/tt1234567/",
    )

    assert result == {
        "image": "https://a.ltrbxd.com/resized/film-poster/1/example.jpg",
        "url": "https://letterboxd.com/film/example-film/",
        "runtime_minutes": 157,
    }


def test_wikidata_detail_keeps_intention_claims_out_of_identity_metadata() -> None:
    service = DiscoveryService(
        request_json=fake_wikidata,
        wikipedia_summary=lambda _: {
            "extract": "Example Film is a fictional film used for testing.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Example_Film"}},
        },
    )
    service.search("Example Film")

    result = service.detail("wikidata:Q100")

    assert result["film"]["source"]["name"] == "Wikidata"
    assert result["film"]["source"]["licence"] == "CC0"
    assert result["film"]["reviews"] == []
    assert result["film"]["runtime_minutes"] == 101
    assert result["film"]["overview"].startswith("Example Film is")
    assert result["film"]["overview_source"]["name"] == "Wikipedia"
    assert len(result["film"]["research_links"]) >= 4
    assert len(result["film"]["study_questions"]) >= 3
    assert "not creator intentions" in result["film"]["evidence_notice"].casefold()


def test_significant_awards_prioritise_major_prizes_and_limit_to_three() -> None:
    claims = {
        "P166": [
            claim_entity("Q1"),
            claim_entity("Q2"),
            claim_entity("Q3"),
            claim_entity("Q4"),
        ]
    }
    labels = {
        "Q1": "Regional audience mention",
        "Q2": "Palme d'Or",
        "Q3": "Academy Award for Best Picture",
        "Q4": "International Film Festival jury prize",
    }

    awards = DiscoveryService._significant_awards(claims, labels, {})

    assert [award["name"] for award in awards] == [
        "Palme d'Or",
        "Academy Award for Best Picture",
        "International Film Festival jury prize",
    ]
    assert "Cannes" in awards[0]["description"]


def test_wikipedia_infobox_completes_missing_crew_with_field_provenance() -> None:
    infobox_html = """
    <table class="infobox vevent"><tbody>
      <tr><th class="infobox-label">Directed by</th><td class="infobox-data">Example Director</td></tr>
      <tr><th class="infobox-label">Written by</th><td class="infobox-data">Example Writer</td></tr>
      <tr><th class="infobox-label">Produced by</th><td class="infobox-data">Example Producer</td></tr>
      <tr><th class="infobox-label">Cinematography</th><td class="infobox-data">Example DP</td></tr>
      <tr><th class="infobox-label">Edited by</th><td class="infobox-data"><ul><li>Editor One</li><li>Editor Two</li></ul></td></tr>
      <tr><th class="infobox-label">Running time</th><td class="infobox-data">2h 37m</td></tr>
    </tbody></table>
    """
    service = DiscoveryService(
        request_json=fake_wikidata,
        wikipedia_summary=lambda _: {
            "extract": "Example Film is a fictional film used for testing.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Example_Film"}},
        },
        wikipedia_infobox=lambda _: {"parse": {"text": infobox_html}},
    )

    result = service.detail("wikidata:Q100")
    film = result["film"]

    assert film["credits"]["directors"] == ["Example Director"]
    assert film["credits"]["writers"] == ["Example Writer"]
    assert film["credits"]["producers"] == ["Example Producer"]
    assert film["credits"]["cinematographers"] == ["Example DP"]
    assert film["credits"]["editors"] == ["Editor One", "Editor Two"]
    assert film["runtime_minutes"] == 101  # Existing Wikidata value is not silently replaced.
    assert film["crew_sources"][-1]["name"] == "Wikipedia infobox"
    assert "cinematographers" in film["crew_sources"][-1]["fields"]
    assert [source["name"] for source in result["sources"]] == ["Wikidata", "Wikipedia"]


def test_wikipedia_infobox_discards_css_and_malformed_crew_values() -> None:
    infobox_html = """
    <table class="infobox vevent"><tbody>
      <tr><th class="infobox-label">Produced by</th><td class="infobox-data">
        <style>.mw-parser-output .plainlist ol,.mw-parser-output .plainlist ul{line-height:inherit;list-style:none;margin:0;padding:0}</style>
        <div class="plainlist"><ul><li>Kim Se-hun</li><li>Jenna Ku</li></ul></div>
      </td></tr>
      <tr><th class="infobox-label">Edited by</th><td class="infobox-data">
        margin:0,padding:0{}.mw-parser-output
      </td></tr>
    </tbody></table>
    """
    service = DiscoveryService(
        request_json=fake_wikidata,
        wikipedia_summary=lambda _: {},
        wikipedia_infobox=lambda _: {"parse": {"text": infobox_html}},
    )

    film = service.detail("wikidata:Q100")["film"]

    assert film["credits"]["producers"] == ["Kim Se-hun", "Jenna Ku"]
    assert film["credits"].get("editors", []) == []
    assert all("mw-parser-output" not in name for name in film["credits"]["producers"])


def test_offline_catalogue_is_used_when_wikidata_is_unavailable() -> None:
    service = DiscoveryService(request_json=unavailable)

    result = service.search("In the Mood for Love", year=2000, director="Wong")

    assert result["mode"] == "degraded"
    assert result["result_count"] == 1
    assert result["results"][0]["title"] == "In the Mood for Love"
    assert result["sources"][0]["state"] == "unavailable"


def test_search_returns_empty_for_wrong_identity() -> None:
    service = DiscoveryService(request_json=fake_wikidata)

    result = service.search("Example Film", year=1972)

    assert result["results"] == []


def test_wikipedia_search_supplements_lagging_wikidata_title_index() -> None:
    def request(params: dict[str, Any]) -> dict[str, Any]:
        if params["action"] == "wbsearchentities":
            return {"search": [{"id": "Q2002001"}]}
        ids = str(params.get("ids") or "").split("|")
        if params.get("props") == "labels":
            labels = {
                "QOLD_DIRECTOR": "Brian De Palma",
                "QNEW_DIRECTOR": "Curry Barker",
            }
            return {
                "entities": {
                    qid: {"id": qid, "labels": {"en": {"value": labels[qid]}}}
                    for qid in ids
                    if qid in labels
                }
            }
        definitions = {
            "Q2002001": ("1976 film by Brian De Palma", "QOLD_DIRECTOR", [1976]),
            "Q136163067": ("2025 film directed by Curry Barker", "QNEW_DIRECTOR", [2025, 2026]),
        }
        return {
            "entities": {
                qid: {
                    "id": qid,
                    "labels": {"en": {"value": "Obsession"}},
                    "descriptions": {"en": {"value": definitions[qid][0]}},
                    "claims": {
                        "P57": [claim_entity(definitions[qid][1])],
                        "P577": [
                            claim_time(f"+{release_year}-05-15T00:00:00Z")
                            for release_year in definitions[qid][2]
                        ],
                    },
                    "sitelinks": {},
                }
                for qid in ids
                if qid in definitions
            }
        }

    wikipedia_result = {
        "query": {
            "pages": [
                {
                    "index": 1,
                    "title": "Obsession (2025 film)",
                    "pageprops": {"wikibase_item": "Q136163067"},
                }
            ]
        }
    }
    service = DiscoveryService(
        request_json=request,
        wikipedia_search=lambda _: wikipedia_result,
    )

    result = service.search("Obsession")

    assert [film["provider_id"] for film in result["results"]] == [
        "Q2002001",
        "Q136163067",
    ]
    assert result["results"][1]["release_years"] == [2025, 2026]


def test_year_filter_accepts_a_later_recorded_release_year() -> None:
    def request(params: dict[str, Any]) -> dict[str, Any]:
        if params["action"] == "wbsearchentities":
            return {"search": []}
        ids = str(params.get("ids") or "").split("|")
        if params.get("props") == "labels":
            return {
                "entities": {
                    "QNEW_DIRECTOR": {
                        "id": "QNEW_DIRECTOR",
                        "labels": {"en": {"value": "Curry Barker"}},
                    }
                }
            }
        return {
            "entities": {
                "Q136163067": {
                    "id": "Q136163067",
                    "labels": {"en": {"value": "Obsession"}},
                    "descriptions": {
                        "en": {"value": "2025 film directed by Curry Barker"}
                    },
                    "claims": {
                        "P57": [claim_entity("QNEW_DIRECTOR")],
                        "P577": [
                            claim_time("+2025-09-05T00:00:00Z"),
                            claim_time("+2026-05-15T00:00:00Z"),
                        ],
                    },
                    "sitelinks": {},
                }
            }
            if "Q136163067" in ids
            else {},
        }

    service = DiscoveryService(
        request_json=request,
        wikipedia_search=lambda _: {
            "query": {
                "pages": [
                    {"index": 1, "pageprops": {"wikibase_item": "Q136163067"}}
                ]
            }
        },
    )

    result = service.search("Obsession", year=2026)

    assert result["result_count"] == 1
    assert result["results"][0]["matched_year"] == 2026
    assert result["results"][0]["release_years"] == [2025, 2026]
