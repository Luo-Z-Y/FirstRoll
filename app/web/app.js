const runtimeConfig = Object.freeze({
  apiBase: window.FIRSTROLL_CONFIG?.apiBase || "",
  publicMode: Boolean(window.FIRSTROLL_CONFIG?.publicMode),
  accountUi: Boolean(
    window.FIRSTROLL_CONFIG?.publicMode
    || window.FIRSTROLL_CONFIG?.localTestAccountEmail,
  ),
  videoAnalysisEnabled: window.FIRSTROLL_CONFIG?.videoAnalysisEnabled !== false,
  buildId: String(window.FIRSTROLL_CONFIG?.buildId || "").trim(),
  buildNumber: Number(window.FIRSTROLL_CONFIG?.buildNumber || 0),
  buildChannel: String(window.FIRSTROLL_CONFIG?.buildChannel || "local").trim().toLowerCase(),
  buildCommit: String(window.FIRSTROLL_CONFIG?.buildCommit || "unknown").trim(),
});

const state = {
  file: null,
  url: null,
  meta: null,
  analysis: null,
  productView: "discovery",
  viewScroll: { discovery: 0, analyse: 0, settings: 0 },
  discovery: {
    results: [],
    selectedFilm: null,
    detailFilmId: null,
    archive: null,
    archiveSelectionId: null,
    lastQuery: null,
    resultStage: "idle",
    shelfState: "idle",
    mode: "unknown",
    activeCriticismProvider: null,
    recentSearches: [],
    relatedFilmCache: new Map(),
    searchRequestId: 0,
    searchController: null,
    shelfRequestId: 0,
    shelfRequestControllers: new Set(),
    studyRequestId: 0,
    studyController: null,
    studyProgress: [],
  },
};

const CRITICISM_SOURCES = [
  { route: "crossref", label: "Research" },
  { route: "douban", label: "Douban" },
  { route: "letterboxd-web", label: "Letterboxd" },
  { route: "guardian-web", label: "Guardian" },
  { route: "letterboxd", label: "Letterboxd API" },
];

const RECENT_SEARCHES_KEY = "firstroll.recent-searches";
const THEME_STORAGE_KEY = "firstroll.theme";
const DISCOVERY_SESSION_KEY = "firstroll.discovery-session";
const PRODUCT_SESSION_KEY = "firstroll.product-session";
const SESSION_SCHEMA_VERSION = 1;
const DISCOVERY_SESSION_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const DISCOVERY_SESSION_MAX_BYTES = 500_000;
const DISCOVERY_SESSION_STAGES = new Set(["loading", "choices", "empty", "archive"]);
const SHELF_SESSION_STATES = new Set(["idle", "loading", "ready", "partial"]);
const MAX_RECENT_SEARCHES = 5;
const systemThemeMedia = window.matchMedia("(prefers-color-scheme: dark)");

const refs = {
  productViews: {
    discovery: document.getElementById("product-discovery"),
    analyse: document.getElementById("product-analyse"),
    settings: document.getElementById("product-settings"),
  },
  productNav: Array.from(document.querySelectorAll(".nav-link[data-product-view]")),
  productViewTriggers: Array.from(document.querySelectorAll("[data-product-view]")),
  themeToggle: document.getElementById("themeToggle"),
  buildIdentity: document.getElementById("buildIdentity"),
  discoveryForm: document.getElementById("discoveryForm"),
  filmTitle: document.getElementById("filmTitle"),
  filmYear: document.getElementById("filmYear"),
  filmDirector: document.getElementById("filmDirector"),
  discoverySubmit: document.getElementById("discoverySubmit"),
  discoveryConnection: document.getElementById("discoveryConnection"),
  discoveryResultsSection: document.getElementById("discoveryResultsSection"),
  discoveryResults: document.getElementById("discoveryResults"),
  resultsTitle: document.getElementById("resultsTitle"),
  resultsMeta: document.getElementById("resultsMeta"),
  filmDetail: document.getElementById("filmDetail"),
  analyseContext: document.getElementById("analyseContext"),
  videoAnalysisComingSoon: document.getElementById("videoAnalysisComingSoon"),
  recentSearches: document.getElementById("recentSearches"),
  videoFile: document.getElementById("videoFile"),
  fileTitle: document.getElementById("fileTitle"),
  fileMeta: document.getElementById("fileMeta"),
  sampleInterval: document.getElementById("sampleInterval"),
  sampleIntervalOut: document.getElementById("sampleIntervalOut"),
  sceneSensitivity: document.getElementById("sceneSensitivity"),
  sceneSensitivityOut: document.getElementById("sceneSensitivityOut"),
  backendUrl: document.getElementById("backendUrl"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  openShotDataBtn: document.getElementById("openShotDataBtn"),
  openColorBtn: document.getElementById("openColorBtn"),
  openObjectsBtn: document.getElementById("openObjectsBtn"),
  exportJsonBtn: document.getElementById("exportJsonBtn"),
  exportScenesCsvBtn: document.getElementById("exportScenesCsvBtn"),
  exportShotsCsvBtn: document.getElementById("exportShotsCsvBtn"),
  generateLlmDraftBtn: document.getElementById("generateLlmDraftBtn"),
  llmDraftWrap: document.getElementById("llmDraftWrap"),
  llmDraftText: document.getElementById("llmDraftText"),
  accountSavedFilms: document.getElementById("accountSavedFilms"),
  accountLibraryCount: document.getElementById("accountLibraryCount"),
  statusText: document.getElementById("statusText"),
  progressBar: document.getElementById("progressBar"),
  previewVideo: document.getElementById("previewVideo"),
  analysisVideo: document.getElementById("analysisVideo"),
  analysisCanvas: document.getElementById("analysisCanvas"),
  tabs: Array.from(document.querySelectorAll(".tab")),
  views: {
    overview: document.getElementById("view-overview"),
    shotdata: document.getElementById("view-shotdata"),
    color: document.getElementById("view-color"),
    objects: document.getElementById("view-objects"),
  },
  placeholders: {
    overview: document.getElementById("overviewPlaceholder"),
    shotdata: document.getElementById("shotdataPlaceholder"),
    color: document.getElementById("colorPlaceholder"),
    objects: document.getElementById("objectsPlaceholder"),
  },
  contents: {
    overview: document.getElementById("overviewContent"),
    shotdata: document.getElementById("shotdataContent"),
    color: document.getElementById("colorContent"),
    objects: document.getElementById("objectsContent"),
  },
};

window.FirstRollUI = Object.freeze({
  setThemePreference,
  themePreference: readThemePreference,
});

setup();

function setup() {
  renderBuildIdentity();
  applyRuntimeMode();
  refs.themeToggle.addEventListener("click", toggleTheme);
  systemThemeMedia.addEventListener?.("change", () => {
    if (readThemePreference() === "system") setThemePreference("system");
  });
  syncThemeToggle();
  refs.productViewTriggers.forEach((trigger) => {
    trigger.addEventListener("click", () => setProductView(trigger.dataset.productView));
  });
  refs.discoveryForm.addEventListener("submit", onDiscoverySearch);
  refs.discoveryResults.addEventListener("click", onFilmResultClick);
  refs.discoveryResults.addEventListener("firstroll:select-film", (event) => {
    selectArchiveFilm(event.detail?.filmId);
  });
  refs.filmDetail.addEventListener("click", onFilmDetailClick);
  refs.filmDetail.addEventListener("keydown", onFilmDetailKeydown);
  refs.recentSearches.addEventListener("click", onRecentSearchClick);
  state.discovery.recentSearches = readRecentSearches();
  renderRecentSearches(state.discovery.recentSearches);
  restoreDiscoverySession();
  restoreProductSession();
  window.addEventListener("pagehide", persistCurrentSession);

  refs.sampleInterval.addEventListener("input", () => {
    refs.sampleIntervalOut.value = `${Number(refs.sampleInterval.value).toFixed(2)}s`;
  });
  refs.sceneSensitivity.addEventListener("input", () => {
    refs.sceneSensitivityOut.value = refs.sceneSensitivity.value;
  });

  refs.videoFile.addEventListener("change", onFileSelected);
  refs.analyzeBtn.addEventListener("click", onAnalyze);
  refs.openShotDataBtn.addEventListener("click", () => setActiveView("shotdata"));
  refs.openColorBtn.addEventListener("click", () => setActiveView("color"));
  refs.openObjectsBtn.addEventListener("click", () => setActiveView("objects"));
  refs.exportJsonBtn.addEventListener("click", exportAnalysisJson);
  refs.exportScenesCsvBtn.addEventListener("click", exportScenesCsv);
  refs.exportShotsCsvBtn.addEventListener("click", exportShotsCsv);
  refs.generateLlmDraftBtn.addEventListener("click", generateLlmDraft);
  refs.accountSavedFilms?.addEventListener("click", onSavedFilmsClick);

  refs.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActiveView(tab.dataset.view));
    tab.addEventListener("keydown", onAnalysisTabKeydown);
  });

  setFeatureButtonsEnabled(false);
  loadDiscoveryStatus();
  document.addEventListener("firstroll:auth-changed", updateAccountFilmState);
  document.addEventListener("firstroll:account-data-changed", updateAccountFilmState);
  document.addEventListener("firstroll:integration-changed", updateIntegrationDependentState);
}

function renderBuildIdentity() {
  if (!refs.buildIdentity || !runtimeConfig.buildId) return;
  const channel = ["local", "live", "preview"].includes(runtimeConfig.buildChannel)
    ? runtimeConfig.buildChannel
    : "local";
  const channelLabel = channel === "live" ? "LIVE" : channel.toUpperCase();
  refs.buildIdentity.textContent = `${runtimeConfig.buildId} · ${channelLabel}`;
  refs.buildIdentity.title = `${channelLabel.toLowerCase()} build ${runtimeConfig.buildId} · commit ${runtimeConfig.buildCommit}`;
  refs.buildIdentity.classList.remove("hidden");
  document.documentElement.dataset.buildChannel = channel;
}

function updateAccountFilmState() {
  updateDeepStudyAuthState();
  updateSavedFilmButton();
  renderSavedFilms(window.FirstRollAuth?.savedFilms?.() || []);
}

function updateDeepStudyAuthState() {
  const button = refs.filmDetail.querySelector("[data-generate-study]");
  if (!button || !runtimeConfig.accountUi) return;
  button.textContent = window.FirstRollAuth?.currentUser()
    ? "Generate study"
    : "Sign in to Deep Study";
}

function updateSavedFilmButton() {
  const button = refs.filmDetail.querySelector("[data-save-film]");
  const film = state.discovery.selectedFilm;
  if (!button || !film) return;
  const signedIn = Boolean(window.FirstRollAuth?.currentUser?.());
  const saved = Boolean(window.FirstRollAuth?.isFilmSaved?.(film.id));
  button.dataset.saved = String(saved);
  button.textContent = signedIn
    ? (saved ? "Remove from saved films" : "Save to account")
    : "Sign in to save";
}

function renderSavedFilms(films) {
  if (!refs.accountSavedFilms || !refs.accountLibraryCount) return;
  const items = Array.isArray(films) ? films : [];
  refs.accountLibraryCount.textContent = `${items.length} ${items.length === 1 ? "film" : "films"}`;
  if (!items.length) {
    refs.accountSavedFilms.innerHTML = '<p class="module-empty">No saved films yet. Open a film dossier and choose “Save to account”.</p>';
    return;
  }
  refs.accountSavedFilms.innerHTML = items.map((film) => {
    const poster = safeHttpUrl(film.poster_url);
    const meta = [film.release_year, film.director].filter(Boolean).join(" · ") || "Film details unavailable";
    return `<article class="saved-film">
      ${poster
        ? `<img src="${escapeHtml(poster)}" alt="" loading="lazy" referrerpolicy="no-referrer" />`
        : `<span class="saved-film-poster" aria-hidden="true">FR</span>`}
      <div>
        <strong>${escapeHtml(film.title || "Untitled")}</strong>
        <small>${escapeHtml(meta)}</small>
      </div>
      <button type="button" data-remove-saved-film="${escapeHtml(film.film_id)}" aria-label="Remove ${escapeHtml(film.title || "film")} from saved films">×</button>
    </article>`;
  }).join("");
}

async function onSavedFilmsClick(event) {
  const retry = event.target.closest("[data-retry-saved-films]");
  if (retry) {
    retry.disabled = true;
    try {
      await window.FirstRollAuth?.refreshSavedFilms?.();
      renderSavedFilms(window.FirstRollAuth?.savedFilms?.() || []);
    } catch (error) {
      console.warn("Saved films could not be refreshed", error);
      retry.disabled = false;
    }
    return;
  }
  const button = event.target.closest("[data-remove-saved-film]");
  if (!button) return;
  button.disabled = true;
  try {
    await window.FirstRollAuth?.removeSavedFilm?.(button.dataset.removeSavedFilm);
  } catch (error) {
    console.warn("Saved film could not be removed", error);
    refs.accountSavedFilms.innerHTML = `<div class="interface-state is-error is-compact" role="alert" tabindex="-1" data-interface-state>
      <span>Saved films</span>
      <h4>The film could not be removed.</h4>
      <p>Your account data is unchanged. Refresh the saved-film list, then try the removal again.</p>
      <button type="button" data-retry-saved-films>Refresh saved films</button>
    </div>`;
    focusInterfaceState(refs.accountSavedFilms);
  } finally {
    button.disabled = false;
  }
}

function updateIntegrationDependentState() {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-film-videos-output]");
  if (film && output && !film.video_sources?.bundle) {
    output.innerHTML = videoProviderStatusMarkup(film.video_sources?.providers);
  }
}

function applyRuntimeMode() {
  document.body.classList.toggle("public-mode", runtimeConfig.accountUi);
  document.body.classList.toggle(
    "video-analysis-disabled",
    !runtimeConfig.videoAnalysisEnabled,
  );
  refs.videoAnalysisComingSoon.classList.toggle(
    "hidden",
    runtimeConfig.videoAnalysisEnabled,
  );
}

function toggleTheme() {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  setThemePreference(nextTheme);
}

function readThemePreference() {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return ["system", "light", "dark"].includes(stored) ? stored : "system";
  } catch (_) {
    return "system";
  }
}

function setThemePreference(preference) {
  const selected = ["system", "light", "dark"].includes(preference)
    ? preference
    : "system";
  const resolved = selected === "system"
    ? (systemThemeMedia.matches ? "dark" : "light")
    : selected;
  document.documentElement.dataset.theme = resolved;
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, selected);
  } catch (_) {
    // Theme switching remains available when local browser storage is disabled.
  }
  syncThemeToggle();
  document.dispatchEvent(new CustomEvent("firstroll:theme-changed", {
    detail: { preference: selected, resolved },
  }));
}

function syncThemeToggle() {
  const dark = document.documentElement.dataset.theme === "dark";
  const label = dark ? "Switch to light mode" : "Switch to dark mode";
  refs.themeToggle.setAttribute("aria-label", label);
  refs.themeToggle.title = label;
  refs.themeToggle.setAttribute("aria-pressed", String(dark));
}

