import { escapeHtml } from "../shared/html";
import { readApiError } from "../api/errors";

// Dossier lifecycle and delegated actions.
// JavaScript controller: migrated module boundaries, not yet a fully typed domain model.
export function createDossier(context, services) {
  const { state, refs } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const setProductView = (...args) => services.navigation.setProductView(...args);
  const toggleSavedFilm = (...args) => services.accounts.toggleSavedFilm(...args);
  const persistDiscoverySession = (...args) => services.session.persistDiscoverySession(...args);
  const renderFilmDetail = (...args) => services.dossierView.renderFilmDetail(...args);
  const formatRating = (...args) => services.dossierView.formatRating(...args);
  const formatCompactCount = (...args) => services.dossierView.formatCompactCount(...args);
  const loadFilmVideos = (...args) => services.videos.loadFilmVideos(...args);
  const selectVideoCategory = (...args) => services.videos.selectVideoCategory(...args);
  const selectCriticismSource = (...args) => services.criticism.selectCriticismSource(...args);
  const loadProviderCriticism = (...args) => services.criticism.loadProviderCriticism(...args);
  const structureProviderCriticism = (...args) => services.criticism.structureProviderCriticism(...args);
  const firstLoadedCriticismRoute = (...args) => services.criticismViews.firstLoadedCriticismRoute(...args);
  const cancelDeepStudyRequest = (...args) => services.study.cancelDeepStudyRequest(...args);
  const generateDeepStudy = (...args) => services.study.generateDeepStudy(...args);
  const discoveryApiBase = (...args) => services.ui.discoveryApiBase(...args);
  const fetchProgressMarkup = (...args) => services.ui.fetchProgressMarkup(...args);
  const focusElement = (...args) => services.ui.focusElement(...args);
  const focusInterfaceState = (...args) => services.ui.focusInterfaceState(...args);

  function cancelFilmDetailRequests() {
    cancelDeepStudyRequest();
    state.discovery.detailController?.abort();
    state.discovery.detailController = null;
    refs.filmDetail.setAttribute("aria-busy", "false");
  }

  async function loadFilmDetail(filmId, options = {}) {
    cancelFilmDetailRequests();
    const controller = new AbortController();
    state.discovery.detailController = controller;
    const currentRequest = () => (
      state.discovery.detailController === controller && !controller.signal.aborted
    );
    state.discovery.detailFilmId = filmId;
    state.discovery.selectedFilm = null;
    persistDiscoverySession();
    refs.filmDetail.classList.remove("hidden");
    refs.filmDetail.setAttribute("aria-busy", "true");
    refs.filmDetail.innerHTML = `<button class="detail-close" type="button" data-detail-close aria-label="Close film dossier">×</button>${fetchProgressMarkup("Building the film dossier…")}`;
    if (options.scroll !== false) {
      refs.filmDetail.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    try {
      const res = await fetch(
        `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(filmId)}`,
        { signal: controller.signal },
      );
      if (!res.ok) throw new Error(await readApiError(res));
      const data = await res.json();
      if (!currentRequest()) return;
      state.discovery.selectedFilm = data.film;
      state.discovery.activeCriticismProvider = firstLoadedCriticismRoute(
        data.film.critical_research?.bundles || {},
      );
      renderFilmDetail(data.film);
      persistDiscoverySession();
      loadFilmReception(data.film);
      if (options.scroll !== false) {
        window.requestAnimationFrame(() => {
          if (!currentRequest()) return;
          refs.filmDetail.scrollIntoView({ behavior: "smooth", block: "start" });
          refs.filmDetail.querySelector("[data-dossier-heading]")?.focus({ preventScroll: true });
        });
      }
    } catch (err) {
      if (err?.name === "AbortError" || !currentRequest()) return;
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
      // Keep the controller for reception and evidence requests until the dossier closes.
      if (currentRequest()) refs.filmDetail.setAttribute("aria-busy", "false");
    }
  }

  async function loadFilmReception(film) {
    const section = refs.filmDetail.querySelector("[data-film-reception]");
    const output = refs.filmDetail.querySelector("[data-reception-scores]");
    if (!section || !output || !film?.id) return;
    try {
      const response = await fetch(
        `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/reception`,
        { signal: state.discovery.detailController?.signal },
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reception = await response.json();
      if (state.discovery.selectedFilm !== film) return;
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
      if (state.discovery.selectedFilm !== film) return;
      output.innerHTML = "";
      if (!section.querySelector(".reception-awards article")) section.classList.add("hidden");
    }
  }

  async function onFilmDetailClick(event) {
    if (event.target.closest("[data-detail-close]")) {
      cancelFilmDetailRequests();
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

  return {
    cancelFilmDetailRequests,
    loadFilmDetail,
    loadFilmReception,
    onFilmDetailClick,
    onFilmDetailKeydown,
  };
}
