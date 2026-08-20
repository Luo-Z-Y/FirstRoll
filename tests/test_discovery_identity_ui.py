from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def test_ambiguous_search_requires_explicit_film_identity_confirmation() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert "films.length > 1" in app
    assert 'refs.resultsTitle.textContent = "Which film did you mean?"' in app
    assert 'data-confirm-film-index="${index}"' in app
    assert "Check the year, filmmaker and original title" in app
    assert "confirmDiscoveryFilm(Number(identityChoice.dataset.confirmFilmIndex))" in app
    assert "renderFilmArchive(primary, [], nearby, true)" in app
    assert "loadRelatedFilms(primary, nearby)" in app
    assert "function filmYearLabel(film)" in app
    assert '`${matchedYear} release · first release ${years[0]}`' in app
    assert ".identity-choice-grid" in styles
    assert ".identity-choice:focus-visible" in styles