function setProductView(viewKey, options = {}) {
  if (!refs.productViews[viewKey]) return;
  if (options.captureCurrent !== false && refs.productViews[state.productView]) {
    state.viewScroll[state.productView] = Math.max(0, Number(window.scrollY) || 0);
  }
  Object.entries(refs.productViews).forEach(([key, section]) => {
    section.classList.toggle("active", key === viewKey);
  });
  refs.productNav.forEach((button) => {
    const active = button.dataset.productView === viewKey;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  state.productView = viewKey;
  if (options.persist !== false) persistProductSession();
  document.dispatchEvent(new CustomEvent("firstroll:view-changed", {
    detail: { view: viewKey },
  }));
  const scrollTop = options.restoreScroll === false
    ? 0
    : Math.max(0, Number(state.viewScroll[viewKey]) || 0);
  window.requestAnimationFrame(() => {
    window.scrollTo({ top: scrollTop, behavior: "auto" });
  });
}

function persistCurrentSession() {
  state.viewScroll[state.productView] = Math.max(0, Number(window.scrollY) || 0);
  persistProductSession();
  persistDiscoverySession();
}

function persistProductSession() {
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

function restoreProductSession() {
  let stored = null;
  try {
    stored = JSON.parse(window.sessionStorage.getItem(PRODUCT_SESSION_KEY) || "null");
  } catch (_) {
    stored = null;
  }
  if (stored?.version === SESSION_SCHEMA_VERSION && stored.scroll) {
    Object.keys(state.viewScroll).forEach((view) => {
      const value = Number(stored.scroll[view]);
      state.viewScroll[view] = Number.isFinite(value) && value >= 0 ? value : 0;
    });
  }
  const view = stored?.version === SESSION_SCHEMA_VERSION && refs.productViews[stored.view]
    ? stored.view
    : "discovery";
  setProductView(view, { captureCurrent: false, persist: false });
}

function normaliseDiscoveryQuery(query = {}) {
  return {
    title: String(query.title || query.q || "").trim().slice(0, 160),
    year: String(query.year || "").trim().slice(0, 4),
    director: String(query.director || "").trim().slice(0, 120),
  };
}

function isStoredFilm(film) {
  if (!film || typeof film !== "object" || Array.isArray(film)) return false;
  if (typeof film.id !== "string" || !film.id.trim()) return false;
  const alternativeTitles = Array.isArray(film.alternative_titles)
    ? film.alternative_titles
    : [];
  return [film.title, film.original_title, ...alternativeTitles]
    .some((value) => typeof value === "string" && value.trim());
}

function discoverySessionFilm(film) {
  if (!isStoredFilm(film)) return null;
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

function clearDiscoverySession() {
  try {
    window.sessionStorage.removeItem(DISCOVERY_SESSION_KEY);
  } catch (_) {
    // There is nothing else to clear when per-tab browser storage is disabled.
  }
}

function sessionByteLength(value) {
  return new TextEncoder().encode(value).byteLength;
}

function persistDiscoverySession() {
  const query = normaliseDiscoveryQuery(state.discovery.lastQuery || {});
  if (!query.title || !DISCOVERY_SESSION_STAGES.has(state.discovery.resultStage)) {
    clearDiscoverySession();
    return;
  }
  const primary = discoverySessionFilm(state.discovery.archive?.primary);
  const archive = primary ? {
    primary,
    directorWorks: (state.discovery.archive.directorWorks || [])
      .map(discoverySessionFilm)
      .filter(Boolean)
      .slice(0, 12),
    relevant: (state.discovery.archive.relevant || [])
      .map(discoverySessionFilm)
      .filter(Boolean)
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
      .filter(Boolean)
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

function readDiscoverySession() {
  try {
    const serialised = window.sessionStorage.getItem(DISCOVERY_SESSION_KEY);
    if (!serialised) return null;
    if (sessionByteLength(serialised) > DISCOVERY_SESSION_MAX_BYTES) {
      clearDiscoverySession();
      return null;
    }
    const snapshot = JSON.parse(serialised);
    const age = Date.now() - Number(snapshot?.savedAt || 0);
    const query = normaliseDiscoveryQuery(snapshot?.query || {});
    const results = Array.isArray(snapshot?.results)
      ? snapshot.results.map(discoverySessionFilm).filter(Boolean).slice(0, 20)
      : [];
    const rawArchive = snapshot?.archive;
    const primary = discoverySessionFilm(rawArchive?.primary);
    const archive = primary ? {
      primary,
      directorWorks: Array.isArray(rawArchive.directorWorks)
        ? rawArchive.directorWorks.map(discoverySessionFilm).filter(Boolean).slice(0, 12)
        : [],
      relevant: Array.isArray(rawArchive.relevant)
        ? rawArchive.relevant.map(discoverySessionFilm).filter(Boolean).slice(0, 10)
        : [],
    } : null;
    if (
      snapshot?.version !== SESSION_SCHEMA_VERSION
      || age < -60_000
      || age > DISCOVERY_SESSION_MAX_AGE_MS
      || !query.title
      || !DISCOVERY_SESSION_STAGES.has(snapshot.stage)
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
      shelfState: SHELF_SESSION_STATES.has(snapshot.shelfState)
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

function restoreDiscoverySession() {
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

function discoveryApiBase() {
  return (runtimeConfig.apiBase || document.body.dataset.apiBase || "").replace(/\/$/, "");
}

function fetchProgressMarkup(message) {
  return `<div class="inline-fetch-progress" data-active-fetch-progress role="status" aria-live="polite">
    <span>${escapeHtml(message)}</span>
    <div class="inline-fetch-track" aria-hidden="true"><i></i></div>
  </div>`;
}

function focusElement(element, options = {}) {
  if (!element) return;
  window.queueMicrotask(() => {
    if (element.isConnected) {
      element.focus({ preventScroll: options.preventScroll === true });
    }
  });
}

function focusInterfaceState(container, selector = "[data-interface-state]") {
  focusElement(container?.querySelector(selector));
}

const RESEARCH_PROGRESS_KINDS = new Set([
  "film_resolving",
  "film_needs_choice",
  "existing_evidence_loading",
  "research_planning",
  "tool_started",
  "tool_completed",
  "tool_failed",
  "evidence_assessed",
  "study_drafting",
  "quality_checked",
  "study_repairing",
  "run_completed",
  "run_failed",
]);
const RESEARCH_PROGRESS_KEYS = new Set([
  "run_id", "kind", "sequence", "message", "elapsed_ms", "counts",
]);
const RESEARCH_PROGRESS_COUNT_KEYS = new Set([
  "theory_sources", "critical_claims", "attributed_sources", "sections",
]);
const RESEARCH_COUNT_LABELS = Object.freeze({
  theory_sources: "theory",
  critical_claims: "critic claims",
  attributed_sources: "attributed text",
  sections: "sections",
});

function researchProgressMarkup(events, options = {}) {
  const history = Array.isArray(events) ? events.slice(-12) : [];
  const latest = history[history.length - 1] || {
    sequence: 1,
    kind: "existing_evidence_loading",
    message: "Preparing the evidence packet…",
    elapsed_ms: 0,
    counts: {},
  };
  const combinedCounts = history.reduce(
    (counts, progress) => ({ ...counts, ...(progress.counts || {}) }),
    {},
  );
  const countsMarkup = Object.entries(combinedCounts)
    .filter(([key, value]) => RESEARCH_PROGRESS_COUNT_KEYS.has(key) && Number.isInteger(value))
    .map(([key, value]) => `<span><b>${escapeHtml(value)}</b> ${escapeHtml(RESEARCH_COUNT_LABELS[key])}</span>`)
    .join("");
  return `<section class="study-progress-history" aria-label="Deep Study progress">
    <header>
      <div><span>${options.completed ? "Run complete" : "Current stage"}</span><strong>${escapeHtml(latest.message)}</strong></div>
      ${countsMarkup ? `<div class="study-progress-counts">${countsMarkup}</div>` : ""}
      <p class="study-progress-current" role="status" aria-live="polite">${escapeHtml(latest.message)}</p>
    </header>
    <ol>
      ${history.map((progress, index) => `<li class="${index === history.length - 1 ? "is-current" : "is-complete"}">
        <i aria-hidden="true">${index === history.length - 1 && !options.completed ? "•" : "✓"}</i>
        <span>${escapeHtml(progress.message)}</span>
        <small>${escapeHtml((Number(progress.elapsed_ms || 0) / 1000).toFixed(1))}s</small>
      </li>`).join("")}
    </ol>
  </section>`;
}

function parseProgressEvent(block) {
  const lines = block.split(/\r?\n/);
  const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
  if (eventName !== "progress") return null;
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  const parsed = JSON.parse(data);
  if (
    !parsed
    || typeof parsed !== "object"
    || Array.isArray(parsed)
    || Object.keys(parsed).some((key) => !RESEARCH_PROGRESS_KEYS.has(key))
    || !RESEARCH_PROGRESS_KINDS.has(parsed.kind)
    || typeof parsed.message !== "string"
    || parsed.message.length > 180
    || (parsed.counts && (
      typeof parsed.counts !== "object"
      || Array.isArray(parsed.counts)
      || Object.entries(parsed.counts).some(([key, value]) => (
        !RESEARCH_PROGRESS_COUNT_KEYS.has(key)
        || !Number.isInteger(value)
        || value < 0
      ))
    ))
  ) {
    throw new Error("The research progress stream was invalid.");
  }
  return {
    run_id: String(parsed.run_id || ""),
    kind: String(parsed.kind || ""),
    sequence: Number(parsed.sequence || 0),
    message: String(parsed.message || ""),
    elapsed_ms: Number(parsed.elapsed_ms || 0),
    counts: parsed.counts && typeof parsed.counts === "object" ? parsed.counts : {},
  };
}

async function consumeResearchProgress(response, expectedRunId, onProgress) {
  if (!response.body) throw new Error("This browser cannot read streaming progress.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastSequence = 0;
  let completed = false;

  const consumeBlock = (block) => {
    const progress = parseProgressEvent(block);
    if (!progress) return;
    if (
      !progress.run_id
      || progress.run_id !== expectedRunId
      || progress.sequence !== lastSequence + 1
      || !progress.message
    ) {
      throw new Error("The research progress stream was invalid.");
    }
    lastSequence = progress.sequence;
    onProgress(progress);
    if (progress.kind === "run_failed") throw new Error(progress.message);
    if (progress.kind === "run_completed") completed = true;
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";
    blocks.forEach(consumeBlock);
    if (done) break;
  }
  if (buffer.trim()) consumeBlock(buffer);
  if (!completed) throw new Error("The research progress stream ended before completion.");
}

async function loadDiscoveryStatus() {
  try {
    const res = await fetch(`${discoveryApiBase()}/api/discovery/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
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

async function onDiscoverySearch(event) {
  event.preventDefault();
  const title = refs.filmTitle.value.trim();
  if (!title) {
    refs.filmTitle.focus();
    return;
  }

  cancelDeepStudyRequest();
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
  refs.discoverySubmit.querySelector("span").textContent = "Searching…";
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
    const data = await res.json();
    if (requestId !== state.discovery.searchRequestId) return;
    state.discovery.mode = data.mode || "unknown";
    state.discovery.lastQuery = normaliseDiscoveryQuery(data.query || query);
    renderDiscoveryResults(data);
  } catch (err) {
    if (err?.name === "AbortError" || requestId !== state.discovery.searchRequestId) return;
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
      refs.discoverySubmit.querySelector("span").textContent = "Search films";
    }
  }
}

function cancelShelfRequests() {
  state.discovery.shelfRequestId += 1;
  state.discovery.shelfRequestControllers.forEach((controller) => controller.abort());
  state.discovery.shelfRequestControllers.clear();
}

function readRecentSearches() {
  try {
    const searches = JSON.parse(window.localStorage.getItem(RECENT_SEARCHES_KEY) || "[]");
    if (!Array.isArray(searches)) return [];
    return searches
      .filter((search) => search && typeof search.title === "string" && search.title.trim())
      .slice(0, MAX_RECENT_SEARCHES)
      .map((search) => ({
        title: search.title.trim(),
        year: String(search.year || "").trim(),
        director: String(search.director || "").trim(),
      }));
  } catch (_) {
    return [];
  }
}

function saveRecentSearch(search) {
  const recentSearches = readRecentSearches();
  const identity = [search.title, search.year, search.director]
    .map((value) => String(value || "").trim().toLocaleLowerCase())
    .join("\u0000");
  const nextSearches = [
    search,
    ...recentSearches.filter((item) => [item.title, item.year, item.director]
      .map((value) => String(value || "").trim().toLocaleLowerCase())
      .join("\u0000") !== identity),
  ].slice(0, MAX_RECENT_SEARCHES);
  persistRecentSearches(nextSearches);
  state.discovery.recentSearches = nextSearches;
  renderRecentSearches(nextSearches);
}

function persistRecentSearches(searches) {
  try {
    if (searches.length) {
      window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(searches));
    } else {
      window.localStorage.removeItem(RECENT_SEARCHES_KEY);
    }
  } catch (_) {
    // Search remains available even when local browser storage is disabled.
  }
}

function renderRecentSearches(searches = readRecentSearches()) {
  refs.recentSearches.classList.toggle("hidden", searches.length === 0);
  refs.recentSearches.innerHTML = searches.length ? `
    <span>Recent</span>
    ${searches.map((search, index) => {
      const details = [search.year, search.director].filter(Boolean).join(" · ");
      const accessibleDetails = details ? `, ${details}` : "";
      return `<span class="recent-search-item">
        <button class="recent-search-query" type="button" data-recent-search="${index}" aria-label="Search again for ${escapeHtml(search.title)}${escapeHtml(accessibleDetails)}"><strong>${escapeHtml(search.title)}</strong>${details ? `<small>${escapeHtml(details)}</small>` : ""}</button>
        <button class="recent-search-dismiss" type="button" data-remove-recent-search="${index}" aria-label="Remove ${escapeHtml(search.title)} from recent searches"><span aria-hidden="true">×</span></button>
      </span>`;
    }).join("")}
    <button class="recent-search-clear" type="button" data-clear-recent-searches>Clear all</button>` : "";
}

function onRecentSearchClick(event) {
  const removeButton = event.target.closest("[data-remove-recent-search]");
  if (removeButton) {
    const index = Number(removeButton.dataset.removeRecentSearch);
    const nextSearches = state.discovery.recentSearches.filter((_, itemIndex) => itemIndex !== index);
    persistRecentSearches(nextSearches);
    state.discovery.recentSearches = nextSearches;
    renderRecentSearches(nextSearches);
    return;
  }
  if (event.target.closest("[data-clear-recent-searches]")) {
    persistRecentSearches([]);
    state.discovery.recentSearches = [];
    renderRecentSearches([]);
    return;
  }
  const button = event.target.closest("[data-recent-search]");
  if (!button) return;
  const search = state.discovery.recentSearches[Number(button.dataset.recentSearch)];
  if (!search) return;
  refs.filmTitle.value = search.title;
  refs.filmYear.value = search.year;
  refs.filmDirector.value = search.director;
  refs.discoveryForm.requestSubmit();
}

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

function filmIdentityChoicesMarkup(films) {
  return `
    <section class="identity-confirmation" aria-labelledby="identityConfirmationTitle">
      <div class="identity-confirmation-intro">
        <p class="eyebrow">Confirm film identity</p>
        <h3 id="identityConfirmationTitle" tabindex="-1">Choose the correct edition</h3>
        <p>Check the year, filmmaker and original title before FirstRoll builds the dossier.</p>
      </div>
      <div class="identity-choice-grid">
        ${films.map((film, index) => {
          const title = film.title || film.original_title || "Untitled";
          const originalTitle = film.original_title && film.original_title !== title
            ? film.original_title
            : "";
          const directors = displayCrew(film.directors || [], "Director not supplied");
          const year = filmYearLabel(film);
          const accessibleIdentity = [title, year, directors].filter(Boolean).join(", ");
          return `
            <button
              type="button"
              class="identity-choice"
              data-confirm-film-index="${index}"
              aria-label="Choose ${escapeHtml(accessibleIdentity)}"
            >
              <span class="identity-choice-poster" aria-hidden="true">
                ${film.poster_url
                  ? `<img src="${escapeHtml(film.poster_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()" />`
                  : ""}
                <span>${escapeHtml(title)}</span>
              </span>
              <span class="identity-choice-copy">
                <small>Candidate ${String(index + 1).padStart(2, "0")}</small>
                <strong>${escapeHtml(title)}</strong>
                ${originalTitle ? `<em>${escapeHtml(originalTitle)}</em>` : ""}
                <span>${escapeHtml(year)} · ${escapeHtml(directors)}</span>
                <b>Choose this film <i aria-hidden="true">↗</i></b>
              </span>
            </button>`;
        }).join("")}
      </div>
    </section>`;
}

function setArchiveHeading(primary) {
  refs.resultsTitle.textContent = "Pulled from the shelf";
  refs.resultsMeta.textContent = [
    primary.title,
    filmYearLabel(primary),
    displayCrew(primary.directors || [], ""),
  ].filter(Boolean).join(" / ");
}

function confirmDiscoveryFilm(index) {
  const primary = state.discovery.results[index];
  if (!primary) return;
  cancelShelfRequests();
  const nearby = uniqueFilms(state.discovery.results, [primary]).slice(0, 10);
  state.discovery.selectedFilm = null;
  state.discovery.detailFilmId = null;
  setArchiveHeading(primary);
  renderFilmArchive(primary, [], nearby, true);
  focusElement(refs.resultsTitle);
  void loadRelatedFilms(primary, nearby);
}

async function loadRelatedFilms(primary, nearby) {
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

async function enrichDirectorFilmography(primary, nearby, requestId) {
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

function applyDirectorShelf(primary, nearby, data) {
  if (state.discovery.archiveSelectionId !== primary.id) return;
  const directorWorks = uniqueFilms(data.same_director || [], [primary]);
  state.discovery.archive = { primary, directorWorks, relevant: nearby };
  hydrateDirectorShelf(primary.id, directorWorks);
}

async function fetchRelatedFilms(filmId, fast = true) {
  const cacheKey = `${filmId}:${fast ? "fast" : "enriched"}`;
  const cached = state.discovery.relatedFilmCache.get(cacheKey);
  if (cached) return cached;
  const controller = new AbortController();
  state.discovery.shelfRequestControllers.add(controller);
  const timeout = window.setTimeout(() => controller.abort(), fast ? 25000 : 90000);
  const progress = fast
    ? window.setTimeout(() => {
      const status = refs.discoveryResults.querySelector("[data-film-shelf-status]");
      if (status) status.textContent = "Still checking the verified director filmography…";
    }, 7000)
    : null;
  try {
    const res = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(filmId)}/related?limit=12&fast=${fast ? "true" : "false"}&director_only=true`,
      { signal: controller.signal },
    );
    if (!res.ok) throw new Error(await readApiError(res));
    const data = await res.json();
    if (data.state === "unavailable") {
      throw new Error("The verified director filmography did not respond.");
    }
    state.discovery.relatedFilmCache.set(cacheKey, data);
    return data;
  } catch (error) {
    throw error?.name === "AbortError"
      ? new Error("The director filmography request timed out.")
      : error;
  } finally {
    state.discovery.shelfRequestControllers.delete(controller);
    window.clearTimeout(timeout);
    window.clearTimeout(progress);
  }
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

function retryDirectorShelf() {
  const archive = state.discovery.archive;
  if (!archive?.primary) return;
  cancelShelfRequests();
  void loadRelatedFilms(archive.primary, archive.relevant || []);
}

function uniqueFilms(films, excluded = []) {
  const seen = new Set(excluded.map((film) => film.id));
  return films.filter((film) => {
    if (!film?.id || seen.has(film.id)) return false;
    seen.add(film.id);
    return true;
  });
}

function renderFilmArchive(primary, directorWorks, relevant, loading) {
  const director = firstCrewName(primary.directors || [], "Director not supplied");
  const duration = formatFilmDuration(primary.runtime_minutes);
  state.discovery.archiveSelectionId = primary.id;
  state.discovery.archive = { primary, directorWorks, relevant };
  state.discovery.resultStage = "archive";
  state.discovery.shelfState = loading ? "loading" : "ready";
  refs.discoveryResults.innerHTML = `
    <div class="archive-pullout-shell">
      <div class="archive-pullout">
        <div class="archive-pullout-label"><span>Selected edition</span><small>FirstRoll Collection</small></div>
        ${criterionCaseMarkup(primary)}
        <div class="archive-pullout-copy">
          <p>${escapeHtml(displayCrew(primary.directors || [], "Director not supplied"))}</p>
          <h3>${escapeHtml(primary.title || "Untitled")}</h3>
          <div>
            <span>${escapeHtml(filmYearLabel(primary))}${duration ? ` · ${escapeHtml(duration)}` : ""}</span>
            ${primary.original_title && primary.original_title !== primary.title ? `<span>${escapeHtml(primary.original_title)}</span>` : ""}
          </div>
          <button type="button" data-film-id="${escapeHtml(primary.id)}">
            Open film dossier <span aria-hidden="true">↗</span>
          </button>
        </div>
      </div>
    </div>
    ${directorShelfMarkup(primary, directorWorks, director, loading)}`;
  persistDiscoverySession();
}

function formatFilmDuration(minutes) {
  const total = Number(minutes);
  if (!Number.isFinite(total) || total <= 0) return "";
  const hours = Math.floor(total / 60);
  const remainder = Math.round(total % 60);
  if (!hours) return `${remainder} min`;
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`;
}

function filmYearLabel(film) {
  const years = [...new Set(
    [film?.year, ...(Array.isArray(film?.release_years) ? film.release_years : [])]
      .map(normaliseFilmYear)
      .filter((year) => year !== null),
  )].sort((left, right) => left - right);
  return years[0] ? String(years[0]) : "Year unknown";
}

function normaliseFilmYear(value) {
  if (value === null || value === undefined || value === "") return null;
  const year = Number(value);
  return Number.isInteger(year) && year >= 1888 && year <= 2100 ? year : null;
}

function criterionCaseMarkup(film) {
  const title = escapeHtml(film.title || "Untitled");
  return `
    <div class="criterion-object" role="img" aria-label="${title} selected archive edition">
      <div class="criterion-disc" aria-hidden="true">
        <i></i><b>FIRSTROLL</b><small>${escapeHtml(film.year || "FILM")}</small>
      </div>
      <div class="criterion-case">
        <div class="criterion-cover">
          <span class="criterion-series">The FirstRoll Collection</span>
          ${film.poster_url
            ? `<img src="${escapeHtml(film.poster_url)}" alt="Poster for ${title}" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()" />`
            : ""}
        </div>
      </div>
    </div>`;
}

function directorShelfFilms(primary, directorWorks) {
  return displayableFilms([primary, ...directorWorks]).slice(0, 12);
}

function directorShelfMarkup(primary, directorWorks, director, loading) {
  const films = directorShelfFilms(primary, directorWorks);
  const status = loading
    ? "Finding other verified films by this director…"
    : `${films.length} verified ${films.length === 1 ? "film" : "films"}.`;
  return `
    <aside
      class="director-shelf${loading ? " is-loading" : ""}"
      data-director-shelf
      data-primary-film-id="${escapeHtml(primary.id)}"
      aria-label="Films directed by ${escapeHtml(director)}"
    >
      <header class="director-shelf-head">
        <div>
          <span>Director filmography</span>
          <h3>${escapeHtml(director)}</h3>
        </div>
        <small data-film-shelf-count>${films.length} ${films.length === 1 ? "film" : "films"}</small>
      </header>
      <div class="director-shelf-stage" data-film-shelf>
        ${directorShelfFilmsMarkup(primary, films, loading)}
      </div>
      <footer class="director-shelf-foot">
        <p data-film-shelf-status role="status" aria-live="polite">${escapeHtml(status)}</p>
        <button class="hidden" type="button" data-retry-director-shelf>Try again</button>
      </footer>
    </aside>`;
}

function directorShelfFilmsMarkup(primary, films, loading) {
  const cards = films.map((film, index) => {
    const selected = film.id === primary.id;
    const title = film.title || film.original_title || "Untitled";
    const year = filmYearLabel(film);
    const poster = safeHttpUrl(film.poster_url);
    const opening = selected
      ? '<article class="director-film-card is-selected" aria-current="true">'
      : `<button class="director-film-card" type="button" data-select-film-id="${escapeHtml(film.id)}" aria-label="Select ${escapeHtml(title)}, ${escapeHtml(year)}">`;
    const closing = selected ? "</article>" : "</button>";
    return `<li class="director-film-slot">
      ${opening}
        <span class="director-film-cover">
          <span class="director-film-fallback" aria-hidden="true"><b>FR</b><span>${escapeHtml(title)}</span><small>${escapeHtml(year)}</small></span>
          ${poster ? `<img src="${escapeHtml(poster)}" alt="" loading="eager" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()" />` : ""}
          <i aria-hidden="true">${String(index + 1).padStart(2, "0")}</i>
        </span>
        <span class="director-film-copy">
          <strong>${escapeHtml(title)}</strong>
          <small>${escapeHtml(year)}${selected ? " · Selected" : ""}</small>
        </span>
      ${closing}
    </li>`;
  });
  if (loading) {
    cards.push(...Array.from({ length: 5 }, (_, index) => `
      <li class="director-film-slot is-skeleton" aria-hidden="true">
        <span class="director-film-card">
          <span class="director-film-cover"><i>${String(films.length + index + 1).padStart(2, "0")}</i></span>
          <span class="director-film-copy"><strong></strong><small></small></span>
        </span>
      </li>`));
  }
  return `<ol class="director-film-list">${cards.join("")}</ol>`;
}

function displayableFilms(films) {
  return uniqueFilms(films).flatMap((film) => {
    const candidateTitles = [film?.title, film?.original_title, ...(film?.alternative_titles || [])];
    const title = candidateTitles.find((value) => {
      const text = String(value || "").trim();
      return text && !/^Q\d+$/i.test(text);
    });
    return film?.id && title ? [{ ...film, title: String(title).trim() }] : [];
  });
}

async function onFilmResultClick(event) {
  if (event.target.closest("[data-retry-discovery]")) {
    refs.discoveryForm.requestSubmit();
    return;
  }
  if (event.target.closest("[data-relax-discovery-filters]")) {
    refs.filmYear.value = "";
    refs.filmDirector.value = "";
    refs.discoveryForm.requestSubmit();
    return;
  }
  if (event.target.closest("[data-edit-discovery-query]")) {
    refs.filmTitle.focus();
    refs.filmTitle.select();
    return;
  }
  const identityChoice = event.target.closest("[data-confirm-film-index]");
  if (identityChoice) {
    confirmDiscoveryFilm(Number(identityChoice.dataset.confirmFilmIndex));
    return;
  }
  if (event.target.closest("[data-retry-director-shelf]")) {
    retryDirectorShelf();
    return;
  }
  const selection = event.target.closest("[data-select-film-id]");
  if (selection) {
    selectArchiveFilm(selection.dataset.selectFilmId);
    return;
  }
  const button = event.target.closest("[data-film-id]");
  if (!button) return;
  await loadFilmDetail(button.dataset.filmId);
}

function selectArchiveFilm(filmId) {
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
  cancelDeepStudyRequest();
  const remaining = uniqueFilms(available, [selected]);
  state.discovery.selectedFilm = null;
  state.discovery.detailFilmId = null;
  refs.filmDetail.classList.add("hidden");
  renderFilmArchive(selected, [], remaining, true);
  void loadRelatedFilms(selected, remaining);
}

async function loadFilmDetail(filmId, options = {}) {
  cancelDeepStudyRequest();
  state.discovery.detailFilmId = filmId;
  state.discovery.selectedFilm = null;
  persistDiscoverySession();
  refs.filmDetail.classList.remove("hidden");
  refs.filmDetail.setAttribute("aria-busy", "true");
  refs.filmDetail.innerHTML = fetchProgressMarkup("Building the film dossier…");
  if (options.scroll !== false) {
    refs.filmDetail.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  try {
    const res = await fetch(`${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(filmId)}`);
    if (!res.ok) throw new Error(await readApiError(res));
    const data = await res.json();
    state.discovery.selectedFilm = data.film;
    state.discovery.activeCriticismProvider = firstLoadedCriticismRoute(
      data.film.critical_research?.bundles || {},
    );
    renderFilmDetail(data.film);
    persistDiscoverySession();
    loadFilmReception(data.film);
    if (options.scroll !== false) {
      window.requestAnimationFrame(() => {
        refs.filmDetail.scrollIntoView({ behavior: "smooth", block: "start" });
        refs.filmDetail.querySelector("[data-dossier-heading]")?.focus({ preventScroll: true });
      });
    }
  } catch (err) {
    console.warn("Film dossier request did not complete", err);
    state.discovery.selectedFilm = null;
    state.discovery.detailFilmId = filmId;
    persistDiscoverySession();
    refs.filmDetail.innerHTML = `<button class="detail-close" type="button" data-detail-close aria-label="Close film dossier">×</button>
      <div class="interface-state is-error" role="alert" tabindex="-1" data-interface-state>
        <span>Film dossier</span>
        <h3>The selected film could not be opened.</h3>
        <p>The verified film ID is unchanged. Check the catalogue connection, then retry this dossier.</p>
        <button type="button" data-retry-film-detail="${escapeHtml(filmId)}">Try opening again</button>
      </div>`;
    focusInterfaceState(refs.filmDetail);
  } finally {
    refs.filmDetail.setAttribute("aria-busy", "false");
  }
}

function renderFilmDetail(film) {
  const directors = displayCrew(film.credits?.directors || film.directors || []);
  const writers = displayCrew(film.credits?.writers || []);
  const producers = displayCrew(film.credits?.producers || []);
  const cinematographers = displayCrew(film.credits?.cinematographers || []);
  const editors = displayCrew(film.credits?.editors || []);
  const genres = (film.genres || []).join(" · ") || "Not supplied";
  const backdrop = film.backdrop_url
    ? `<img class="detail-backdrop" src="${escapeHtml(film.backdrop_url)}" alt="" />`
    : "";
  const originalTitle = film.original_title && film.original_title !== film.title
    ? `<p class="detail-original">${escapeHtml(film.original_title)}</p>`
    : "";
  const overviewMarkup = detailOverviewMarkup(film.overview);
  const reviews = Array.isArray(film.reviews) ? film.reviews : [];
  const sourceUrl = safeHttpUrl(film.source?.url);
  const overviewSourceUrl = safeHttpUrl(film.overview_source?.url);
  const overviewSourceName = String(film.overview_source?.name || "Source");
  const overviewSourceLicence = String(film.overview_source?.licence || "");
  const tmdbNotice = String(film.source?.name || "").toLocaleLowerCase() === "tmdb"
    ? '<p class="detail-attribution">This product uses the TMDB API but is not endorsed or certified by TMDB.</p>'
    : "";
  const criticalResearch = film.critical_research || {};
  const doubanStatus = criticalResearch.providers?.douban || {};
  const letterboxdStatus = criticalResearch.providers?.letterboxd || {};
  const criticalBundles = criticalResearch.bundles || (
    criticalResearch.bundle ? { [String(criticalResearch.bundle.provider || "source").toLowerCase()]: criticalResearch.bundle } : {}
  );
  const activeCriticismProvider = state.discovery.activeCriticismProvider
    || firstLoadedCriticismRoute(criticalBundles);
  state.discovery.activeCriticismProvider = activeCriticismProvider;
  const activeCriticalBundle = criticismBundleForRoute(criticalBundles, activeCriticismProvider);
  const criticismSourceAvailability = {
    crossref: true,
    douban: Boolean(doubanStatus.installed),
    "letterboxd-web": true,
    "guardian-web": true,
    letterboxd: Boolean(letterboxdStatus.configured),
  };
  const videoBundle = film.video_sources?.bundle || null;
  const videoCount = Array.isArray(videoBundle?.videos) ? videoBundle.videos.length : 0;
  const criticalSourceCount = Object.values(criticalBundles).reduce(
    (total, bundle) => total + (Array.isArray(bundle?.reviews) ? bundle.reviews.length : 0),
    0,
  );
  const factsOpen = window.matchMedia("(min-width: 641px)").matches ? " open" : "";

  refs.filmDetail.innerHTML = `
    <div class="detail-hero">
      <button class="detail-close" type="button" data-detail-close aria-label="Close film dossier">×</button>
      ${backdrop}
      <div class="detail-copy">
        <p class="eyebrow">Study dossier / ${escapeHtml(filmYearLabel(film))}</p>
        <h2 tabindex="-1" data-dossier-heading>${escapeHtml(film.title || "Untitled")}</h2>
        ${originalTitle}
        <div class="detail-actions">
          ${runtimeConfig.videoAnalysisEnabled
            ? '<button class="detail-action primary" type="button" data-analyse-film>Analyse a clip</button>'
            : '<button class="detail-action primary" type="button" disabled>Video analysis · coming soon</button>'}
          ${runtimeConfig.accountUi ? '<button class="detail-action" type="button" data-save-film>Save to account</button>' : ""}
          ${sourceUrl ? `<a class="detail-action" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">View source ↗</a>` : ""}
        </div>
        ${overviewMarkup}
        ${overviewSourceUrl ? `<p class="detail-attribution">Overview: <a href="${escapeHtml(overviewSourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(overviewSourceName)}${overviewSourceLicence ? ` · ${escapeHtml(overviewSourceLicence)}` : ""} ↗</a></p>` : ""}
        ${tmdbNotice}
        ${filmReceptionMarkup(film.awards || [])}
      </div>
      <details class="detail-facts"${factsOpen}>
        <summary>Credits &amp; film facts</summary>
        <div class="detail-facts-list">
          ${detailFact("Director", directors)}
          ${detailFact("Written by", writers)}
          ${detailFact("Produced by", producers)}
          ${detailFact("Cinematography", cinematographers)}
          ${detailFact("Edited by", editors)}
          ${detailFact("Runtime", film.runtime_minutes ? `${film.runtime_minutes} minutes` : "Not supplied")}
          ${detailFact("Genres", genres)}
          ${crewSourcesMarkup(film.crew_sources)}
        </div>
      </details>
    </div>
    <nav class="study-paths" aria-label="Film dossier sections">
      <a class="study-path" href="#dossier-watch">
        <span>01</span><h3>Watch &amp; verify</h3>
        <p>${videoCount ? `${videoCount} cached video source${videoCount === 1 ? "" : "s"}` : "Find interviews, lectures and film-study video"}</p>
      </a>
      <a class="study-path" href="#dossier-criticism">
        <span>02</span><h3>Read perspectives</h3>
        <p>${criticalSourceCount ? `${criticalSourceCount} attributed source${criticalSourceCount === 1 ? "" : "s"} ready` : "Compare attributed criticism and reported claims"}</p>
      </a>
      <a class="study-path" href="#dossier-study">
        <span>03</span><h3>Build the study</h3>
        <p>Turn evidence into precise hypotheses for close viewing</p>
      </a>
    </nav>
    <section id="dossier-watch" class="film-videos">
      <div class="film-videos-head">
        <div class="dossier-section-copy">
          <span>01 · Viewing context</span>
          <h3>Watch &amp; study</h3>
          <p>Use interviews, lectures and essays as attributed context—not direct proof of what the film does.</p>
        </div>
        <button type="button" data-load-film-videos>${videoBundle ? "Find more videos" : "Find relevant videos"}</button>
      </div>
      <div data-film-videos-output aria-busy="false">
        ${videoBundle
          ? filmVideosMarkup(videoBundle)
          : videoProviderStatusMarkup(film.video_sources?.providers)}
      </div>
    </section>
    <section id="dossier-criticism" class="critical-perspectives">
      <div class="critical-head">
        <div class="dossier-section-copy">
          <span>02 · Attributed interpretation</span>
          <h3>Critical perspectives</h3>
          <p>Compare who reports each interpretation before using it to shape a viewing question.</p>
        </div>
        ${criticismSourceTabsMarkup(
          criticalBundles,
          activeCriticismProvider,
          criticismSourceAvailability,
        )}
      </div>
      <div id="dossier-criticism-panel" role="tabpanel" aria-label="Selected criticism source" data-critical-output aria-busy="false">
        ${activeCriticalBundle ? criticalResearchMarkup(activeCriticalBundle) : '<p class="module-empty">No criticism source is loaded yet. Choose a provider above to fetch attributed material for this exact film.</p>'}
      </div>
    </section>
    <section id="dossier-study" class="deep-study">
      <div class="deep-study-head">
        <div class="dossier-section-copy">
          <span>03 · Evidence-grounded synthesis</span>
          <h3>Deep Study</h3>
          <p>Choose a formal focus, then build an inspectable reading from the evidence currently available.</p>
        </div>
        <button class="study-cancel hidden" type="button" data-cancel-study>Stop waiting</button>
      </div>
      <div class="study-prompt-row">
        <textarea data-study-question rows="2" maxlength="500" aria-label="Optional focus for Deep Study" placeholder="Optional focus — for example: spatial hierarchy, cutting rhythm, or point of view"></textarea>
        <button type="button" data-generate-study>Generate study</button>
      </div>
      <div class="deep-study-output" data-study-output aria-busy="false"></div>
    </section>
    ${reviews.length ? `<div class="reviews-section"><h3>Perspectives</h3><div class="review-grid">${reviews.map(reviewCard).join("")}</div></div>` : ""}`;
  updateDeepStudyAuthState();
  updateSavedFilmButton();
}

function videoProviderStatusMarkup(providers = {}) {
  if (window.FirstRollIntegrations?.configured?.("youtube")) {
    return '<p class="module-empty">Personal YouTube search is ready for this browser tab.</p>';
  }
  const youtubeReady = providers?.youtube?.state === "ready";
  const bilibiliReady = providers?.bilibili?.state === "ready";
  if (youtubeReady && bilibiliReady) {
    return '<p class="module-empty">Video search is ready. Choose “Find relevant videos” to retrieve identity-matched viewing context.</p>';
  }
  if (!youtubeReady && bilibiliReady) {
    return '<p class="module-empty">YouTube search is not configured on this server yet. Bilibili results remain available, with strict film-identity matching.</p>';
  }
  return '<p class="module-empty">Public video providers are not configured on this server yet.</p>';
}

function displayCrewNames(values) {
  const forbidden = /mw-parser-output|\.mw-|line-height|list-style|margin:|padding:|display:|font-size:|@media|!important|var\(|[{}<>]/i;
  const names = (Array.isArray(values) ? values : [])
    .filter((value) => typeof value === "string")
    .map((value) => value.trim())
    .filter((value) => value.length >= 2 && value.length <= 120)
    .filter((value) => !/^Q\d+$/i.test(value))
    .filter((value) => /\p{L}/u.test(value) && !forbidden.test(value))
    .filter((value) => (value.match(/[,:;]/g) || []).length <= 2);
  return [...new Set(names)];
}

function displayCrew(values, fallback = "Not supplied") {
  return displayCrewNames(values).join(", ") || fallback;
}

function firstCrewName(values, fallback = "Not supplied") {
  return displayCrewNames(values)[0] || fallback;
}

function detailOverviewMarkup(value) {
  const overview = String(value || "No synopsis is available from this source.").trim();
  const limit = 460;
  if (overview.length <= limit) {
    return `<div class="detail-synopsis"><span>Catalogue synopsis</span><p class="detail-overview">${escapeHtml(overview)}</p></div>`;
  }
  const clipped = overview
    .slice(0, limit)
    .replace(/\s+\S*$/, "")
    .trim();
  return `<div class="detail-synopsis">
    <span>Catalogue synopsis</span>
    <p class="detail-overview">${escapeHtml(clipped)}…</p>
    <details class="detail-overview-more">
      <summary>Read the full attributed synopsis</summary>
      <p>${escapeHtml(overview)}</p>
    </details>
  </div>`;
}

function detailFact(label, value) {
  return `<div class="detail-fact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function filmReceptionMarkup(awards) {
  const items = Array.isArray(awards) ? awards.slice(0, 3) : [];
  return `<section class="detail-reception" data-film-reception>
    <div class="reception-scores" data-reception-scores aria-live="polite">
      <h3>Reception</h3>
      <div class="reception-loading" role="status" aria-label="Loading ratings"><i></i><i></i><i></i></div>
    </div>
    <div class="reception-awards" data-reception-awards>
      ${items.length ? `<h3>Awards</h3><div>${items.map(awardMarkup).join("")}</div>` : ""}
    </div>
  </section>`;
}

function awardMarkup(award) {
  const url = safeHttpUrl(award.url);
  const name = escapeHtml(award.name || "Film award");
  const title = url
    ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${name} ↗</a>`
    : `<strong>${name}</strong>`;
  return `<article>${title}<p>${escapeHtml(award.description || "")}</p></article>`;
}

async function loadFilmReception(film) {
  const section = refs.filmDetail.querySelector("[data-film-reception]");
  const output = refs.filmDetail.querySelector("[data-reception-scores]");
  if (!section || !output || !film?.id) return;
  try {
    const response = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/reception`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const reception = await response.json();
    const scores = Array.isArray(reception.scores) ? reception.scores : [];
    if (!scores.length) {
      output.innerHTML = "";
      if (!section.querySelector(".reception-awards article")) section.classList.add("hidden");
      return;
    }
    section.classList.remove("hidden");
    const aggregate = reception.aggregate;
    const doubanUnavailable = reception.providers?.douban?.installed === false;
    output.innerHTML = `<h3>Reception</h3><div class="score-grid">
      ${aggregate ? `<article class="score-card aggregate"><span>Combined</span><strong>${escapeHtml(formatRating(aggregate.score))}</strong><small>/ 100 · ${escapeHtml(aggregate.method)}</small></article>` : ""}
      ${scores.map((score) => `<article class="score-card"><span>${escapeHtml(score.provider)}</span><strong>${escapeHtml(formatRating(score.score))}</strong><small>/ ${escapeHtml(score.scale)}${score.votes ? ` · ${escapeHtml(formatCompactCount(score.votes))} ratings` : ""}</small></article>`).join("")}
    </div>${doubanUnavailable ? '<p class="reception-provider-note">Douban is not connected on this hosted server yet.</p>' : ""}`;
  } catch (_) {
    output.innerHTML = "";
    if (!section.querySelector(".reception-awards article")) section.classList.add("hidden");
  }
}

function formatRating(value) {
  const number = Number(value);
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function formatCompactCount(value) {
  return new Intl.NumberFormat("en-GB", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function crewSourcesMarkup(sources) {
  const usable = (Array.isArray(sources) ? sources : []).filter((source) => safeHttpUrl(source?.url));
  if (!usable.length) return "";
  return `<div class="crew-provenance"><span>Crew sources</span><p>${usable.map((source) => `<a href="${escapeHtml(safeHttpUrl(source.url))}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.name || "Source")} ↗</a>`).join(" · ")}</p></div>`;
}

function reviewCard(review) {
  const url = safeHttpUrl(review.url);
  return `
    <article class="review-card">
      <div class="review-head"><strong>${escapeHtml(review.author || "Community member")}</strong><span>${escapeHtml(review.source?.name || "Source-labelled")}</span></div>
      <p>${escapeHtml(review.excerpt || "No excerpt supplied.")}</p>
      ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Read at source ↗</a>` : ""}
    </article>`;
}

async function onFilmDetailClick(event) {
  if (event.target.closest("[data-detail-close]")) {
    cancelDeepStudyRequest();
    state.discovery.selectedFilm = null;
    state.discovery.detailFilmId = null;
    refs.filmDetail.classList.add("hidden");
    refs.filmDetail.innerHTML = "";
    persistDiscoverySession();
    return;
  }
  const detailRetry = event.target.closest("[data-retry-film-detail]");
  if (detailRetry) {
    await loadFilmDetail(detailRetry.dataset.retryFilmDetail);
    return;
  }
  const citation = event.target.closest("[data-study-citation-target]");
  if (citation) {
    event.preventDefault();
    const target = document.getElementById(citation.dataset.studyCitationTarget);
    if (target) {
      if (target.tagName === "DETAILS") target.open = true;
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      focusElement(target, { preventScroll: true });
    }
    return;
  }
  if (event.target.closest("[data-analyse-film]")) {
    const film = state.discovery.selectedFilm;
    refs.analyseContext.textContent = film
      ? `Selected: ${film.title}`
      : "";
    refs.analyseContext.classList.toggle("hidden", !film);
    setProductView("analyse");
    refs.videoFile.focus();
    return;
  }
  const saveButton = event.target.closest("[data-save-film]");
  if (saveButton) {
    await toggleSavedFilm(saveButton);
    return;
  }
  if (event.target.closest("[data-cancel-study]")) {
    cancelDeepStudyRequest({ announce: true });
    return;
  }
  const studyRetry = event.target.closest("[data-retry-study]");
  if (studyRetry) {
    const studyButton = refs.filmDetail.querySelector("[data-generate-study]");
    if (studyButton) await generateDeepStudy(studyButton);
    return;
  }
  const studyButton = event.target.closest("[data-generate-study]");
  if (studyButton) {
    await generateDeepStudy(studyButton);
    return;
  }
  const videoRetry = event.target.closest("[data-retry-film-videos]");
  if (videoRetry) {
    const videoButton = refs.filmDetail.querySelector("[data-load-film-videos]");
    if (videoButton) await loadFilmVideos(videoButton);
    return;
  }
  const videoButton = event.target.closest("[data-load-film-videos]");
  if (videoButton) {
    await loadFilmVideos(videoButton);
    return;
  }
  const videoCategoryButton = event.target.closest("[data-video-category]");
  if (videoCategoryButton) {
    selectVideoCategory(videoCategoryButton);
    return;
  }
  const criticismSourceButton = event.target.closest("[data-criticism-source]");
  if (criticismSourceButton) {
    await selectCriticismSource(criticismSourceButton);
    return;
  }
  const criticismRetry = event.target.closest("[data-retry-criticism]");
  if (criticismRetry) {
    const provider = criticismRetry.dataset.retryCriticism;
    const providerButton = refs.filmDetail.querySelector(
      `[data-criticism-source="${CSS.escape(provider)}"]`,
    );
    if (providerButton) await loadProviderCriticism(providerButton, provider);
    return;
  }
  const criticismRefreshButton = event.target.closest("[data-refresh-criticism]");
  if (criticismRefreshButton) {
    await loadProviderCriticism(
      criticismRefreshButton,
      criticismRefreshButton.dataset.refreshCriticism,
    );
    return;
  }
  const structureButton = event.target.closest("[data-structure-criticism]");
  if (structureButton) {
    await structureProviderCriticism(structureButton.dataset.structureCriticism, structureButton);
  }
}

function onFilmDetailKeydown(event) {
  const tab = event.target.closest('[role="tab"]');
  const tablist = tab?.closest('[role="tablist"]');
  if (!tab || !tablist || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
    return;
  }
  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]:not(:disabled)'));
  const current = tabs.indexOf(tab);
  if (current < 0 || !tabs.length) return;
  event.preventDefault();
  const nextIndex = event.key === "Home"
    ? 0
    : event.key === "End"
      ? tabs.length - 1
      : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  tabs[nextIndex].focus();
  tabs[nextIndex].click();
}

async function toggleSavedFilm(button) {
  const film = state.discovery.selectedFilm;
  if (!film) return;
  if (!window.FirstRollAuth?.currentUser?.()) {
    window.FirstRollAuth?.open?.("sign-in");
    return;
  }
  button.disabled = true;
  try {
    if (window.FirstRollAuth.isFilmSaved(film.id)) {
      await window.FirstRollAuth.removeSavedFilm(film.id);
    } else {
      await window.FirstRollAuth.saveFilm(film);
    }
    updateSavedFilmButton();
  } catch (error) {
    button.textContent = error?.message || "Could not update saved films";
  } finally {
    button.disabled = false;
  }
}

async function loadFilmVideos(button) {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-film-videos-output]");
  if (!film || !output) return;
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Searching…";
  output.setAttribute("aria-busy", "true");
  output.innerHTML = fetchProgressMarkup(videoButtonProgressLabel(Boolean(film.video_sources?.bundle)));
  try {
    const authorisation = await window.FirstRollAuth?.authorisationHeaders?.() || {};
    const integration = window.FirstRollIntegrations?.requestHeaders?.("youtube") || {};
    const response = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/videos`,
      { method: "POST", headers: { ...authorisation, ...integration } },
    );
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    film.video_sources = film.video_sources || {};
    film.video_sources.bundle = data.video_sources;
    output.innerHTML = filmVideosMarkup(data.video_sources);
    focusInterfaceState(output);
    button.textContent = "Find more videos";
  } catch (error) {
    console.warn("Video source request did not complete", error);
    output.innerHTML = `<div class="interface-state is-error is-compact" role="alert" tabindex="-1" data-interface-state>
      <span>Viewing context</span>
      <h4>Video search could not finish.</h4>
      <p>The film dossier is unchanged. Check the provider connection, then retry the identity-matched search.</p>
      <button type="button" data-retry-film-videos>Try video search again</button>
    </div>`;
    button.textContent = originalLabel;
    focusInterfaceState(output);
  } finally {
    output.setAttribute("aria-busy", "false");
    button.disabled = false;
  }
}

function videoButtonProgressLabel(expanding) {
  return expanding
    ? "Searching for additional matches and merging them into the local catalogue…"
    : "Matching public videos to the verified film identity…";
}

function filmVideosMarkup(bundle) {
  const videos = Array.isArray(bundle?.videos) ? bundle.videos : [];
  if (!videos.length) return `<div class="interface-state is-compact" role="status" tabindex="-1" data-interface-state>
    <span>Viewing context</span>
    <h4>No identity-matched videos were found.</h4>
    <p>Nothing has been added to the evidence layer. You can retry later without changing the dossier.</p>
    <button type="button" data-retry-film-videos>Try video search again</button>
  </div>`;
  const categories = [...new Set(videos.map((video) => video.category || "other"))];
  return `${videoCategoryTabsMarkup(categories)}
  <div id="dossier-video-panel" class="film-video-grid" role="tabpanel" aria-labelledby="video-category-tab-0" data-video-category-panel>
    ${videos.map(filmVideoCardMarkup).join("")}
  </div>
  <p class="video-source-boundary">${escapeHtml(bundle.notice || "Third-party videos are attributed but their claims are not verified by FirstRoll.")}</p>`;
}

function videoCategoryTabsMarkup(categories) {
  const tabs = ["all", ...categories];
  return `<div class="critical-provider-actions video-category-tabs" role="tablist" aria-label="Video categories">
    ${tabs.map((category, index) => `<button id="video-category-tab-${index}" type="button" role="tab" class="${index === 0 ? "is-active" : ""}" aria-selected="${index === 0}" aria-controls="dossier-video-panel" tabindex="${index === 0 ? "0" : "-1"}" data-video-category="${escapeHtml(category)}">${escapeHtml(category === "all" ? "All" : videoCategoryLabel(category))}</button>`).join("")}
  </div>`;
}

function selectVideoCategory(button) {
  const output = button.closest("[data-film-videos-output]");
  if (!output) return;
  const selected = button.dataset.videoCategory || "all";
  output.querySelectorAll("[data-video-category]").forEach((tab) => {
    const active = tab === button;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.setAttribute("tabindex", active ? "0" : "-1");
  });
  output.querySelector("[data-video-category-panel]")?.setAttribute("aria-labelledby", button.id);
  output.querySelectorAll("[data-video-category-card]").forEach((card) => {
    card.hidden = selected !== "all" && card.dataset.videoCategoryCard !== selected;
  });
}

function filmVideoCardMarkup(video) {
  const embedUrl = safeVideoEmbedUrl(video.embed_url);
  const sourceUrl = safeHttpUrl(video.url);
  if (!embedUrl || !sourceUrl) return "";
  const relevance = String(video.relevance || "title").replaceAll("_", " + ");
  const category = videoCategoryLabel(video.category);
  const duration = Number.isFinite(Number(video.duration_seconds))
    ? ` · ${formatTime(Number(video.duration_seconds))}`
    : "";
  return `<article class="film-video-card" data-video-category-card="${escapeHtml(video.category || "other")}">
    <div class="film-video-frame">
      <iframe
        src="${escapeHtml(embedUrl)}"
        title="${escapeHtml(video.title || `${video.platform} video`)}"
        loading="lazy"
        referrerpolicy="strict-origin-when-cross-origin"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen></iframe>
    </div>
    <div class="film-video-copy">
      <span>${escapeHtml(category)} · ${escapeHtml(video.platform || "Video")}${escapeHtml(duration)}</span>
      <h4>${escapeHtml(video.title || "Untitled video")}</h4>
      <small>Matched by ${escapeHtml(relevance)}</small>
      ${video.creator ? `<p>${escapeHtml(video.creator)}</p>` : ""}
      <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Open at source ↗</a>
    </div>
  </article>`;
}

function videoCategoryLabel(value) {
  const labels = {
    full_film: "Full film",
    interview: "Interview",
    video_essay: "Review",
    lecture: "Lecture",
    trailer: "Trailer",
    scene_extract: "Scene / extract",
    behind_the_scenes: "Behind the scenes",
    other: "Other",
  };
  return labels[value] || labels.other;
}

async function selectCriticismSource(button) {
  const provider = button.dataset.criticismSource;
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-critical-output]");
  if (!film || !output || !provider) return;
  state.discovery.activeCriticismProvider = provider;
  updateCriticismSourceTabs(provider);
  const bundle = criticismBundleForRoute(film.critical_research?.bundles || {}, provider);
  if (bundle) {
    output.innerHTML = criticalResearchMarkup(bundle);
    return;
  }
  await loadProviderCriticism(button, provider);
}

async function loadProviderCriticism(button, providerOverride = null) {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-critical-output]");
  if (!film || !output) return;
  const provider = providerOverride || button.dataset.criticismSource;
  const source = criticismSource(provider);
  const providerLabel = source?.label || "Source";
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = button.dataset.criticismSource ? `${providerLabel} · Fetching` : "Refreshing…";
  if (state.discovery.activeCriticismProvider === provider) {
    output.setAttribute("aria-busy", "true");
    output.innerHTML = fetchProgressMarkup(`Fetching ${providerLabel}…`);
  }
  try {
    const response = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/criticism/${provider}`,
      { method: "POST" },
    );
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const bundle = data.critical_research;
    const research = state.discovery.selectedFilm.critical_research;
    research.bundles = research.bundles || {};
    research.bundles[String(bundle.provider || provider).toLowerCase()] = bundle;
    if (state.discovery.activeCriticismProvider === provider) {
      output.innerHTML = criticalResearchMarkup(bundle);
    }
    updateCriticismSourceTabs(state.discovery.activeCriticismProvider);
    if (!runtimeConfig.publicMode) {
      const structureButton = state.discovery.activeCriticismProvider === provider
        ? output.querySelector(`[data-structure-criticism="${provider}"]`)
        : null;
      await structureProviderCriticism(provider, structureButton);
    }
  } catch (error) {
    console.warn("Criticism source request did not complete", error);
    if (state.discovery.activeCriticismProvider === provider) {
      output.innerHTML = `<div class="interface-state is-error is-compact" role="alert" tabindex="-1" data-interface-state>
        <span>${escapeHtml(providerLabel)} criticism</span>
        <h4>This source could not be fetched.</h4>
        <p>Other evidence remains available. Retry this provider without changing the selected film.</p>
        <button type="button" data-retry-criticism="${escapeHtml(provider)}">Try ${escapeHtml(providerLabel)} again</button>
      </div>`;
      focusInterfaceState(output);
    }
  } finally {
    output.setAttribute("aria-busy", "false");
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

async function structureProviderCriticism(provider, button = null) {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-critical-output]");
  if (!film || !output || !provider) return;
  const status = output.querySelector(`[data-structure-status="${provider}"]`);
  if (button) {
    button.disabled = true;
    button.textContent = "Structuring…";
  }
  if (status && state.discovery.activeCriticismProvider === provider) {
    status.className = "critical-stage-status";
    status.textContent = "Reviews are cached. DeepSeek is structuring them in small validated batches…";
  }
  if (state.discovery.activeCriticismProvider === provider) {
    output.setAttribute("aria-busy", "true");
    output.querySelector("[data-active-fetch-progress]")?.remove();
    output.insertAdjacentHTML("afterbegin", fetchProgressMarkup("DeepSeek is structuring the fetched reviews…"));
  }
  try {
    const response = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/criticism/${provider}/structure`,
      { method: "POST" },
    );
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const bundle = data.critical_research;
    const research = state.discovery.selectedFilm.critical_research;
    research.bundles = research.bundles || {};
    research.bundles[String(bundle.provider || provider).toLowerCase()] = bundle;
    if (state.discovery.activeCriticismProvider === provider) {
      output.innerHTML = criticalResearchMarkup(bundle);
    }
  } catch (error) {
    console.warn("Criticism structuring did not complete", error);
    if (state.discovery.activeCriticismProvider !== provider) return;
    output.querySelector("[data-active-fetch-progress]")?.remove();
    const currentStatus = output.querySelector(`[data-structure-status="${provider}"]`);
    if (currentStatus) {
      currentStatus.className = "critical-stage-status is-error";
      currentStatus.setAttribute("role", "alert");
      currentStatus.setAttribute("tabindex", "-1");
      currentStatus.textContent = "Reviews remain available, but DeepSeek could not return validated claims. Retry once or continue with the attributed source text.";
      focusElement(currentStatus);
    } else {
      output.insertAdjacentHTML("afterbegin", '<p class="critical-stage-status is-error" role="alert" tabindex="-1" data-interface-state>Reviews and previous claims remain available, but DeepSeek could not return validated claims. Retry once or continue with the attributed source text.</p>');
      focusInterfaceState(output);
    }
    if (button) {
      button.disabled = false;
      button.textContent = "Retry DeepSeek";
    }
  } finally {
    output.setAttribute("aria-busy", "false");
  }
}

function criticalResearchMarkup(bundle) {
  const claims = Array.isArray(bundle?.claims) ? bundle.claims : [];
  const reviews = Array.isArray(bundle?.reviews) ? bundle.reviews : [];
  const reviewMap = Object.fromEntries(reviews.map((review) => [review.source_id, review]));
  const route = criticismProviderRoute(bundle?.provider);
  const pending = bundle?.claim_status === "pending";
  const canStructure = !runtimeConfig.publicMode;
  return `
    <div class="critical-source-row">
      <div class="critical-source-heading">${escapeHtml(bundle.provider || "Attributed source")}</div>
      <div class="critical-source-actions">
        ${route ? `<button type="button" data-refresh-criticism="${escapeHtml(route)}">Refresh source</button>` : ""}
        ${route && canStructure ? `<button type="button" data-structure-criticism="${escapeHtml(route)}">${pending ? "Structure with DeepSeek" : "Refresh structured claims"}</button>` : ""}
      </div>
    </div>
    ${reviews.length ? rawReviewMarkup(reviews, bundle.provider, pending) : `<p class="module-empty">No attributed review text was fetched.</p>`}
    ${pending ? `<p class="critical-stage-status" data-structure-status="${escapeHtml(route)}">${canStructure ? "Reviews are cached locally. Structured claims are pending." : "Attributed reviews are ready. Deep Study can develop a separate evidence-grounded analysis."}</p>` : ""}
    ${claims.length ? `<div class="critical-grid">${claims.map((claim) => criticalClaimMarkup(claim, reviewMap[claim.source_id], bundle.provider)).join("")}</div>` : ""}
    ${!pending && !claims.length ? `<p class="module-empty">DeepSeek found no substantive claims in the supplied review text.</p>` : ""}
    <p class="critical-boundary">${escapeHtml(bundle.notice || "Secondary criticism; not verified film observation.")}</p>`;
}

function criticismProviderRoute(provider) {
  const value = String(provider || "").toLowerCase();
  if (value === "douban") return "douban";
  if (value === "letterboxd") return "letterboxd";
  if (value === "letterboxd public web") return "letterboxd-web";
  if (value === "the guardian public web") return "guardian-web";
  if (value === "crossref scholarship") return "crossref";
  return "";
}

function criticismSource(route) {
  return CRITICISM_SOURCES.find((source) => source.route === route) || null;
}

function criticismBundleForRoute(bundles, route) {
  if (!route) return null;
  return Object.values(bundles || {}).find(
    (bundle) => bundle && criticismProviderRoute(bundle.provider) === route,
  ) || null;
}

function firstLoadedCriticismRoute(bundles) {
  return CRITICISM_SOURCES.find(
    (source) => criticismBundleForRoute(bundles, source.route),
  )?.route || null;
}

function criticismSourceTabsMarkup(bundles, activeProvider, availability) {
  const visibleSources = CRITICISM_SOURCES.filter(
    (source) => Boolean(criticismBundleForRoute(bundles, source.route))
      || availability[source.route] === true,
  );
  if (!visibleSources.length) return "";
  const selectedProvider = activeProvider || visibleSources[0].route;
  return `<div class="critical-provider-actions" role="tablist" aria-label="Criticism sources">
    ${visibleSources.map((source) => {
      const loaded = Boolean(criticismBundleForRoute(bundles, source.route));
      const active = source.route === selectedProvider;
      return `<button id="criticism-tab-${escapeHtml(source.route)}" type="button" role="tab" class="${active ? "is-active" : ""} ${loaded ? "is-loaded" : ""}" aria-selected="${active}" aria-controls="dossier-criticism-panel" tabindex="${active ? "0" : "-1"}" data-criticism-source="${escapeHtml(source.route)}">${escapeHtml(source.label)}</button>`;
    }).join("")}
  </div>`;
}

function updateCriticismSourceTabs(activeProvider) {
  const film = state.discovery.selectedFilm;
  const bundles = film?.critical_research?.bundles || {};
  refs.filmDetail.querySelectorAll("[data-criticism-source]").forEach((button) => {
    const active = button.dataset.criticismSource === activeProvider;
    const loaded = Boolean(criticismBundleForRoute(bundles, button.dataset.criticismSource));
    button.classList.toggle("is-active", active);
    button.classList.toggle("is-loaded", loaded);
    button.setAttribute("aria-selected", String(active));
    button.setAttribute("tabindex", active ? "0" : "-1");
  });
  const activeTab = refs.filmDetail.querySelector(
    `[data-criticism-source="${CSS.escape(activeProvider)}"]`,
  );
  const panel = refs.filmDetail.querySelector("#dossier-criticism-panel");
  if (activeTab && panel) {
    panel.setAttribute("aria-labelledby", activeTab.id);
    panel.removeAttribute("aria-label");
  }
}

function rawReviewMarkup(reviews, provider, open) {
  return `<details class="critical-raw-reviews" ${open ? "open" : ""}>
    <summary>${escapeHtml(reviews.length)} attributed source${reviews.length === 1 ? "" : "s"} fetched</summary>
    <div class="critical-raw-grid">${reviews.map((review) => {
      const url = safeHttpUrl(review.url);
      const text = String(review.summary || "");
      const visible = text.length > 1400 ? `${text.slice(0, 1400).trim()}…` : text;
      return `<article><header><strong>${escapeHtml(review.title || "Untitled review")}</strong><span>${escapeHtml(review.author || provider || "Attributed source")}${review.rating_label ? ` · ${escapeHtml(review.rating_label)}` : ""}</span></header><p lang="${escapeHtml(review.language || "und")}">${escapeHtml(visible)}</p>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Read complete source ↗</a>` : ""}</article>`;
    }).join("")}</div>
  </details>`;
}

function criticalClaimMarkup(claim, review, provider) {
  const sourceUrl = safeHttpUrl(review?.url);
  const tags = Array.isArray(claim.lens_tags) ? claim.lens_tags.map((tag) => tag.replaceAll("_", " ")).join(" · ") : "critical perspective";
  const missing = Array.isArray(claim.missing_fields) ? claim.missing_fields.map((field) => field.replaceAll("_", " ")).join(" · ") : "";
  return `<article class="critical-card">
    <header><span>${escapeHtml(claim.claim_id || "Claim")} · ${escapeHtml(tags)}</span><em>${escapeHtml(claim.extraction_confidence || "unknown")} confidence</em></header>
    <p>${escapeHtml(claim.critic_claim || "")}</p>
    ${claim.short_source_excerpt ? `<blockquote lang="${escapeHtml(review?.language || "und")}"><span>Source excerpt</span>${escapeHtml(claim.short_source_excerpt)}</blockquote>` : ""}
    ${claim.scene_or_sequence ? `<dl><dt>Sequence</dt><dd>${escapeHtml(claim.scene_or_sequence)}</dd></dl>` : ""}
    ${claim.described_observation ? `<dl><dt>Reported observation</dt><dd>${escapeHtml(claim.described_observation)}</dd></dl>` : ""}
    ${missing ? `<small>Not supplied: ${escapeHtml(missing)}</small>` : ""}
    <footer><div><strong>${escapeHtml(review?.title || `${provider || "Source"} review`)}</strong><span>${escapeHtml(review?.rating_label || "Summary")}</span></div>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Read at ${escapeHtml(provider || "source")} ↗</a>` : ""}</footer>
  </article>`;
}

function studyResponseError(response, detail) {
  const error = new Error(detail || `Deep Study returned HTTP ${response.status}.`);
  error.status = response.status;
  error.retryAfter = response.headers.get("Retry-After") || "";
  return error;
}

function deepStudyFailureMarkup(error) {
  const message = String(error?.message || "").toLocaleLowerCase();
  let title = "Deep Study could not complete.";
  let guidance = "Your film, evidence and focus are unchanged. Retry once; if the problem repeats, narrow the focus or try again later.";
  if (error?.status === 429 || message.includes("allowance") || message.includes("quota")) {
    title = "The study allowance is unavailable right now.";
    guidance = "No result was stored. Keep this focus and try again after the allowance resets or use an approved personal provider key.";
  } else if (error?.status === 401 || message.includes("sign in")) {
    title = "Sign in is required for this study.";
    guidance = "Sign in again, then retry the same focus. The current film dossier remains open.";
  } else if (message.includes("valid study") || message.includes("invalid study")) {
    title = "DeepSeek did not return a valid study.";
    guidance = "The evidence remains intact. Retry once; if validation fails again, use a narrower formal question.";
  } else if (error instanceof TypeError || message.includes("connection")) {
    title = "The study connection was interrupted.";
    guidance = "Check the connection and retry. A provider request that had already started may still count towards external usage.";
  }
  return `<div class="interface-state is-error is-inverse" role="alert" tabindex="-1" data-interface-state>
    <span>Study stopped safely</span>
    <h4>${escapeHtml(title)}</h4>
    <p>${escapeHtml(guidance)}</p>
    <button type="button" data-retry-study>Try Deep Study again</button>
  </div>`;
}

function cancelDeepStudyRequest(options = {}) {
  const controller = state.discovery.studyController;
  if (!controller) return false;
  controller.abort();
  state.discovery.studyController = null;
  state.discovery.studyRequestId += 1;
  const output = refs.filmDetail.querySelector("[data-study-output]");
  const generateButton = refs.filmDetail.querySelector("[data-generate-study]");
  const cancelButton = refs.filmDetail.querySelector("[data-cancel-study]");
  if (generateButton) {
    generateButton.disabled = false;
    generateButton.textContent = "Generate study";
  }
  cancelButton?.classList.add("hidden");
  output?.setAttribute("aria-busy", "false");
  if (options.announce && output) {
    output.innerHTML = `${researchProgressMarkup(state.discovery.studyProgress)}<div class="interface-state is-inverse" role="status" tabindex="-1" data-interface-state>
      <span>Browser request stopped</span>
      <h4>You stopped waiting for this study.</h4>
      <p>Your film, evidence and focus remain here. A provider request already in progress may still finish and consume external quota.</p>
      <button type="button" data-retry-study>Start the study again</button>
    </div>`;
    focusInterfaceState(output);
  } else {
    state.discovery.studyProgress = [];
  }
  return true;
}

async function generateDeepStudy(button) {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-study-output]");
  const cancelButton = refs.filmDetail.querySelector("[data-cancel-study]");
  const question = refs.filmDetail.querySelector("[data-study-question]")?.value.trim() || null;
  if (!film || !output) return;
  const authorisation = await window.FirstRollAuth?.authorisationHeaders?.() || {};
  if (runtimeConfig.publicMode && !authorisation.Authorization) {
    window.FirstRollAuth?.open?.();
    output.innerHTML = `<div class="interface-state is-error is-inverse" role="alert" tabindex="-1" data-interface-state>
      <span>Account required</span>
      <h4>Sign in to use Deep Study.</h4>
      <p>The selected film and focus remain ready. Complete sign-in, then generate the study again.</p>
    </div>`;
    focusInterfaceState(output);
    return;
  }

  cancelDeepStudyRequest();
  const requestId = state.discovery.studyRequestId + 1;
  const controller = new AbortController();
  state.discovery.studyRequestId = requestId;
  state.discovery.studyController = controller;
  button.disabled = true;
  button.textContent = "Studying…";
  cancelButton?.classList.remove("hidden");
  output.setAttribute("aria-busy", "true");
  state.discovery.studyProgress = [{
    sequence: 1,
    kind: "existing_evidence_loading",
    message: "Reading the film record against your cited sources…",
    elapsed_ms: 0,
    counts: {},
  }];
  output.innerHTML = researchProgressMarkup(state.discovery.studyProgress);
  const currentRequest = () => (
    state.discovery.studyRequestId === requestId
    && state.discovery.selectedFilm?.id === film.id
  );

  try {
    const integration = window.FirstRollIntegrations?.requestHeaders?.("deepseek") || {};
    let data;
    if (runtimeConfig.publicMode) {
      const streamResponse = await fetch(
        `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/study/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authorisation, ...integration },
          body: JSON.stringify({ question }),
          signal: controller.signal,
        },
      );
      if (!streamResponse.ok) {
        throw studyResponseError(streamResponse, await readApiError(streamResponse));
      }
      const runId = streamResponse.headers.get("X-FirstRoll-Run-ID");
      if (!runId) throw new Error("The research run did not return an identifier.");
      await consumeResearchProgress(streamResponse, runId, (progress) => {
        if (!currentRequest()) return;
        state.discovery.studyProgress.push(progress);
        output.innerHTML = researchProgressMarkup(state.discovery.studyProgress);
      });
      const resultResponse = await fetch(
        `${discoveryApiBase()}/api/research/runs/${encodeURIComponent(runId)}`,
        { headers: authorisation, signal: controller.signal },
      );
      if (!resultResponse.ok) {
        throw studyResponseError(resultResponse, await readApiError(resultResponse));
      }
      data = await resultResponse.json();
    } else {
      const response = await fetch(
        `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/study`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authorisation, ...integration },
          body: JSON.stringify({ question }),
          signal: controller.signal,
        },
      );
      if (!response.ok) throw studyResponseError(response, await readApiError(response));
      data = await response.json();
    }
    if (!currentRequest()) return;
    const study = data.study || {};
    if (!runtimeConfig.publicMode) {
      const endToEnd = (study.observability?.stages || []).find(
        (stage) => stage.name === "end_to_end",
      );
      state.discovery.studyProgress.push({
        sequence: state.discovery.studyProgress.length + 1,
        kind: "run_completed",
        message: "The study is ready.",
        elapsed_ms: Number(endToEnd?.duration_ms || 0),
        counts: { sections: Array.isArray(study.sections) ? study.sections.length : 0 },
      });
    }
    output.innerHTML = `${researchProgressMarkup(state.discovery.studyProgress, { completed: true })}${deepStudyQuotaMarkup(data.quota)}${deepStudyMarkup(study)}`;
    focusElement(output.querySelector("[data-study-result]"));
  } catch (error) {
    if (error?.name === "AbortError" || !currentRequest()) return;
    console.warn("Deep Study request did not complete", error);
    output.innerHTML = `${researchProgressMarkup(state.discovery.studyProgress)}${deepStudyFailureMarkup(error)}`;
    focusInterfaceState(output);
  } finally {
    if (currentRequest()) {
      state.discovery.studyController = null;
      button.disabled = false;
      button.textContent = "Generate study";
      cancelButton?.classList.add("hidden");
      output.setAttribute("aria-busy", "false");
    }
  }
}

function deepStudyQuotaMarkup(quota) {
  const user = quota?.user;
  const global = quota?.global;
  if (!user || !global) return "";
  if (quota.unlimited) {
    return '<p class="study-quota"><strong>Unlimited local testing</strong> · this development account does not consume the public demo allowance</p>';
  }
  const reset = quota.reset_at
    ? new Date(quota.reset_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
        timeZoneName: "short",
      })
    : "00:00 UTC";
  return `<p class="study-quota"><strong>${escapeHtml(user.remaining)} of ${escapeHtml(user.limit)}</strong> account studies remain today · ${escapeHtml(global.remaining)} available across the public demo · resets ${escapeHtml(reset)}</p>`;
}

const PACKET_ISSUE_LABELS = Object.freeze({
  attributed_omission_unexplained: "Some attributed omissions do not have a recognised reason.",
  citation_ids_invalid: "One or more evidence identifiers are not citation-ready.",
  duplicate_evidence_present: "The selected packet still contains duplicate evidence.",
  film_identity_incomplete: "The selected film identity is incomplete.",
  film_identity_mismatch: "The packet identity does not match the selected film.",
  film_specific_evidence_sparse: "No film-specific attributed source is available; the study remains a viewing framework.",
  focus_relevance_low: "The lexical focus signal is weak; inspect the selected evidence before relying on it.",
  instruction_containment_missing: "Retrieved instructions are not safely bounded.",
  provenance_incomplete: "Some selected evidence has incomplete applicable provenance.",
  single_evidence_class: "Only one evidence class is currently available.",
  theory_evidence_missing: "No theory framework is available for synthesis.",
  unknown_evidence_language: "Some selected evidence has an unknown language label.",
});
const SELECTION_REASON_LABELS = Object.freeze({
  below_minimum_content: "too little substantive text",
  duplicate: "duplicate or near-duplicate",
  source_quota: "source/domain diversity limit",
  item_limit: "layer item limit",
  total_budget_exhausted: "layer character budget",
});
const STUDY_STAGE_LABELS = Object.freeze({
  film_context: "Film context",
  criticism_cache: "Criticism cache",
  video_cache: "Video cache",
  retrieval_planning: "Retrieval planning",
  lexical_retrieval: "Lexical retrieval",
  semantic_retrieval: "Semantic retrieval",
  fusion_and_selection: "Fusion and selection",
  packet_assembly: "Packet assembly",
  prompt_serialisation: "Prompt serialisation",
  model_transport: "Model transport",
  validation_and_repair: "Validation and repair",
  end_to_end: "End to end",
});

function packetLayerMarkup(label, selection, selected) {
  const candidates = Number(selection?.candidate_items ?? selected);
  const omitted = Number(selection?.omitted_items || 0);
  const characters = Number(selection?.selected_characters || 0);
  return `<article class="packet-layer-card">
    <span>${escapeHtml(label)}</span>
    <strong>${escapeHtml(selected)} selected</strong>
    <small>${escapeHtml(candidates)} candidates · ${escapeHtml(omitted)} omitted${characters ? ` · ${escapeHtml(characters)} chars` : ""}</small>
  </article>`;
}

function packetTransparencyMarkup(study) {
  const packet = study.evidence_packet || {};
  const retrieval = packet.retrieval || {};
  const theory = retrieval.theory_selection || {};
  const critical = retrieval.critical_selection || {};
  const attributed = retrieval.attributed_selection || {};
  const quality = study.packet_quality || {};
  const qualityIssues = Array.isArray(quality.issues) ? quality.issues : [];
  const sources = Array.isArray(study.sources) ? study.sources : [];
  const claims = Array.isArray(study.critical_claims) ? study.critical_claims : [];
  const attributedSources = Array.isArray(study.attributed_sources)
    ? study.attributed_sources
    : [];
  const omissions = [theory, critical, attributed].reduce((totals, selection) => {
    Object.entries(selection?.omission_reasons || {}).forEach(([reason, value]) => {
      if (SELECTION_REASON_LABELS[reason] && Number.isInteger(value) && value > 0) {
        totals[reason] = (totals[reason] || 0) + value;
      }
    });
    return totals;
  }, {});
  const gaps = qualityIssues.map(
    (issue) => PACKET_ISSUE_LABELS[issue] || String(issue).replaceAll("_", " "),
  );
  if (!attributedSources.length && !claims.length && !gaps.some((gap) => gap.includes("film-specific"))) {
    gaps.push("No film-specific attributed source is available; formal claims require close viewing.");
  }
  const observedEvidence = attributedSources.some(
    (source) => source.evidence_type === "film_observed",
  );
  if (!observedEvidence) {
    gaps.push("No measured clip evidence entered this study; film-form claims remain hypotheses.");
  }
  const provenance = Number(quality.provenance?.completeness_ratio || 0);
  const duplication = Number(quality.duplication?.duplicate_ratio || 0);
  const relevance = Number(quality.focus_relevance?.relevance_ratio || 0);
  const observability = study.observability || {};
  const stages = Array.isArray(observability.stages) ? observability.stages : [];
  const counts = observability.counts || {};
  const timingRows = stages
    .filter((stage) => STUDY_STAGE_LABELS[stage.name] && stage.status !== "not_run")
    .map((stage) => `<li><span>${escapeHtml(STUDY_STAGE_LABELS[stage.name])}</span><b>${escapeHtml(Number(stage.duration_ms || 0).toFixed(1))} ms</b><small>${escapeHtml(stage.status)}</small></li>`)
    .join("");
  return `<section class="packet-transparency" aria-labelledby="packetTransparencyTitle">
    <header>
      <div><span>Evidence packet</span><h4 id="packetTransparencyTitle">What entered this study</h4></div>
      <strong class="packet-status is-${escapeHtml(quality.status || "unknown")}">${escapeHtml(quality.status === "passed" ? "Ready" : quality.status === "limited" ? "Ready with limits" : "Inspect packet")}</strong>
    </header>
    <div class="packet-layer-grid">
      ${packetLayerMarkup("Theory", theory, sources.length)}
      ${packetLayerMarkup("Critic claims", critical, claims.length)}
      ${packetLayerMarkup("Attributed text", attributed, attributedSources.length)}
    </div>
    <div class="packet-metrics" aria-label="Packet quality metrics">
      <span><b>${escapeHtml(Math.round(provenance * 100))}%</b> provenance</span>
      <span><b>${escapeHtml(Math.round(duplication * 100))}%</b> duplicates</span>
      <span><b>${escapeHtml(Math.round(relevance * 100))}%</b> lexical focus</span>
      ${Number.isInteger(counts.prompt_tokens) ? `<span><b>${escapeHtml(counts.prompt_tokens)}</b> input tokens</span>` : ""}
    </div>
    ${Object.keys(omissions).length ? `<details class="packet-omissions"><summary>Why evidence was left out</summary><ul>${Object.entries(omissions).map(([reason, value]) => `<li><b>${escapeHtml(value)}</b> ${escapeHtml(SELECTION_REASON_LABELS[reason])}</li>`).join("")}</ul></details>` : ""}
    ${gaps.length ? `<div class="packet-gaps"><strong>Evidence gaps</strong><ul>${[...new Set(gaps)].map((gap) => `<li>${escapeHtml(gap)}</li>`).join("")}</ul></div>` : ""}
    ${timingRows ? `<details class="study-observability"><summary>Study timing and stages</summary><ul>${timingRows}</ul></details>` : ""}
  </section>`;
}

function deepStudyMarkup(study) {
  const sections = Array.isArray(study.sections) ? study.sections : [];
  const sources = Array.isArray(study.sources) ? study.sources : [];
  const criticalClaims = Array.isArray(study.critical_claims) ? study.critical_claims : [];
  const attributedSources = Array.isArray(study.attributed_sources) ? study.attributed_sources : [];
  const sourceMap = Object.fromEntries(sources.map((source) => [source.id, source]));
  const attributedSourceMap = Object.fromEntries(attributedSources.map((source) => [source.evidence_id, source]));
  const viewingTasks = Array.isArray(study.next_viewing) ? study.next_viewing : [];
  const quality = study.quality || {};
  const retrieval = study.evidence_packet?.retrieval || {};
  const plan = Array.isArray(retrieval.plan) ? retrieval.plan : [];
  const qualityLabel = quality.status === "passed" ? "Quality gate passed" : "Evidence remains insufficient";
  return `
    <div class="study-quality ${quality.status === "passed" ? "is-passed" : "is-limited"}">
      <strong>${escapeHtml(qualityLabel)}</strong>
      <span>${escapeHtml(Math.round((quality.score || 0) * 100))}% specificity · ${quality.repair_attempted ? "one audit pass used" : "first draft passed"}</span>
    </div>
    ${packetTransparencyMarkup(study)}
    <article class="study-essay" tabindex="-1" data-study-result>
      <header><span>${escapeHtml(study.model || "DeepSeek")} · evidence-grounded essay</span><h4>${escapeHtml(study.title || "Film study")}</h4></header>
      <p class="study-essay-lede">${escapeHtml(study.central_argument || "No central argument was returned.")}</p>
      <div class="study-essay-body">
        ${sections.map((section, index) => studyEssayParagraphMarkup(section, sourceMap, attributedSourceMap, quality.sections?.[index])).join("")}
      </div>
      <p class="study-essay-boundary"><strong>Evidence boundary.</strong> ${escapeHtml(study.creator_intent_boundary || study.grounding_notice || "Current evidence does not establish creator intention.")}</p>
    </article>
    ${viewingTasks.length ? `<details class="study-viewing-guide"><summary>How to test this reading against the film</summary><ol>${viewingTasks.map((task) => `<li>${escapeHtml(task)}</li>`).join("")}</ol></details>` : ""}
    <details class="study-retrieval"><summary>Why these sources</summary><p>${escapeHtml(String(retrieval.method || "local retrieval").replaceAll("_", " "))} · ${escapeHtml(retrieval.candidate_count || 0)} candidates · ${escapeHtml(retrieval.embedding?.state || "lexical only")}</p>${plan.map((item) => `<span>${escapeHtml(item.origin)} · ${escapeHtml(item.lens)} — ${escapeHtml(item.query)}</span>`).join("")}</details>
    ${studySourceKeyMarkup(sources, attributedSources, criticalClaims)}`;
}

function studyEvidenceTarget(value) {
  return `study-evidence-${String(value || "unknown").replace(/[^A-Za-z0-9_-]+/g, "-")}`;
}

function studySourceKeyMarkup(sources, attributedSources, criticalClaims) {
  return `<div class="study-source-key"><strong>Evidence used</strong>
    ${sources.map((source) => `<details id="${escapeHtml(studyEvidenceTarget(source.id))}" tabindex="-1" data-study-evidence><summary><b>${escapeHtml(source.id)}</b> ${escapeHtml(source.title)} · ${escapeHtml(source.locator || `p. ${source.page || "?"}`)}</summary><p>${escapeHtml(source.excerpt || "")}</p></details>`).join("")}
    ${attributedSources.map(attributedEvidenceMarkup).join("")}
    ${criticalClaims.map((claim) => `<details id="${escapeHtml(studyEvidenceTarget(claim.claim_id))}" tabindex="-1" data-study-evidence><summary><b>${escapeHtml(claim.claim_id)}</b> Attributed critic report · ${escapeHtml(claim.source_id)}</summary><p>${escapeHtml(claim.critic_claim || "No critic claim text was supplied.")}</p></details>`).join("")}
  </div>`;
}

function attributedEvidenceMarkup(source) {
  const sourceUrl = safeHttpUrl(source.source_url);
  const link = sourceUrl ? ` <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Source ↗</a>` : "";
  return `<details id="${escapeHtml(studyEvidenceTarget(source.evidence_id))}" tabindex="-1" data-study-evidence><summary><b>${escapeHtml(source.evidence_id || "E?")}</b> ${escapeHtml(source.title || "Attributed source")} · ${escapeHtml(source.locator || source.evidence_type || "text")}</summary><p>${escapeHtml(source.content || "")}</p>${link}</details>`;
}

function studyEssayParagraphMarkup(section, sourceMap, attributedSourceMap, quality) {
  const ids = Array.isArray(section.source_ids) ? section.source_ids : [];
  const citations = ids.map((id) => {
    const source = sourceMap[id];
    const label = source ? `${id} · p. ${source.page || "?"}` : id;
    const target = studyEvidenceTarget(id);
    return `<a href="#${escapeHtml(target)}" data-study-citation-target="${escapeHtml(target)}" title="Open ${escapeHtml(source?.title || "local source")}">${escapeHtml(label)}</a>`;
  }).join("");
  const criticIds = Array.isArray(section.critic_claim_ids) ? section.critic_claim_ids : [];
  const criticCitations = criticIds.map((id) => {
    const target = studyEvidenceTarget(id);
    return `<a class="critic-citation" href="#${escapeHtml(target)}" data-study-citation-target="${escapeHtml(target)}">${escapeHtml(id)} · critic</a>`;
  }).join("");
  const attributedIds = Array.isArray(section.attributed_source_ids) ? section.attributed_source_ids : [];
  const attributedCitations = attributedIds.map((id) => {
    const target = studyEvidenceTarget(id);
    return `<a class="critic-citation" href="#${escapeHtml(target)}" data-study-citation-target="${escapeHtml(target)}" title="Open ${escapeHtml(attributedSourceMap[id]?.title || "attributed text")}">${escapeHtml(id)} · text</a>`;
  }).join("");
  const qualityIssues = Array.isArray(quality?.issues) ? quality.issues : [];
  const prose = [
    section.critic_reports,
    section.theory_explains,
    section.hypothesis || section.analysis,
    section.mechanism,
    section.alternative_reading,
  ].filter(Boolean).join(" ");
  return `<div class="study-essay-paragraph"><p>${escapeHtml(prose || "No study paragraph was returned.")}<span class="essay-citations">${citations}${criticCitations}${attributedCitations}</span></p>${qualityIssues.length ? `<small>Editorial note: ${qualityIssues.map((item) => item.replaceAll("_", " ")).join(" · ")}</small>` : ""}</div>`;
}

async function readApiError(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
    if (typeof body.detail?.message === "string" && body.detail.message.trim()) {
      return body.detail.message;
    }
    return `HTTP ${response.status}`;
  } catch (_) {
    return `HTTP ${response.status}`;
  }
}

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : null;
  } catch (_) {
    return null;
  }
}

function safeVideoEmbedUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    const isYouTube = url.protocol === "https:"
      && url.hostname === "www.youtube-nocookie.com"
      && /^\/embed\/[A-Za-z0-9_-]{11}$/.test(url.pathname);
    const isBilibili = url.protocol === "https:"
      && url.hostname === "player.bilibili.com"
      && /^BV[A-Za-z0-9]{10}$/.test(url.searchParams.get("bvid") || "");
    return isYouTube || isBilibili ? url.toString() : null;
  } catch (_) {
    return null;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setActiveView(viewKey) {
  refs.tabs.forEach((tab) => {
    const active = tab.dataset.view === viewKey;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.setAttribute("tabindex", active ? "0" : "-1");
  });
  Object.entries(refs.views).forEach(([key, view]) => {
    view.classList.toggle("active", key === viewKey);
  });
}

function onAnalysisTabKeydown(event) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const current = refs.tabs.indexOf(event.currentTarget);
  if (current < 0) return;
  event.preventDefault();
  const nextIndex = event.key === "Home"
    ? 0
    : event.key === "End"
      ? refs.tabs.length - 1
      : (current + (event.key === "ArrowRight" ? 1 : -1) + refs.tabs.length)
        % refs.tabs.length;
  const next = refs.tabs[nextIndex];
  setActiveView(next.dataset.view);
  next.focus();
}

function onFileSelected(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  if (state.url) {
    URL.revokeObjectURL(state.url);
  }

  state.file = file;
  state.analysis = null;
  state.meta = null;

  const url = URL.createObjectURL(file);
  state.url = url;

  refs.fileTitle.textContent = file.name;
  refs.fileMeta.textContent = `${formatBytes(file.size)} · ${file.type || "video/*"}`;
  refs.previewVideo.src = url;
  refs.analysisVideo.src = url;

  clearAnalysisViews();
  setFeatureButtonsEnabled(false);
  refs.analyzeBtn.disabled = true;
  setStatus("Reading metadata...");
  setProgress(0);

  refs.analysisVideo.onloadedmetadata = () => {
    state.meta = buildVideoMeta(file, refs.analysisVideo);
    refs.analyzeBtn.disabled = false;
    setStatus("Metadata ready. Generate analysis when ready.");
    setProgress(0);
    renderOverviewMetadataOnly(state.meta);
  };
}

function buildVideoMeta(file, videoEl) {
  const durationSec = Number(videoEl.duration || 0);
  const fpsEstimated = estimateFps(durationSec);
  return {
    id: cryptoId(),
    filename: file.name,
    durationSec,
    width: Number(videoEl.videoWidth || 0),
    height: Number(videoEl.videoHeight || 0),
    frameCountEstimated: Math.round(durationSec * fpsEstimated),
    fpsEstimated,
    createdAt: new Date().toISOString(),
  };
}

function estimateFps(durationSec) {
  if (durationSec < 30) return 30;
  if (durationSec < 600) return 24;
  return 23.976;
}

async function onAnalyze() {
  if (!state.file || !state.meta) return;

  const interval = Number(refs.sampleInterval.value);
  const sensitivity = Number(refs.sceneSensitivity.value);
  const backendUrl = refs.backendUrl.value.trim();

  refs.analyzeBtn.disabled = true;
  setStatus("Sending video to backend...");
  setProgress(0);

  try {
    const apiResult = await analyzeViaBackend(backendUrl, state.file, sensitivity);
    const normalized = normalizeApiResult(apiResult, interval, sensitivity);
    state.meta = normalized.meta;
    state.analysis = normalized;

    setStatus("Analysis complete.");
    setProgress(100);

    renderAll(state.meta, state.analysis);
    setFeatureButtonsEnabled(true);
  } catch (err) {
    console.error(err);
    setStatus("Analysis could not complete. Check the backend connection, then choose Generate scene analysis to retry.", "error");
    setProgress(0);
  } finally {
    refs.analyzeBtn.disabled = false;
  }
}

async function analyzeViaBackend(url, file, sceneSensitivity) {
  if (!url) {
    throw new Error("Backend URL is required.");
  }

  const form = new FormData();
  form.append("video", file);
  form.append("scene_sensitivity", String(sceneSensitivity));
  form.append("shot_threshold", "0.35");
  form.append("include_object_detection", "true");
  form.append("include_shot_scale", "true");

  setProgress(12);
  const res = await fetch(url, { method: "POST", body: form });
  setProgress(78);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      // ignore json parse errors
    }
    throw new Error(detail);
  }
  const data = await res.json();
  setProgress(92);
  return data;
}

function normalizeApiResult(data, interval, sensitivity) {
  if (!data || !data.meta || !data.global || !Array.isArray(data.scenes)) {
    throw new Error("Invalid backend response shape.");
  }
  return {
    meta: data.meta,
    global: data.global,
    scenes: data.scenes,
    shots: Array.isArray(data.shots) ? data.shots : [],
    outputs: data.outputs || {},
    config: { interval, sensitivity, source: "backend" },
  };
}

function setFeatureButtonsEnabled(enabled) {
  refs.openShotDataBtn.disabled = !enabled;
  refs.openColorBtn.disabled = !enabled;
  refs.openObjectsBtn.disabled = !enabled;
  refs.exportJsonBtn.disabled = !enabled;
  refs.exportScenesCsvBtn.disabled = !enabled;
  refs.exportShotsCsvBtn.disabled = !enabled;
  refs.generateLlmDraftBtn.disabled = !enabled;
}

async function analyzeVideo(video, intervalSec, sensitivity, onProgress) {
  const duration = Number(video.duration || 0);
  if (!duration || Number.isNaN(duration)) {
    throw new Error("Invalid video duration.");
  }

  const samples = await sampleFrames(video, intervalSec, onProgress);
  onProgress(74, "Detecting shot boundaries...");
  const shots = detectShots(samples, duration, sensitivity);

  onProgress(84, "Grouping scenes...");
  const scenes = detectScenes(shots, duration, sensitivity);

  onProgress(92, "Computing scene summaries...");
  const sceneSummaries = summarizeScenes(scenes, shots);

  const asl = shots.length ? avg(shots.map((s) => s.durationSec)) : 0;
  const avgSceneLen = sceneSummaries.length ? avg(sceneSummaries.map((s) => s.durationSec)) : 0;

  onProgress(100, "Finalizing UI models...");

  return {
    samples,
    shots,
    scenes: sceneSummaries,
    global: {
      shotCount: shots.length,
      sceneCount: sceneSummaries.length,
      averageShotLengthSec: asl,
      averageSceneLengthSec: avgSceneLen,
      averageShotsPerScene: sceneSummaries.length ? shots.length / sceneSummaries.length : 0,
    },
  };
}

async function sampleFrames(video, intervalSec, onProgress) {
  const canvas = refs.analysisCanvas;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  const duration = Number(video.duration || 0);
  const times = [];
  for (let t = 0; t < duration; t += intervalSec) {
    times.push(Number(t.toFixed(3)));
  }
  if (!times.length || times[times.length - 1] < duration - 0.25) {
    times.push(Math.max(0, Number((duration - 0.02).toFixed(3))));
  }

  const out = [];

  for (let i = 0; i < times.length; i += 1) {
    const t = times[i];
    await seekTo(video, t);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const { data, width, height } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const features = extractFrameFeatures(data, width, height);
    out.push({ timeSec: t, ...features });

    const pct = Math.round(((i + 1) / times.length) * 72);
    onProgress(pct, `Sampling frames ${i + 1}/${times.length}`);
  }

  return out;
}

function extractFrameFeatures(data, width, height) {
  const totalPixels = width * height;
  const gray = new Float32Array(totalPixels);
  const hist = new Array(16).fill(0);

  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let satSum = 0;
  let brightness = 0;

  for (let px = 0, i = 0; i < data.length; i += 4, px += 1) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];

    sumR += r;
    sumG += g;
    sumB += b;

    const maxCh = Math.max(r, g, b);
    const minCh = Math.min(r, g, b);
    const sat = maxCh === 0 ? 0 : (maxCh - minCh) / maxCh;
    satSum += sat;

    const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    gray[px] = luma;
    brightness += luma;

    const bin = Math.min(15, Math.floor(luma / 16));
    hist[bin] += 1;
  }

  for (let i = 0; i < hist.length; i += 1) {
    hist[i] /= totalPixels;
  }

  let globalEnergy = 0;
  let centerEnergy = 0;
  const cx0 = Math.floor(width * 0.3);
  const cx1 = Math.floor(width * 0.7);
  const cy0 = Math.floor(height * 0.3);
  const cy1 = Math.floor(height * 0.7);

  for (let y = 1; y < height; y += 1) {
    for (let x = 1; x < width; x += 1) {
      const idx = y * width + x;
      const gx = gray[idx] - gray[idx - 1];
      const gy = gray[idx] - gray[idx - width];
      const grad = Math.abs(gx) + Math.abs(gy);
      globalEnergy += grad;

      if (x >= cx0 && x <= cx1 && y >= cy0 && y <= cy1) {
        centerEnergy += grad;
      }
    }
  }

  return {
    avgRgb: [sumR / totalPixels, sumG / totalPixels, sumB / totalPixels],
    hist,
    saturation: satSum / totalPixels,
    brightness: brightness / totalPixels,
    texture: globalEnergy / totalPixels,
    centerFocusRatio: centerEnergy / (globalEnergy + 1e-6),
  };
}

function detectShots(samples, durationSec, sensitivity) {
  if (!samples.length) return [];

  const transitions = [];
  for (let i = 1; i < samples.length; i += 1) {
    const prev = samples[i - 1];
    const cur = samples[i];

    const colorDiff = rgbDistance(prev.avgRgb, cur.avgRgb);
    const histDiff = l1Dist(prev.hist, cur.hist) * 100;
    const textureDiff = Math.abs(prev.texture - cur.texture) * 18;

    const score = colorDiff * 0.72 + histDiff * 0.22 + textureDiff * 0.06;
    transitions.push({ index: i, timeSec: cur.timeSec, score });
  }

  const scores = transitions.map((t) => t.score);
  const mean = avg(scores);
  const sd = std(scores);
  const sensitivityFactor = 1.35 - sensitivity * 0.08; // sensitivity 10 => lower threshold
  const threshold = mean + sd * Math.max(0.45, sensitivityFactor);

  const boundaries = [0];
  transitions.forEach((t) => {
    if (t.score >= threshold) boundaries.push(t.timeSec);
  });

  const deduped = [...new Set(boundaries.map((x) => Number(x.toFixed(3))))].sort((a, b) => a - b);
  if (deduped[deduped.length - 1] < durationSec) {
    deduped.push(durationSec);
  }

  const shots = [];
  for (let i = 0; i < deduped.length - 1; i += 1) {
    const start = deduped[i];
    const end = deduped[i + 1];
    if (end - start < 0.15) continue;

    const shotSamples = samples.filter((s) => s.timeSec >= start && s.timeSec < end + 1e-6);
    const meanRgb = averageRgb(shotSamples.map((s) => s.avgRgb));
    const meanFocus = avg(shotSamples.map((s) => s.centerFocusRatio));
    const meanTexture = avg(shotSamples.map((s) => s.texture));

    shots.push({
      shotId: shots.length + 1,
      startSec: start,
      endSec: end,
      durationSec: end - start,
      avgRgb: meanRgb,
      focus: meanFocus,
      texture: meanTexture,
      shotScale: classifyShotScale(meanFocus),
    });
  }

  return shots;
}

function classifyShotScale(centerFocusRatio) {
  if (centerFocusRatio >= 0.62) return "Close-Up";
  if (centerFocusRatio >= 0.49) return "Medium";
  return "Long";
}

function detectScenes(shots, durationSec, sensitivity) {
  if (!shots.length) {
    return [{ sceneId: 1, shotIds: [], startSec: 0, endSec: durationSec }];
  }

  const boundaries = [0];
  const baseThreshold = 45 - sensitivity * 1.6;

  for (let i = 1; i < shots.length; i += 1) {
    const prev = shots[i - 1];
    const cur = shots[i];
    const drift = rgbDistance(prev.avgRgb, cur.avgRgb);
    const rhythm = Math.abs(prev.durationSec - cur.durationSec) * 7;
    const cue = drift + rhythm;

    const shotsSinceBoundary = i - boundaries[boundaries.length - 1];
    if ((cue > baseThreshold && shotsSinceBoundary >= 2) || shotsSinceBoundary >= 8) {
      boundaries.push(i);
    }
  }

  boundaries.push(shots.length);

  const scenes = [];
  for (let i = 0; i < boundaries.length - 1; i += 1) {
    const s = boundaries[i];
    const e = boundaries[i + 1];
    const sceneShots = shots.slice(s, e);
    if (!sceneShots.length) continue;

    scenes.push({
      sceneId: scenes.length + 1,
      shotIds: sceneShots.map((x) => x.shotId),
      startSec: sceneShots[0].startSec,
      endSec: sceneShots[sceneShots.length - 1].endSec,
    });
  }

  return scenes;
}

function summarizeScenes(scenes, shots) {
  return scenes.map((scene) => {
    const sceneShots = shots.filter((shot) => scene.shotIds.includes(shot.shotId));
    const durationSec = scene.endSec - scene.startSec;
    const avgShotLenSec = sceneShots.length ? durationSec / sceneShots.length : 0;

    const counts = { Long: 0, Medium: 0, "Close-Up": 0 };
    sceneShots.forEach((s) => {
      counts[s.shotScale] = (counts[s.shotScale] || 0) + 1;
    });

    const dominantRgb = averageRgb(sceneShots.map((s) => s.avgRgb));
    const hue = rgbToHue(dominantRgb);
    const motionProxy = avg(sceneShots.map((s) => s.texture));

    const props = inferNotableProps(dominantRgb, motionProxy, avg(sceneShots.map((s) => s.focus)));

    return {
      sceneId: scene.sceneId,
      startSec: scene.startSec,
      endSec: scene.endSec,
      durationSec,
      shotCount: sceneShots.length,
      averageShotLengthSec: avgShotLenSec,
      shotScaleComposition: {
        longPct: pct(counts.Long, sceneShots.length),
        mediumPct: pct(counts.Medium, sceneShots.length),
        closePct: pct(counts["Close-Up"], sceneShots.length),
      },
      dominantRgb,
      dominantHue: hue,
      props,
      shots: sceneShots,
      motionProxy,
    };
  });
}

function getFlatShots(analysis) {
  const rows = [];
  analysis.scenes.forEach((scene) => {
    scene.shots.forEach((shot) => {
      rows.push({
        sceneId: scene.sceneId,
        shotId: shot.shotId,
        startSec: shot.startSec,
        endSec: shot.endSec,
        durationSec: shot.durationSec,
        shotScale: shot.shotScale,
        avgRgb: shot.avgRgb,
      });
    });
  });
  return rows;
}

function inferNotableProps(rgb, motionProxy, focusProxy) {
  const [r, g, b] = rgb;
  const brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const picks = [];

  if (r > g + 15 && r > b + 15) {
    picks.push({ label: "interior furniture", score: 0.76 });
    picks.push({ label: "wooden surfaces", score: 0.68 });
  }
  if (g > r + 12 && g > b + 12) {
    picks.push({ label: "foliage / plants", score: 0.78 });
    picks.push({ label: "textile details", score: 0.61 });
  }
  if (b > r + 10 && b > g + 10) {
    picks.push({ label: "screens / sky / water", score: 0.74 });
    picks.push({ label: "metal props", score: 0.57 });
  }

  if (brightness < 72) {
    picks.push({ label: "lamps / practical lights", score: 0.64 });
  }

  if (motionProxy > 55) {
    picks.push({ label: "vehicles / moving crowd", score: 0.63 });
  }

  if (focusProxy >= 0.62) {
    picks.push({ label: "hand props / facial accessories", score: 0.58 });
  }

  if (picks.length === 0) {
    picks.push({ label: "set decoration", score: 0.55 });
    picks.push({ label: "background signage", score: 0.49 });
  }

  const dedup = [];
  const seen = new Set();
  picks.forEach((p) => {
    if (!seen.has(p.label)) {
      dedup.push(p);
      seen.add(p.label);
    }
  });

  return dedup
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .map((p) => ({ ...p, score: Number(p.score.toFixed(2)) }));
}

function renderAll(meta, analysis) {
  renderOverview(meta, analysis);
  renderShotData(analysis);
  renderColorAnalysis(analysis);
  renderObjectAnalysis(analysis);
}

function clearAnalysisViews() {
  Object.values(refs.contents).forEach((el) => {
    el.classList.add("hidden");
    el.innerHTML = "";
  });
  Object.values(refs.placeholders).forEach((el) => {
    el.classList.remove("hidden");
  });
}

function renderOverviewMetadataOnly(meta) {
  const html = `
    <div class="meta-grid">
      ${metaItem("Filename", meta.filename)}
      ${metaItem("Duration", formatTime(meta.durationSec))}
      ${metaItem("Resolution", `${meta.width} × ${meta.height}`)}
      ${metaItem("FPS (estimated)", `${meta.fpsEstimated}`)}
      ${metaItem("Frame count (estimated)", `${meta.frameCountEstimated}`)}
    </div>
  `;

  refs.placeholders.overview.classList.add("hidden");
  refs.contents.overview.classList.remove("hidden");
  refs.contents.overview.innerHTML = html;
}

function renderOverview(meta, analysis) {
  const sceneBlocks = analysis.scenes
    .map((scene) => {
      const pctWidth = Math.max(1.5, (scene.durationSec / meta.durationSec) * 100);
      const color = rgbToCss(scene.dominantRgb);
      return `<div class="scene-block" title="Scene ${scene.sceneId}: ${formatTime(scene.durationSec)}" style="width:${pctWidth}%;background:${color}"></div>`;
    })
    .join("");

  const html = `
    <div class="meta-grid">
      ${metaItem("Filename", meta.filename)}
      ${metaItem("Duration", formatTime(meta.durationSec))}
      ${metaItem("Resolution", `${meta.width} × ${meta.height}`)}
      ${metaItem("FPS (estimated)", `${meta.fpsEstimated}`)}
      ${metaItem("Frame count (estimated)", `${meta.frameCountEstimated}`)}
      ${metaItem("Sampling", `${analysis.config.interval.toFixed(2)}s interval`)}
    </div>

    <div class="kpi-grid">
      ${kpi("Average Shot Length", formatTime(analysis.global.averageShotLengthSec))}
      ${kpi("Average Scene Length", formatTime(analysis.global.averageSceneLengthSec))}
      ${kpi("Total Shots", `${analysis.global.shotCount}`)}
      ${kpi("Total Scenes", `${analysis.global.sceneCount}`)}
      ${kpi("Avg Shots / Scene", `${analysis.global.averageShotsPerScene.toFixed(2)}`)}
    </div>

    <div class="scene-timeline">${sceneBlocks}</div>
    <p class="scene-caption">Scene timeline (segment width = scene duration, color = scene dominant hue)</p>
  `;

  refs.placeholders.overview.classList.add("hidden");
  refs.contents.overview.classList.remove("hidden");
  refs.contents.overview.innerHTML = html;
}

function renderShotData(analysis) {
  const rows = analysis.scenes
    .map((scene) => {
      const scales = scene.shotScaleComposition;
      return `
      <tr>
        <td>Scene ${scene.sceneId}</td>
        <td>${formatTime(scene.startSec)} - ${formatTime(scene.endSec)}</td>
        <td>${formatTime(scene.durationSec)}</td>
        <td>${scene.shotCount}</td>
        <td>${formatTime(scene.averageShotLengthSec)}</td>
        <td>
          <div class="scale-stack" aria-label="shot scale composition">
            <span class="scale-long" style="width:${scales.longPct}%"></span>
            <span class="scale-medium" style="width:${scales.mediumPct}%"></span>
            <span class="scale-close" style="width:${scales.closePct}%"></span>
          </div>
        </td>
        <td>L ${scales.longPct}% / M ${scales.mediumPct}% / C ${scales.closePct}%</td>
      </tr>`;
    })
    .join("");

  const html = `
    <div class="kpi-grid">
      ${kpi("Global ASL", formatTime(analysis.global.averageShotLengthSec))}
      ${kpi("Average Scene Length", formatTime(analysis.global.averageSceneLengthSec))}
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Scene</th>
            <th>Timecode</th>
            <th>Scene Length</th>
            <th>Shot Count</th>
            <th>Avg Shot Length (Scene)</th>
            <th>Shot Scale Mix</th>
            <th>Composition</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;

  refs.placeholders.shotdata.classList.add("hidden");
  refs.contents.shotdata.classList.remove("hidden");
  refs.contents.shotdata.innerHTML = html;
}

function renderColorAnalysis(analysis) {
  refs.placeholders.color.classList.add("hidden");
  refs.contents.color.classList.remove("hidden");

  const cards = analysis.scenes
    .map((scene) => {
      const id = `wheel-${scene.sceneId}`;
      return `
      <article class="scene-card">
        <h4>Scene ${scene.sceneId}</h4>
        <p class="meta">${formatTime(scene.startSec)} - ${formatTime(scene.endSec)} · Dominant hue ${Math.round(scene.dominantHue)}°</p>
        <div class="wheel-row">
          <canvas id="${id}" class="wheel-canvas" width="180" height="180"></canvas>
          <div>
            <div class="swatch" style="background:${rgbToCss(scene.dominantRgb)}"></div>
            <p class="meta">${rgbLabel(scene.dominantRgb)}</p>
          </div>
        </div>
      </article>
      `;
    })
    .join("");

  refs.contents.color.innerHTML = `<div class="scene-grid">${cards}</div>`;

  analysis.scenes.forEach((scene) => {
    const canvas = document.getElementById(`wheel-${scene.sceneId}`);
    drawColorWheel(canvas, scene.dominantHue, scene.dominantRgb);
  });
}

function drawColorWheel(canvas, hueHighlight, rgbHighlight) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.46;

  ctx.clearRect(0, 0, width, height);

  for (let deg = 0; deg < 360; deg += 1) {
    const start = ((deg - 90) * Math.PI) / 180;
    const end = ((deg + 1 - 90) * Math.PI) / 180;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, start, end);
    ctx.closePath();
    ctx.fillStyle = `hsl(${deg}, 88%, 52%)`;
    ctx.fill();
  }

  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.58, 0, Math.PI * 2);
  ctx.fillStyle = "#fff";
  ctx.fill();

  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.7, 0, Math.PI * 2);
  ctx.strokeStyle = "rgba(0,0,0,0.08)";
  ctx.lineWidth = 1;
  ctx.stroke();

  const hlStart = ((hueHighlight - 10 - 90) * Math.PI) / 180;
  const hlEnd = ((hueHighlight + 10 - 90) * Math.PI) / 180;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, hlStart, hlEnd);
  ctx.arc(cx, cy, radius * 0.58, hlEnd, hlStart, true);
  ctx.closePath();
  ctx.fillStyle = "rgba(0,0,0,0.16)";
  ctx.fill();

  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.25, 0, Math.PI * 2);
  ctx.fillStyle = rgbToCss(rgbHighlight);
  ctx.fill();
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function renderObjectAnalysis(analysis) {
  const cards = analysis.scenes
    .map((scene) => {
      const chips = scene.props
        .map((p) => `<span class="chip">${p.label} · ${Math.round(p.score * 100)}%</span>`)
        .join("");

      return `
      <article class="scene-card">
        <h4>Scene ${scene.sceneId}</h4>
        <p class="meta">${formatTime(scene.startSec)} - ${formatTime(scene.endSec)} · ${scene.shotCount} shots</p>
        <div class="chips">${chips}</div>
      </article>
      `;
    })
    .join("");

  const html = `
    <div class="scene-grid">${cards}</div>
    <p class="note">
      Props are currently heuristic proxies from visual signatures.
      Future step: replace this module with detector output + LLM interpretation API for scene meaning analysis.
    </p>
  `;

  refs.placeholders.objects.classList.add("hidden");
  refs.contents.objects.classList.remove("hidden");
  refs.contents.objects.innerHTML = html;
  refs.llmDraftWrap.classList.remove("hidden");
  refs.llmDraftText.value = "";
}

function generateLlmDraft() {
  if (!state.analysis || !state.meta) return;
  const lines = [];
  lines.push(`Film Clip: ${state.meta.filename}`);
  lines.push(`Duration: ${formatTime(state.meta.durationSec)} | Scenes: ${state.analysis.global.sceneCount} | Shots: ${state.analysis.global.shotCount}`);
  lines.push(`Global ASL: ${formatTime(state.analysis.global.averageShotLengthSec)} | Avg Scene Length: ${formatTime(state.analysis.global.averageSceneLengthSec)}`);
  lines.push("");
  lines.push("Scene Notes (for LLM interpretation):");
  lines.push("");

  state.analysis.scenes.forEach((scene) => {
    const s = scene.shotScaleComposition;
    const propText = scene.props.map((p) => `${p.label} (${Math.round(p.score * 100)}%)`).join(", ");
    lines.push(
      `Scene ${scene.sceneId} [${formatTime(scene.startSec)} - ${formatTime(scene.endSec)}]: duration ${formatTime(scene.durationSec)}, ${scene.shotCount} shots, ASL ${formatTime(scene.averageShotLengthSec)}.`
    );
    lines.push(
      `Shot scales: Long ${s.longPct}%, Medium ${s.mediumPct}%, Close-Up ${s.closePct}%. Dominant hue ${Math.round(scene.dominantHue)}° (${rgbLabel(scene.dominantRgb)}).`
    );
    lines.push(`Notable props: ${propText}.`);
    lines.push("");
  });

  lines.push("Task suggestion:");
  lines.push("Interpret how scene rhythm, dominant color shifts, shot scale composition, and notable props might contribute to narrative meaning and emotional tone.");

  refs.llmDraftText.value = lines.join("\\n");
  setActiveView("objects");
}

function metaItem(name, value) {
  return `<div class="meta-item"><span class="name">${name}</span><span class="value">${value}</span></div>`;
}

function kpi(label, value) {
  return `<article class="kpi-card"><p class="kpi-label">${label}</p><p class="kpi-value">${value}</p></article>`;
}

function setStatus(text, kind = "") {
  refs.statusText.textContent = text;
  refs.statusText.classList.toggle("is-error", kind === "error");
}

function setProgress(percent) {
  refs.progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
}

function seekTo(video, timeSec) {
  return new Promise((resolve, reject) => {
    const onSeeked = () => {
      cleanup();
      resolve();
    };

    const onError = () => {
      cleanup();
      reject(new Error("Failed to seek video frame."));
    };

    const cleanup = () => {
      video.removeEventListener("seeked", onSeeked);
      video.removeEventListener("error", onError);
    };

    video.addEventListener("seeked", onSeeked, { once: true });
    video.addEventListener("error", onError, { once: true });

    try {
      video.currentTime = Math.max(0, Math.min(timeSec, Math.max(0, video.duration - 0.02)));
    } catch (err) {
      cleanup();
      reject(err);
    }
  });
}

function rgbDistance(a, b) {
  const dr = a[0] - b[0];
  const dg = a[1] - b[1];
  const db = a[2] - b[2];
  return Math.sqrt(dr * dr + dg * dg + db * db);
}

function l1Dist(a, b) {
  let sum = 0;
  for (let i = 0; i < a.length; i += 1) {
    sum += Math.abs(a[i] - b[i]);
  }
  return sum;
}

function avg(arr) {
  if (!arr || !arr.length) return 0;
  return arr.reduce((s, x) => s + x, 0) / arr.length;
}

function std(arr) {
  if (!arr || arr.length < 2) return 0;
  const m = avg(arr);
  const variance = avg(arr.map((x) => (x - m) ** 2));
  return Math.sqrt(variance);
}

function averageRgb(list) {
  if (!list.length) return [0, 0, 0];
  const total = list.reduce(
    (acc, rgb) => [acc[0] + rgb[0], acc[1] + rgb[1], acc[2] + rgb[2]],
    [0, 0, 0],
  );
  return [total[0] / list.length, total[1] / list.length, total[2] / list.length];
}

function pct(n, d) {
  if (!d) return 0;
  return Math.round((n / d) * 100);
}

function rgbToHue(rgb) {
  let [r, g, b] = rgb.map((v) => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const diff = max - min;

  if (diff === 0) return 0;

  let hue;
  switch (max) {
    case r:
      hue = ((g - b) / diff) % 6;
      break;
    case g:
      hue = (b - r) / diff + 2;
      break;
    default:
      hue = (r - g) / diff + 4;
      break;
  }

  const deg = hue * 60;
  return deg < 0 ? deg + 360 : deg;
}

function rgbToCss(rgb) {
  const [r, g, b] = rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))));
  return `rgb(${r}, ${g}, ${b})`;
}

