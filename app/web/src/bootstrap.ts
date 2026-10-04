import type { AppContext } from "./context";
import type { Services } from "./services";

// Event registration only. Called once by the application composition root.
export function createBootstrap(context: AppContext, services: () => Services) {
  const { state, refs, systemThemeMedia } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const renderBuildIdentity: Services["navigation"]["renderBuildIdentity"] = (...args) => services().navigation.renderBuildIdentity(...args);
  const applyRuntimeMode: Services["navigation"]["applyRuntimeMode"] = (...args) => services().navigation.applyRuntimeMode(...args);
  const toggleTheme: Services["navigation"]["toggleTheme"] = (...args) => services().navigation.toggleTheme(...args);
  const readThemePreference: Services["navigation"]["readThemePreference"] = (...args) => services().navigation.readThemePreference(...args);
  const setThemePreference: Services["navigation"]["setThemePreference"] = (...args) => services().navigation.setThemePreference(...args);
  const syncThemeToggle: Services["navigation"]["syncThemeToggle"] = (...args) => services().navigation.syncThemeToggle(...args);
  const setProductView: Services["navigation"]["setProductView"] = (...args) => services().navigation.setProductView(...args);
  const updateAccountFilmState: Services["accounts"]["updateAccountFilmState"] = (...args) => services().accounts.updateAccountFilmState(...args);
  const onSavedFilmsClick: Services["accounts"]["onSavedFilmsClick"] = (...args) => services().accounts.onSavedFilmsClick(...args);
  const updateIntegrationDependentState: Services["accounts"]["updateIntegrationDependentState"] = (...args) => services().accounts.updateIntegrationDependentState(...args);
  const persistCurrentSession: Services["session"]["persistCurrentSession"] = (...args) => services().session.persistCurrentSession(...args);
  const restoreProductSession: Services["session"]["restoreProductSession"] = (...args) => services().session.restoreProductSession(...args);
  const restoreDiscoverySession: Services["session"]["restoreDiscoverySession"] = (...args) => services().session.restoreDiscoverySession(...args);
  const readRecentSearches: Services["recent"]["readRecentSearches"] = (...args) => services().recent.readRecentSearches(...args);
  const renderRecentSearches: Services["recent"]["renderRecentSearches"] = (...args) => services().recent.renderRecentSearches(...args);
  const onRecentSearchClick: Services["recent"]["onRecentSearchClick"] = (...args) => services().recent.onRecentSearchClick(...args);
  const loadDiscoveryStatus: Services["discovery"]["loadDiscoveryStatus"] = (...args) => services().discovery.loadDiscoveryStatus(...args);
  const onDiscoverySearch: Services["discovery"]["onDiscoverySearch"] = (...args) => services().discovery.onDiscoverySearch(...args);
  const onFilmResultClick: Services["discovery"]["onFilmResultClick"] = (...args) => services().discovery.onFilmResultClick(...args);
  const selectArchiveFilm: Services["discovery"]["selectArchiveFilm"] = (...args) => services().discovery.selectArchiveFilm(...args);
  const onFilmDetailClick: Services["dossier"]["onFilmDetailClick"] = (...args) => services().dossier.onFilmDetailClick(...args);
  const onFilmDetailKeydown: Services["dossier"]["onFilmDetailKeydown"] = (...args) => services().dossier.onFilmDetailKeydown(...args);
  const setActiveView: Services["analysis"]["setActiveView"] = (...args) => services().analysis.setActiveView(...args);
  const onAnalysisTabKeydown: Services["analysis"]["onAnalysisTabKeydown"] = (...args) => services().analysis.onAnalysisTabKeydown(...args);
  const onFileSelected: Services["analysis"]["onFileSelected"] = (...args) => services().analysis.onFileSelected(...args);
  const onAnalyze: Services["analysis"]["onAnalyze"] = (...args) => services().analysis.onAnalyze(...args);
  const setFeatureButtonsEnabled: Services["analysis"]["setFeatureButtonsEnabled"] = (...args) => services().analysis.setFeatureButtonsEnabled(...args);
  const exportAnalysisJson: Services["analysis"]["exportAnalysisJson"] = (...args) => services().analysis.exportAnalysisJson(...args);
  const exportScenesCsv: Services["analysis"]["exportScenesCsv"] = (...args) => services().analysis.exportScenesCsv(...args);
  const exportShotsCsv: Services["analysis"]["exportShotsCsv"] = (...args) => services().analysis.exportShotsCsv(...args);
  const generateLlmDraft: Services["analysis"]["generateLlmDraft"] = (...args) => services().analysis.generateLlmDraft(...args);

  function setup(): void {
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
      tab.addEventListener("click", () => { const view = tab.dataset.view; if (view === "overview" || view === "shotdata" || view === "color" || view === "objects") setActiveView(view); });
      tab.addEventListener("keydown", onAnalysisTabKeydown);
    });

    setFeatureButtonsEnabled(false);
    loadDiscoveryStatus();
    document.addEventListener("firstroll:auth-changed", updateAccountFilmState);
    document.addEventListener("firstroll:account-data-changed", updateAccountFilmState);
    document.addEventListener("firstroll:integration-changed", updateIntegrationDependentState);
  }

  return {
    setup,
  };
}
