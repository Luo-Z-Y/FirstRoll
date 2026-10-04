import { requiredElement } from "./shared/dom";
import type { AppState } from "./state";

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

  const state: AppState = {
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
      discovery: requiredElement<HTMLElement>("product-discovery"),
      analyse: requiredElement<HTMLElement>("product-analyse"),
      settings: requiredElement<HTMLElement>("product-settings"),
    },
    productNav: Array.from(document.querySelectorAll<HTMLElement>(".nav-link[data-product-view]")),
    productViewTriggers: Array.from(document.querySelectorAll<HTMLElement>("[data-product-view]")),
    themeToggle: requiredElement<HTMLButtonElement>("themeToggle"),
    buildIdentity: requiredElement<HTMLElement>("buildIdentity"),
    discoveryForm: requiredElement<HTMLFormElement>("discoveryForm"),
    filmTitle: requiredElement<HTMLInputElement>("filmTitle"),
    filmYear: requiredElement<HTMLInputElement>("filmYear"),
    filmDirector: requiredElement<HTMLInputElement>("filmDirector"),
    discoverySubmit: requiredElement<HTMLButtonElement>("discoverySubmit"),
    discoveryConnection: requiredElement<HTMLElement>("discoveryConnection"),
    discoveryResultsSection: requiredElement<HTMLElement>("discoveryResultsSection"),
    discoveryResults: requiredElement<HTMLElement>("discoveryResults"),
    resultsTitle: requiredElement<HTMLElement>("resultsTitle"),
    resultsMeta: requiredElement<HTMLElement>("resultsMeta"),
    filmDetail: requiredElement<HTMLElement>("filmDetail"),
    analyseContext: requiredElement<HTMLElement>("analyseContext"),
    videoAnalysisComingSoon: requiredElement<HTMLElement>("videoAnalysisComingSoon"),
    recentSearches: requiredElement<HTMLElement>("recentSearches"),
    videoFile: requiredElement<HTMLInputElement>("videoFile"),
    fileTitle: requiredElement<HTMLElement>("fileTitle"),
    fileMeta: requiredElement<HTMLElement>("fileMeta"),
    sampleInterval: requiredElement<HTMLInputElement>("sampleInterval"),
    sampleIntervalOut: requiredElement<HTMLOutputElement>("sampleIntervalOut"),
    sceneSensitivity: requiredElement<HTMLInputElement>("sceneSensitivity"),
    sceneSensitivityOut: requiredElement<HTMLOutputElement>("sceneSensitivityOut"),
    backendUrl: requiredElement<HTMLInputElement>("backendUrl"),
    analyzeBtn: requiredElement<HTMLButtonElement>("analyzeBtn"),
    openShotDataBtn: requiredElement<HTMLButtonElement>("openShotDataBtn"),
    openColorBtn: requiredElement<HTMLButtonElement>("openColorBtn"),
    openObjectsBtn: requiredElement<HTMLButtonElement>("openObjectsBtn"),
    exportJsonBtn: requiredElement<HTMLButtonElement>("exportJsonBtn"),
    exportScenesCsvBtn: requiredElement<HTMLButtonElement>("exportScenesCsvBtn"),
    exportShotsCsvBtn: requiredElement<HTMLButtonElement>("exportShotsCsvBtn"),
    generateLlmDraftBtn: requiredElement<HTMLButtonElement>("generateLlmDraftBtn"),
    llmDraftWrap: requiredElement<HTMLElement>("llmDraftWrap"),
    llmDraftText: requiredElement<HTMLTextAreaElement>("llmDraftText"),
    accountSavedFilms: requiredElement<HTMLElement>("accountSavedFilms"),
    accountLibraryCount: requiredElement<HTMLElement>("accountLibraryCount"),
    statusText: requiredElement<HTMLElement>("statusText"),
    progressBar: requiredElement<HTMLElement>("progressBar"),
    previewVideo: requiredElement<HTMLVideoElement>("previewVideo"),
    analysisVideo: requiredElement<HTMLVideoElement>("analysisVideo"),
    analysisCanvas: requiredElement<HTMLCanvasElement>("analysisCanvas"),
    tabs: Array.from(document.querySelectorAll<HTMLButtonElement>(".tab")),
    views: {
      overview: requiredElement<HTMLElement>("view-overview"),
      shotdata: requiredElement<HTMLElement>("view-shotdata"),
      color: requiredElement<HTMLElement>("view-color"),
      objects: requiredElement<HTMLElement>("view-objects"),
    },
    placeholders: {
      overview: requiredElement<HTMLElement>("overviewPlaceholder"),
      shotdata: requiredElement<HTMLElement>("shotdataPlaceholder"),
      color: requiredElement<HTMLElement>("colorPlaceholder"),
      objects: requiredElement<HTMLElement>("objectsPlaceholder"),
    },
    contents: {
      overview: requiredElement<HTMLElement>("overviewContent"),
      shotdata: requiredElement<HTMLElement>("shotdataContent"),
      color: requiredElement<HTMLElement>("colorContent"),
      objects: requiredElement<HTMLElement>("objectsContent"),
    },
  };

  return { runtimeConfig, state, systemThemeMedia, refs };
}

export type AppContext = ReturnType<typeof createContext>;