function rgbLabel(rgb) {
  const [r, g, b] = rgb.map((v) => Math.round(v));
  return `RGB(${r}, ${g}, ${b})`;
}

function formatTime(sec) {
  if (!Number.isFinite(sec)) return "00:00";
  const s = Math.max(0, Math.round(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

function cryptoId() {
  return Math.random().toString(36).slice(2, 10);
}

function downloadTextFile(filename, content, mimeType = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[\",\\n]/.test(text)) return `"${text.replace(/\"/g, "\"\"")}"`;
  return text;
}

function toCsv(rows, header) {
  const lines = [header.join(",")];
  rows.forEach((row) => {
    lines.push(row.map((v) => csvEscape(v)).join(","));
  });
  return `${lines.join("\\n")}\\n`;
}

function exportAnalysisJson() {
  if (!state.analysis || !state.meta) return;
  const payload = {
    videoMeta: state.meta,
    config: state.analysis.config,
    global: state.analysis.global,
    scenes: state.analysis.scenes.map((scene) => ({
      sceneId: scene.sceneId,
      startSec: scene.startSec,
      endSec: scene.endSec,
      durationSec: scene.durationSec,
      shotCount: scene.shotCount,
      averageShotLengthSec: scene.averageShotLengthSec,
      shotScaleComposition: scene.shotScaleComposition,
      dominantRgb: scene.dominantRgb.map((v) => Math.round(v)),
      dominantHue: scene.dominantHue,
      props: scene.props,
    })),
    shots: getFlatShots(state.analysis).map((shot) => ({
      sceneId: shot.sceneId,
      shotId: shot.shotId,
      startSec: shot.startSec,
      endSec: shot.endSec,
      durationSec: shot.durationSec,
      shotScale: shot.shotScale,
      avgRgb: shot.avgRgb.map((v) => Math.round(v)),
    })),
  };
  downloadTextFile(
    `${safeStem(state.meta.filename)}_analysis.json`,
    JSON.stringify(payload, null, 2),
    "application/json;charset=utf-8",
  );
}

function exportScenesCsv() {
  if (!state.analysis || !state.meta) return;
  const header = [
    "scene_id",
    "start_sec",
    "end_sec",
    "duration_sec",
    "shot_count",
    "avg_shot_length_sec",
    "long_pct",
    "medium_pct",
    "close_pct",
    "dominant_hue_deg",
    "dominant_rgb",
    "notable_props",
  ];
  const rows = state.analysis.scenes.map((scene) => [
    scene.sceneId,
    scene.startSec.toFixed(3),
    scene.endSec.toFixed(3),
    scene.durationSec.toFixed(3),
    scene.shotCount,
    scene.averageShotLengthSec.toFixed(3),
    scene.shotScaleComposition.longPct,
    scene.shotScaleComposition.mediumPct,
    scene.shotScaleComposition.closePct,
    Math.round(scene.dominantHue),
    rgbLabel(scene.dominantRgb),
    scene.props.map((p) => p.label).join(" | "),
  ]);
  downloadTextFile(
    `${safeStem(state.meta.filename)}_scenes.csv`,
    toCsv(rows, header),
    "text/csv;charset=utf-8",
  );
}

function exportShotsCsv() {
  if (!state.analysis || !state.meta) return;
  const header = ["scene_id", "shot_id", "start_sec", "end_sec", "duration_sec", "shot_scale", "avg_rgb"];
  const rows = getFlatShots(state.analysis).map((shot) => [
    shot.sceneId,
    shot.shotId,
    shot.startSec.toFixed(3),
    shot.endSec.toFixed(3),
    shot.durationSec.toFixed(3),
    shot.shotScale,
    rgbLabel(shot.avgRgb),
  ]);
  downloadTextFile(
    `${safeStem(state.meta.filename)}_shots.csv`,
    toCsv(rows, header),
    "text/csv;charset=utf-8",
  );
}

function safeStem(filename) {
  const i = filename.lastIndexOf(".");
  const stem = i > 0 ? filename.slice(0, i) : filename;
  return stem.replace(/[^a-zA-Z0-9-_]+/g, "_");
}
