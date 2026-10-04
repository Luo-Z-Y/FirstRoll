import { errorInfo, json } from "../api/decode";
import { readApiError } from "../api/errors";
import type { Film, RelatedResult } from "../api/models";
import { relatedResult, searchResult, statusResult } from "../api/models";
import type { AppContext } from "../context";
import { uniqueFilms } from "../discovery/films";
import type { Services } from "../services";
import { eventElement } from "../shared/dom";

// Search and shelf requests; owns stale-response and cancellation guards.
export function createDiscovery(context: AppContext, services: () => Services) {
  const { state, refs } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const normaliseDiscoveryQuery: Services["session"]["normaliseDiscoveryQuery"] = (...args) => services().session.normaliseDiscoveryQuery(...args);
  const clearDiscoverySession: Services["session"]["clearDiscoverySession"] = (...args) => services().session.clearDiscoverySession(...args);
  const persistDiscoverySession: Services["session"]["persistDiscoverySession"] = (...args) => services().session.persistDiscoverySession(...args);
  const saveRecentSearch: Services["recent"]["saveRecentSearch"] = (...args) => services().recent.saveRecentSearch(...args);
  const renderDiscoveryResults: Services["shelf"]["renderDiscoveryResults"] = (...args) => services().shelf.renderDiscoveryResults(...args);
  const setArchiveHeading: Services["shelf"]["setArchiveHeading"] = (...args) => services().shelf.setArchiveHeading(...args);
  const setDirectorShelfLoading: Services["shelf"]["setDirectorShelfLoading"] = (...args) => services().shelf.setDirectorShelfLoading(...args);
  const hydrateDirectorShelf: Services["shelf"]["hydrateDirectorShelf"] = (...args) => services().shelf.hydrateDirectorShelf(...args);
  const showFilmShelfFallback: Services["shelf"]["showFilmShelfFallback"] = (...args) => services().shelf.showFilmShelfFallback(...args);
  const renderFilmArchive: Services["shelf"]["renderFilmArchive"] = (...args) => services().shelf.renderFilmArchive(...args);
  const cancelFilmDetailRequests: Services["dossier"]["cancelFilmDetailRequests"] = (...args) => services().dossier.cancelFilmDetailRequests(...args);
  const loadFilmDetail: Services["dossier"]["loadFilmDetail"] = (...args) => services().dossier.loadFilmDetail(...args);
  const discoveryApiBase: Services["ui"]["discoveryApiBase"] = (...args) => services().ui.discoveryApiBase(...args);
  const fetchProgressMarkup: Services["ui"]["fetchProgressMarkup"] = (...args) => services().ui.fetchProgressMarkup(...args);
  const focusElement: Services["ui"]["focusElement"] = (...args) => services().ui.focusElement(...args);
  const focusInterfaceState: Services["ui"]["focusInterfaceState"] = (...args) => services().ui.focusInterfaceState(...args);

  async function loadDiscoveryStatus(): Promise<void> {
    try {
      const res = await fetch(`${discoveryApiBase()}/api/discovery/status`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await json(res, statusResult);
      state.discovery.mode = data.mode || "unknown";
      const warmup = data.local_library?.index?.warmup;
      if (warmup?.state === "warming") {
        refs.discoveryConnection.textContent = "Preparing local semantic study search in the background…";
        refs.discoveryConnection.classList.remove("hidden");
        window.setTimeout(loadDiscoveryStatus, 1000);
      } else if (warmup?.state === "failed") {
        refs.discoveryConnection.textContent = "Semantic warm-up did not complete; lexical study retrieval remains available.";
        refs.discoveryConnection.classList.remove("hidden");
      } else {
        refs.discoveryConnection.textContent = "";
        refs.discoveryConnection.classList.add("hidden");
      }
    } catch (_) {
      refs.discoveryConnection.textContent = "Search unavailable";
      refs.discoveryConnection.classList.remove("hidden");
    }
  }

  async function onDiscoverySearch(event: Event): Promise<void> {
    event.preventDefault();
    const title = refs.filmTitle.value.trim();
    if (!title) {
      refs.filmTitle.focus();
      return;
    }

    cancelFilmDetailRequests();
    const params = new URLSearchParams({ q: title });
    const year = refs.filmYear.value.trim();
    const director = refs.filmDirector.value.trim();
    const query = normaliseDiscoveryQuery({ title, year, director });
    if (year) params.set("year", year);
    if (director) params.set("director", director);
    saveRecentSearch(query);

    state.discovery.searchController?.abort();
    cancelShelfRequests();
    const requestId = state.discovery.searchRequestId + 1;
    const controller = new AbortController();
    state.discovery.searchRequestId = requestId;
    state.discovery.searchController = controller;
    state.discovery.results = [];
    state.discovery.selectedFilm = null;
    state.discovery.detailFilmId = null;
    state.discovery.archive = null;
    state.discovery.archiveSelectionId = null;
    state.discovery.lastQuery = query;
    state.discovery.resultStage = "loading";
    state.discovery.shelfState = "idle";
    persistDiscoverySession();

    refs.discoverySubmit.setAttribute("aria-busy", "true");
    refs.discoveryResultsSection.setAttribute("aria-busy", "true");
    const submitLabel = refs.discoverySubmit.querySelector<HTMLElement>("span");
    if (submitLabel) submitLabel.textContent = "Searching…";
    refs.discoveryResultsSection.classList.remove("hidden");
    refs.filmDetail.classList.add("hidden");
    refs.discoveryResults.innerHTML = fetchProgressMarkup("Matching title, year and filmmaker identity…");
    refs.resultsTitle.textContent = `Finding “${title}”`;
    refs.resultsMeta.textContent = "";

    try {
      const res = await fetch(
        `${discoveryApiBase()}/api/discovery/search?${params.toString()}`,
        { signal: controller.signal },
      );
      if (!res.ok) throw new Error(await readApiError(res));
      const data = await json(res, searchResult);
      if (requestId !== state.discovery.searchRequestId) return;
      state.discovery.mode = data.mode || "unknown";
      state.discovery.lastQuery = normaliseDiscoveryQuery(data.query || query);
      renderDiscoveryResults(data);
    } catch (err) {
      if (errorInfo(err).name === "AbortError" || requestId !== state.discovery.searchRequestId) return;
      console.warn("Discovery request did not complete", err);
      state.discovery.resultStage = "error";
      clearDiscoverySession();
      refs.resultsTitle.textContent = "Discovery is unavailable";
      refs.discoveryResults.innerHTML = `<div class="interface-state is-error" role="alert" tabindex="-1" data-interface-state>
        <span>Catalogue connection</span>
        <h3>Film search could not finish.</h3>
        <p>Your query is still in the form. Check the FirstRoll connection, then try the same search again.</p>
        <button type="button" data-retry-discovery>Try search again</button>
      </div>`;
      focusInterfaceState(refs.discoveryResults);
    } finally {
      if (state.discovery.searchController === controller) {
        state.discovery.searchController = null;
        refs.discoverySubmit.removeAttribute("aria-busy");
        refs.discoveryResultsSection.setAttribute("aria-busy", "false");
        if (submitLabel) submitLabel.textContent = "Search films";
      }
    }
  }

  function cancelShelfRequests(): void {
    state.discovery.shelfRequestId += 1;
    state.discovery.shelfRequestControllers.forEach((controller) => controller.abort());
    state.discovery.shelfRequestControllers.clear();
  }

  function confirmDiscoveryFilm(index: number): void {
    const primary = state.discovery.results[index];
    if (!primary) return;
    cancelFilmDetailRequests();
    cancelShelfRequests();
    const nearby = uniqueFilms(state.discovery.results, [primary]).slice(0, 10);
    state.discovery.selectedFilm = null;
    state.discovery.detailFilmId = null;
    setArchiveHeading(primary);
    renderFilmArchive(primary, [], nearby, true);
    focusElement(refs.resultsTitle);
    void loadRelatedFilms(primary, nearby);
  }

  async function loadRelatedFilms(primary: Film, nearby: Film[]): Promise<void> {
    const requestId = state.discovery.shelfRequestId + 1;
    state.discovery.shelfRequestId = requestId;
    setDirectorShelfLoading(primary.id);
    try {
      const data = await fetchRelatedFilms(primary.id);
      if (
        requestId !== state.discovery.shelfRequestId
        || state.discovery.archiveSelectionId !== primary.id
      ) return;
      applyDirectorShelf(primary, nearby, data);
      void enrichDirectorFilmography(primary, nearby, requestId);
    } catch (error) {
      if (
        requestId !== state.discovery.shelfRequestId
        || state.discovery.archiveSelectionId !== primary.id
      ) return;
      showFilmShelfFallback(primary.id, error);
    }
  }

  async function enrichDirectorFilmography(primary: Film, nearby: Film[], requestId: number): Promise<void> {
    try {
      const data = await fetchRelatedFilms(primary.id, false);
      if (
        requestId !== state.discovery.shelfRequestId
        || state.discovery.archiveSelectionId !== primary.id
      ) return;
      const current = state.discovery.archive?.directorWorks || [];
      const enriched = uniqueFilms(data.same_director || [], [primary]);
      const enrichedById = new Map(enriched.map((film) => [film.id, film]));
      const merged = current.map((film) => {
        const update = enrichedById.get(film.id);
        if (!update) return film;
        enrichedById.delete(film.id);
        const next = { ...film, ...update };
        if (!update.poster_url && film.poster_url) {
          next.poster_url = film.poster_url;
          next.poster_source = film.poster_source;
        }
        return next;
      });
      const additions = [...enrichedById.values()];
      state.discovery.archive = {
        primary,
        directorWorks: [...merged, ...additions],
        relevant: nearby,
      };
      hydrateDirectorShelf(primary.id, state.discovery.archive.directorWorks);
    } catch (error) {
      if (
        requestId === state.discovery.shelfRequestId
        && state.discovery.archiveSelectionId === primary.id
      ) {
        console.debug("Director poster enrichment did not complete", error);
      }
    }
  }

  function applyDirectorShelf(primary: Film, nearby: Film[], data: RelatedResult): void {
    if (state.discovery.archiveSelectionId !== primary.id) return;
    const directorWorks = uniqueFilms(data.same_director || [], [primary]);
    state.discovery.archive = { primary, directorWorks, relevant: nearby };
    hydrateDirectorShelf(primary.id, directorWorks);
  }

  async function fetchRelatedFilms(filmId: string, fast = true): Promise<RelatedResult> {
    const cacheKey = `${filmId}:${fast ? "fast" : "enriched"}`;
    const cached = state.discovery.relatedFilmCache.get(cacheKey);
    if (cached) return cached;
    const controller = new AbortController();
    state.discovery.shelfRequestControllers.add(controller);
    const timeout = window.setTimeout(() => controller.abort(), fast ? 25000 : 90000);
    const progress = fast
      ? window.setTimeout(() => {
        const status = refs.discoveryResults.querySelector<HTMLElement>("[data-film-shelf-status]");
        if (status) status.textContent = "Still checking the verified director filmography…";
      }, 7000)
      : null;
    try {
      const res = await fetch(
        `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(filmId)}/related?limit=12&fast=${fast ? "true" : "false"}&director_only=true`,
        { signal: controller.signal },
      );
      if (!res.ok) throw new Error(await readApiError(res));
      const data = await json(res, relatedResult);
      if (data.state === "unavailable") {
        throw new Error("The verified director filmography did not respond.");
      }
      state.discovery.relatedFilmCache.set(cacheKey, data);
      return data;
    } catch (error) {
      throw errorInfo(error).name === "AbortError"
        ? new Error("The director filmography request timed out.")
        : error;
    } finally {
      state.discovery.shelfRequestControllers.delete(controller);
      window.clearTimeout(timeout);
      if (progress !== null) window.clearTimeout(progress);
    }
  }

  function retryDirectorShelf(): void {
    const archive = state.discovery.archive;
    if (!archive?.primary) return;
    cancelShelfRequests();
    void loadRelatedFilms(archive.primary, archive.relevant || []);
  }

  async function onFilmResultClick(event: MouseEvent): Promise<void> {
    const target = eventElement(event);
    if (!target) return;
    if (target.closest<HTMLButtonElement>("[data-retry-discovery]")) {
      refs.discoveryForm.requestSubmit();
      return;
    }
    if (target.closest<HTMLButtonElement>("[data-relax-discovery-filters]")) {
      refs.filmYear.value = "";
      refs.filmDirector.value = "";
      refs.discoveryForm.requestSubmit();
      return;
    }
    if (target.closest<HTMLButtonElement>("[data-edit-discovery-query]")) {
      refs.filmTitle.focus();
      refs.filmTitle.select();
      return;
    }
    const identityChoice = target.closest<HTMLButtonElement>("[data-confirm-film-index]");
    if (identityChoice) {
      confirmDiscoveryFilm(Number(identityChoice.dataset.confirmFilmIndex));
      return;
    }
    if (target.closest<HTMLButtonElement>("[data-retry-director-shelf]")) {
      retryDirectorShelf();
      return;
    }
    const selection = target.closest<HTMLButtonElement>("[data-select-film-id]");
    if (selection) {
      selectArchiveFilm(selection.dataset.selectFilmId);
      return;
    }
    const button = target.closest<HTMLButtonElement>("[data-film-id]");
    if (!button) return;
    await loadFilmDetail(button.dataset.filmId);
  }

  function selectArchiveFilm(filmId?: string): void {
    const archive = state.discovery.archive;
    if (!archive || archive.primary.id === filmId) return;
    const available = uniqueFilms([
      archive.primary,
      ...archive.directorWorks,
      ...archive.relevant,
    ]);
    const selected = available.find((film) => film.id === filmId);
    if (!selected) return;
    cancelShelfRequests();
    cancelFilmDetailRequests();
    const remaining = uniqueFilms(available, [selected]);
    state.discovery.selectedFilm = null;
    state.discovery.detailFilmId = null;
    refs.filmDetail.classList.add("hidden");
    renderFilmArchive(selected, [], remaining, true);
    void loadRelatedFilms(selected, remaining);
  }

  return {
    loadDiscoveryStatus,
    onDiscoverySearch,
    cancelShelfRequests,
    confirmDiscoveryFilm,
    loadRelatedFilms,
    enrichDirectorFilmography,
    applyDirectorShelf,
    fetchRelatedFilms,
    retryDirectorShelf,
    onFilmResultClick,
    selectArchiveFilm,
  };
}
