import { displayCrew } from "../shared/crew";
import { directorShelfFilms } from "../discovery/films";
import { filmIdentityChoicesMarkup, filmArchiveMarkup, directorShelfFilmsMarkup } from "../discovery/views";
import { filmYearLabel } from "../shared/format";

// Discovery results and shelf DOM updates. Network requests are delegated.
// JavaScript controller: migrated module boundaries, not yet a fully typed domain model.
export function createShelf(context, services) {
  const { state, refs } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const normaliseDiscoveryQuery = (...args) => services.session.normaliseDiscoveryQuery(...args);
  const persistDiscoverySession = (...args) => services.session.persistDiscoverySession(...args);
  const confirmDiscoveryFilm = (...args) => services.discovery.confirmDiscoveryFilm(...args);
  const focusInterfaceState = (...args) => services.ui.focusInterfaceState(...args);

  function renderDiscoveryResults(data) {
    const films = Array.isArray(data.results) ? data.results : [];
    const query = normaliseDiscoveryQuery(data.query || state.discovery.lastQuery || {});
    state.discovery.results = films;
    state.discovery.lastQuery = query;
    refs.resultsTitle.textContent = films.length ? "Pulled from the shelf" : "Nothing on this shelf";
    refs.resultsMeta.textContent = [query.title, query.year, query.director].filter(Boolean).join(" / ");
    if (!films.length) {
      state.discovery.archive = null;
      state.discovery.archiveSelectionId = null;
      state.discovery.resultStage = "empty";
      state.discovery.shelfState = "idle";
      const hasFilters = Boolean(query.year || query.director);
      refs.discoveryResults.innerHTML = `
        <div class="interface-state" role="status" tabindex="-1" data-interface-state>
          <span>Identity check complete</span>
          <h3>No exact film matched.</h3>
          <p>${hasFilters ? "Keep the title and remove the optional year and director filters, or edit the query." : "Check the title spelling or try an original-language title."}</p>
          ${hasFilters ? '<button type="button" data-relax-discovery-filters>Search by title only</button>' : '<button type="button" data-edit-discovery-query>Edit the title</button>'}
        </div>`;
      persistDiscoverySession();
      focusInterfaceState(refs.discoveryResults);
      return;
    }

    if (films.length > 1) {
      state.discovery.archive = null;
      state.discovery.archiveSelectionId = null;
      state.discovery.resultStage = "choices";
      state.discovery.shelfState = "idle";
      refs.resultsTitle.textContent = "Which film did you mean?";
      refs.resultsMeta.textContent = `${films.length} possible matches`;
      refs.discoveryResults.innerHTML = filmIdentityChoicesMarkup(films);
      persistDiscoverySession();
      focusInterfaceState(refs.discoveryResults, "#identityConfirmationTitle");
      return;
    }

    confirmDiscoveryFilm(0);
  }

  function setArchiveHeading(primary) {
    refs.resultsTitle.textContent = "Pulled from the shelf";
    refs.resultsMeta.textContent = [
      primary.title,
      filmYearLabel(primary),
      displayCrew(primary.directors || [], ""),
    ].filter(Boolean).join(" / ");
  }

  function setDirectorShelfLoading(primaryId) {
    const shelf = refs.discoveryResults.querySelector("[data-director-shelf]");
    if (!shelf || shelf.dataset.primaryFilmId !== primaryId) return;
    const archive = state.discovery.archive;
    const primary = archive?.primary;
    const films = primary ? directorShelfFilms(primary, archive.directorWorks || []) : [];
    const stage = shelf.querySelector("[data-film-shelf]");
    if (stage && primary) stage.innerHTML = directorShelfFilmsMarkup(primary, films, true);
    shelf.classList.add("is-loading");
    shelf.classList.remove("has-partial-data");
    const status = shelf.querySelector("[data-film-shelf-status]");
    const retry = shelf.querySelector("[data-retry-director-shelf]");
    if (status) status.textContent = "Finding other verified films by this director…";
    retry?.classList.add("hidden");
    state.discovery.shelfState = "loading";
    persistDiscoverySession();
  }

  function hydrateDirectorShelf(primaryId, directorWorks) {
    if (state.discovery.archiveSelectionId !== primaryId) return;
    const shelf = refs.discoveryResults.querySelector("[data-director-shelf]");
    if (!shelf || shelf.dataset.primaryFilmId !== primaryId) return;
    const primary = state.discovery.archive?.primary;
    if (!primary) return;
    const films = directorShelfFilms(primary, directorWorks);
    const stage = shelf.querySelector("[data-film-shelf]");
    const count = shelf.querySelector("[data-film-shelf-count]");
    const status = shelf.querySelector("[data-film-shelf-status]");
    const retry = shelf.querySelector("[data-retry-director-shelf]");
    if (stage) stage.innerHTML = directorShelfFilmsMarkup(primary, films, false);
    if (count) count.textContent = `${films.length} ${films.length === 1 ? "film" : "films"}`;
    if (status) {
      status.textContent = films.length > 1
        ? `${films.length} verified films are ready to browse.`
        : "Only the selected film is currently on this shelf.";
    }
    retry?.classList.add("hidden");
    shelf.classList.remove("is-loading", "has-partial-data");
    state.discovery.shelfState = "ready";
    persistDiscoverySession();
  }

  function markDirectorShelfPartial(primaryId) {
    const shelf = refs.discoveryResults.querySelector("[data-director-shelf]");
    if (!shelf || shelf.dataset.primaryFilmId !== primaryId) return;
    shelf.classList.remove("is-loading");
    shelf.classList.add("has-partial-data");
    const status = shelf.querySelector("[data-film-shelf-status]");
    const retry = shelf.querySelector("[data-retry-director-shelf]");
    if (status) {
      status.textContent = "Showing the selected film. Try loading the director’s other films again.";
    }
    retry?.classList.remove("hidden");
  }

  function showFilmShelfFallback(primaryId, error) {
    console.warn("Director filmography request did not complete", error);
    const shelf = refs.discoveryResults.querySelector("[data-director-shelf]");
    if (!shelf || shelf.dataset.primaryFilmId !== primaryId) return;
    const archive = state.discovery.archive;
    const primary = archive?.primary;
    const films = primary ? directorShelfFilms(primary, archive.directorWorks || []) : [];
    const stage = shelf.querySelector("[data-film-shelf]");
    const count = shelf.querySelector("[data-film-shelf-count]");
    if (stage && primary) stage.innerHTML = directorShelfFilmsMarkup(primary, films, false);
    if (count) count.textContent = `${films.length} ${films.length === 1 ? "film" : "films"}`;
    markDirectorShelfPartial(primaryId);
    state.discovery.shelfState = "partial";
    persistDiscoverySession();
  }

  function renderFilmArchive(primary, directorWorks, relevant, loading) {
    state.discovery.archiveSelectionId = primary.id;
    state.discovery.archive = { primary, directorWorks, relevant };
    state.discovery.resultStage = "archive";
    state.discovery.shelfState = loading ? "loading" : "ready";
    refs.discoveryResults.innerHTML = filmArchiveMarkup(primary, directorWorks, loading);
    persistDiscoverySession();
  }

  return {
    renderDiscoveryResults,
    setArchiveHeading,
    setDirectorShelfLoading,
    hydrateDirectorShelf,
    markDirectorShelfPartial,
    showFilmShelfFallback,
    renderFilmArchive,
  };
}
