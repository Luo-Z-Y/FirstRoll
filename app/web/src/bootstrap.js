// Event registration only. Called once by the application composition root.
// JavaScript controller: migrated module boundaries, not yet a fully typed domain model.
export function createBootstrap(context, services) {
  const { state, refs, systemThemeMedia } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const renderBuildIdentity = (...args) => services.navigation.renderBuildIdentity(...args);
  const applyRuntimeMode = (...args) => services.navigation.applyRuntimeMode(...args);
  const toggleTheme = (...args) => services.navigation.toggleTheme(...args);
  const readThemePreference = (...args) => services.navigation.readThemePreference(...args);
  const setThemePreference = (...args) => services.navigation.setThemePreference(...args);
  const syncThemeToggle = (...args) => services.navigation.syncThemeToggle(...args);
  const setProductView = (...args) => services.navigation.setProductView(...args);
  const updateAccountFilmState = (...args) => services.accounts.updateAccountFilmState(...args);
  const onSavedFilmsClick = (...args) => services.accounts.onSavedFilmsClick(...args);
  const updateIntegrationDependentState = (...args) => services.accounts.updateIntegrationDependentState(...args);
  const persistCurrentSession = (...args) => services.session.persistCurrentSession(...args);
  const restoreProductSession = (...args) => services.session.restoreProductSession(...args);
  const restoreDiscoverySession = (...args) => services.session.restoreDiscoverySession(...args);
  const readRecentSearches = (...args) => services.recent.readRecentSearches(...args);
  const renderRecentSearches = (...args) => services.recent.renderRecentSearches(...args);
  const onRecentSearchClick = (...args) => services.recent.onRecentSearchClick(...args);
  const loadDiscoveryStatus = (...args) => services.discovery.loadDiscoveryStatus(...args);
  const onDiscoverySearch = (...args) => services.discovery.onDiscoverySearch(...args);
  const onFilmResultClick = (...args) => services.discovery.onFilmResultClick(...args);
  const selectArchiveFilm = (...args) => services.discovery.selectArchiveFilm(...args);
  const onFilmDetailClick = (...args) => services.dossier.onFilmDetailClick(...args);
  const onFilmDetailKeydown = (...args) => services.dossier.onFilmDetailKeydown(...args);
  const setActiveView = (...args) => services.analysis.setActiveView(...args);
  const onAnalysisTabKeydown = (...args) => services.analysis.onAnalysisTabKeydown(...args);
  const onFileSelected = (...args) => services.analysis.onFileSelected(...args);
  const onAnalyze = (...args) => services.analysis.onAnalyze(...args);
  const setFeatureButtonsEnabled = (...args) => services.analysis.setFeatureButtonsEnabled(...args);
  const exportAnalysisJson = (...args) => services.analysis.exportAnalysisJson(...args);
  const exportScenesCsv = (...args) => services.analysis.exportScenesCsv(...args);
  const exportShotsCsv = (...args) => services.analysis.exportShotsCsv(...args);
  const generateLlmDraft = (...args) => services.analysis.generateLlmDraft(...args);

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

  return {
    setup,
  };
}
