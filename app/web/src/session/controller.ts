import { record } from "../api/decode";
import type { Film } from "../api/models";
import { film as decodeFilm } from "../api/models";
import type { AppContext } from "../context";
import type { DiscoveryQuery } from "../discovery/types";
import { isProductView } from "../navigation/types";
import type { Services } from "../services";
import { normaliseFilmYear } from "../shared/format";
import { safeHttpUrl } from "../shared/html";
import type { Archive } from "../state";

interface DiscoverySnapshot { query: DiscoveryQuery; results: Film[]; archive: Archive | null; mode: string; stage: string; shelfState: string; detailFilmId: string | null }

// Versioned, bounded per-tab snapshots. No provider secrets belong in stored state.
const DISCOVERY_SESSION_KEY = "firstroll.discovery-session";

const PRODUCT_SESSION_KEY = "firstroll.product-session";

const SESSION_SCHEMA_VERSION = 1;

const DISCOVERY_SESSION_MAX_AGE_MS = 24 * 60 * 60 * 1000;

const DISCOVERY_SESSION_MAX_BYTES = 500_000;

const DISCOVERY_SESSION_STAGES = new Set(["loading", "choices", "empty", "archive"]);

const SHELF_SESSION_STATES = new Set(["idle", "loading", "ready", "partial"]);

