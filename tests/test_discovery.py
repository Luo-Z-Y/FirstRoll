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
                    "P2047": [claim_quantity("101")],
                    "P345": [claim_string("tt1234567")],
                },
            }
        }
    }


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
