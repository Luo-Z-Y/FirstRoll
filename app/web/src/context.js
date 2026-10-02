// Each application instance gets its own state and DOM references.
// No module-level singleton state is shared between previews or tests.
export function createContext() {
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
    productView: "discovery",
    viewScroll: { discovery: 0, analyse: 0, settings: 0 },
    discovery: {
      results: [],
      selectedFilm: null,
      detailFilmId: null,
      detailController: null,
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

  return { runtimeConfig, state, systemThemeMedia, refs };
}
