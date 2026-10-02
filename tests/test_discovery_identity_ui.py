from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def test_ambiguous_search_requires_explicit_film_identity_confirmation(application_source: str) -> None:
    app = application_source
    formatting = (WEB / "src" / "shared" / "format.ts").read_text(encoding="utf-8")
    views = (WEB / "src" / "discovery" / "views.ts").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert "films.length > 1" in app
    assert 'refs.resultsTitle.textContent = "Which film did you mean?"' in app
    assert 'from "../discovery/views"' in app
    assert 'data-confirm-film-index="${index}"' in views
    assert "Check the year, filmmaker and original title" in views
    assert "confirmDiscoveryFilm(Number(identityChoice.dataset.confirmFilmIndex))" in app
    assert "renderFilmArchive(primary, [], nearby, true)" in app
    assert "loadRelatedFilms(primary, nearby)" in app
    assert 'from "../shared/format"' in app
    assert "export function filmYearLabel(" in formatting
    assert "export function normaliseFilmYear(" in formatting
    assert 'value === null || value === undefined || value === ""' in formatting
    assert "year >= 1888 && year <= 2100" in formatting
    assert 'return years[0] ? String(years[0]) : "Year unknown"' in formatting
    assert "release · first release" not in app
    assert 'years.join(" / ")' not in formatting
    assert ".identity-choice-grid" in styles
    assert ".identity-choice:focus-visible" in styles


def test_raw_wikidata_ids_are_not_presented_as_people(application_source: str) -> None:
    app = application_source
    crew = (WEB / "src" / "shared" / "crew.ts").read_text(encoding="utf-8")
    views = (WEB / "src" / "discovery" / "views.ts").read_text(encoding="utf-8")

    assert 'from "../shared/crew"' in app
    assert r'.filter((value) => !/^Q\d+$/i.test(value))' in crew
    assert 'displayCrew(primary.directors || [], "Director not supplied")' in views