export function createSession(context: AppContext, services: () => Services) {
  const { state, refs } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const setProductView: Services["navigation"]["setProductView"] = (...args) => services().navigation.setProductView(...args);
  const loadRelatedFilms: Services["discovery"]["loadRelatedFilms"] = (...args) => services().discovery.loadRelatedFilms(...args);
  const renderDiscoveryResults: Services["shelf"]["renderDiscoveryResults"] = (...args) => services().shelf.renderDiscoveryResults(...args);
  const setArchiveHeading: Services["shelf"]["setArchiveHeading"] = (...args) => services().shelf.setArchiveHeading(...args);
  const markDirectorShelfPartial: Services["shelf"]["markDirectorShelfPartial"] = (...args) => services().shelf.markDirectorShelfPartial(...args);
  const renderFilmArchive: Services["shelf"]["renderFilmArchive"] = (...args) => services().shelf.renderFilmArchive(...args);
  const loadFilmDetail: Services["dossier"]["loadFilmDetail"] = (...args) => services().dossier.loadFilmDetail(...args);
  const fetchProgressMarkup: Services["ui"]["fetchProgressMarkup"] = (...args) => services().ui.fetchProgressMarkup(...args);

  function persistCurrentSession(): void {
    state.viewScroll[state.productView] = Math.max(0, Number(window.scrollY) || 0);
    persistProductSession();
    persistDiscoverySession();
  }

  function persistProductSession(): void {
    try {
      window.sessionStorage.setItem(PRODUCT_SESSION_KEY, JSON.stringify({
        version: SESSION_SCHEMA_VERSION,
        view: state.productView,
        scroll: state.viewScroll,
      }));
    } catch (_) {
      // Navigation remains usable when per-tab browser storage is disabled.
    }
  }

  function restoreProductSession(): void {
    let stored: Record<string, unknown> | null = null;
    try {
      stored = record(JSON.parse(window.sessionStorage.getItem(PRODUCT_SESSION_KEY) || "null"));
    } catch (_) {
      stored = null;
    }
    if (stored?.version === SESSION_SCHEMA_VERSION && stored.scroll) {
      const scroll = typeof stored.scroll === "object" && !Array.isArray(stored.scroll)
        ? record(stored.scroll) : {};
      Object.keys(state.viewScroll).forEach((view) => {
        if (!isProductView(view)) return;
        const value = Number(scroll[view]);
        state.viewScroll[view] = Number.isFinite(value) && value >= 0 ? value : 0;
      });
    }
    const view = stored?.version === SESSION_SCHEMA_VERSION && isProductView(stored.view)
      ? stored.view
      : "discovery";
    setProductView(view, { captureCurrent: false, persist: false });
  }

  function normaliseDiscoveryQuery(value: unknown = {}): DiscoveryQuery {
    const query = value && typeof value === "object" && !Array.isArray(value) ? record(value) : {};
    return {
      title: String(query.title || query.q || "").trim().slice(0, 160),
      year: String(query.year || "").trim().slice(0, 4),
      director: String(query.director || "").trim().slice(0, 120),
    };
  }

  function isStoredFilm(value: unknown): boolean {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const film = record(value);
    if (typeof film.id !== "string" || !film.id.trim()) return false;
    const alternativeTitles = Array.isArray(film.alternative_titles)
      ? film.alternative_titles
      : [];
    return [film.title, film.original_title, ...alternativeTitles]
      .some((value) => typeof value === "string" && value.trim());
  }

  function discoverySessionFilm(value: unknown): Film | null {
    if (!isStoredFilm(value)) return null;
    let film: Film;
    try { film = decodeFilm(value); } catch (_) { return null; }
    const alternativeTitles = Array.isArray(film.alternative_titles)
      ? film.alternative_titles
        .filter((value) => typeof value === "string" && value.trim())
        .slice(0, 20)
      : [];
    const directors = Array.isArray(film.directors)
      ? film.directors
        .filter((value) => typeof value === "string" && value.trim())
        .slice(0, 12)
      : [];
    const releaseYears = Array.isArray(film.release_years)
      ? film.release_years.map(normaliseFilmYear).filter((value) => value !== null).slice(0, 12)
      : [];
    const posterUrl = safeHttpUrl(film.poster_url);
    const posterSourceUrl = safeHttpUrl(film.poster_source?.url);
    const runtime = Number(film.runtime_minutes);
    return {
      id: String(film.id).trim().slice(0, 180),
      provider_id: String(film.provider_id || "").trim().slice(0, 120),
      title: String(film.title || "").trim().slice(0, 240),
      original_title: String(film.original_title || "").trim().slice(0, 240),
      alternative_titles: alternativeTitles,
      year: normaliseFilmYear(film.year),
      release_years: releaseYears,
      runtime_minutes: Number.isFinite(runtime) && runtime > 0 ? runtime : null,
      directors,
      poster_url: posterUrl || null,
      poster_source: film.poster_source?.name ? {
        name: String(film.poster_source.name).trim().slice(0, 120),
        url: posterSourceUrl || null,
      } : null,
    };
  }

  function clearDiscoverySession(): void {
    try {
      window.sessionStorage.removeItem(DISCOVERY_SESSION_KEY);
    } catch (_) {
      // There is nothing else to clear when per-tab browser storage is disabled.
    }
  }

  function sessionByteLength(value: string): number {
    return new TextEncoder().encode(value).byteLength;
  }

  function persistDiscoverySession(): void {
    const query = normaliseDiscoveryQuery(state.discovery.lastQuery || {});
    if (!query.title || !DISCOVERY_SESSION_STAGES.has(state.discovery.resultStage)) {
      clearDiscoverySession();
      return;
    }
    const primary = discoverySessionFilm(state.discovery.archive?.primary);
    const archive = primary ? {
      primary,
      directorWorks: (state.discovery.archive?.directorWorks || [])
        .map(discoverySessionFilm)
        .filter((film): film is Film => film !== null)
        .slice(0, 12),
      relevant: (state.discovery.archive?.relevant || [])
        .map(discoverySessionFilm)
        .filter((film): film is Film => film !== null)
        .slice(0, 10),
    } : null;
    const snapshot = {
      version: SESSION_SCHEMA_VERSION,
      savedAt: Date.now(),
      query,
      mode: state.discovery.mode,
      stage: state.discovery.resultStage,
      shelfState: state.discovery.shelfState,
      results: state.discovery.results
        .map(discoverySessionFilm)
        .filter((film): film is Film => film !== null)
        .slice(0, 20),
      archive,
      detailFilmId: state.discovery.detailFilmId,
    };
    try {
      const serialised = JSON.stringify(snapshot);
      if (sessionByteLength(serialised) > DISCOVERY_SESSION_MAX_BYTES) {
        clearDiscoverySession();
        return;
      }
      window.sessionStorage.setItem(DISCOVERY_SESSION_KEY, serialised);
    } catch (_) {
      // Search remains available when per-tab browser storage is disabled or full.
    }
  }

  function readDiscoverySession(): DiscoverySnapshot | null {
    try {
      const serialised = window.sessionStorage.getItem(DISCOVERY_SESSION_KEY);
      if (!serialised) return null;
      if (sessionByteLength(serialised) > DISCOVERY_SESSION_MAX_BYTES) {
        clearDiscoverySession();
        return null;
      }
      const snapshot = record(JSON.parse(serialised));
      const age = Date.now() - Number(snapshot?.savedAt || 0);
      const query = normaliseDiscoveryQuery(snapshot?.query || {});
      const results = Array.isArray(snapshot?.results)
        ? snapshot.results.map(discoverySessionFilm).filter((film): film is Film => film !== null).slice(0, 20)
        : [];
      const rawArchive = snapshot.archive ? record(snapshot.archive) : null;
      const primary = discoverySessionFilm(rawArchive?.primary);
      const archive = primary ? {
        primary,
        directorWorks: Array.isArray(rawArchive?.directorWorks)
          ? rawArchive?.directorWorks.map(discoverySessionFilm).filter((film): film is Film => film !== null).slice(0, 12)
          : [],
        relevant: Array.isArray(rawArchive?.relevant)
          ? rawArchive?.relevant.map(discoverySessionFilm).filter((film): film is Film => film !== null).slice(0, 10)
          : [],
      } : null;
      if (
        snapshot?.version !== SESSION_SCHEMA_VERSION
        || !Number.isFinite(age)
        || age < -60_000
        || age > DISCOVERY_SESSION_MAX_AGE_MS
        || !query.title
        || typeof snapshot.stage !== "string" || !DISCOVERY_SESSION_STAGES.has(snapshot.stage)
        || (snapshot.stage === "archive" && !archive)
      ) {
        clearDiscoverySession();
        return null;
      }
      return {
        query,
        results,
        archive,
        mode: String(snapshot.mode || "unknown"),
        stage: snapshot.stage,
        shelfState: typeof snapshot.shelfState === "string" && SHELF_SESSION_STATES.has(snapshot.shelfState)
          ? snapshot.shelfState
          : "idle",
        detailFilmId: typeof snapshot.detailFilmId === "string"
          ? snapshot.detailFilmId
          : null,
      };
    } catch (_) {
      clearDiscoverySession();
      return null;
    }
  }

  function restoreDiscoverySession(): boolean {
    const snapshot = readDiscoverySession();
    if (!snapshot) return false;
    refs.filmTitle.value = snapshot.query.title;
    refs.filmYear.value = snapshot.query.year;
    refs.filmDirector.value = snapshot.query.director;
    refs.discoveryResultsSection.classList.remove("hidden");
    refs.filmDetail.classList.add("hidden");
    state.discovery.lastQuery = snapshot.query;
    state.discovery.results = snapshot.results;
    state.discovery.mode = snapshot.mode;
    state.discovery.resultStage = snapshot.stage;
    state.discovery.shelfState = snapshot.shelfState;
    state.discovery.detailFilmId = snapshot.detailFilmId;
    state.discovery.selectedFilm = null;

    if (snapshot.stage === "loading") {
      refs.resultsTitle.textContent = `Finding “${snapshot.query.title}”`;
      refs.resultsMeta.textContent = "";
      refs.discoveryResults.innerHTML = fetchProgressMarkup(
        "Restoring the latest film search…",
      );
      window.queueMicrotask(() => refs.discoveryForm.requestSubmit());
      return true;
    }
    if (snapshot.stage === "archive" && snapshot.archive) {
      const { primary, directorWorks, relevant } = snapshot.archive;
      setArchiveHeading(primary);
      renderFilmArchive(
        primary,
        directorWorks,
        relevant,
        snapshot.shelfState === "loading",
      );
      state.discovery.shelfState = snapshot.shelfState;
      if (snapshot.shelfState === "partial") markDirectorShelfPartial(primary.id);
      persistDiscoverySession();
      if (snapshot.shelfState === "loading") {
        void loadRelatedFilms(primary, relevant);
      }
      if (snapshot.detailFilmId) {
        void loadFilmDetail(snapshot.detailFilmId, { scroll: false });
      }
      return true;
    }
    renderDiscoveryResults({
      results: snapshot.results,
      query: snapshot.query,
      mode: snapshot.mode,
    });
    return true;
  }

  return {
    persistCurrentSession,
    persistProductSession,
    restoreProductSession,
    normaliseDiscoveryQuery,
    isStoredFilm,
    discoverySessionFilm,
    clearDiscoverySession,
    sessionByteLength,
    persistDiscoverySession,
    readDiscoverySession,
    restoreDiscoverySession,
  };
}
