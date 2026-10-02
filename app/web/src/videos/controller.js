import { readApiError } from "../api/errors";

// Video fetching and category selection with dossier ownership guards.
// JavaScript controller: migrated module boundaries, not yet a fully typed domain model.
export function createVideos(context, services) {
  const { state, refs } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const videoButtonProgressLabel = (...args) => services.videoViews.videoButtonProgressLabel(...args);
  const filmVideosMarkup = (...args) => services.videoViews.filmVideosMarkup(...args);
  const discoveryApiBase = (...args) => services.ui.discoveryApiBase(...args);
  const fetchProgressMarkup = (...args) => services.ui.fetchProgressMarkup(...args);
  const focusInterfaceState = (...args) => services.ui.focusInterfaceState(...args);

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
      if (state.discovery.selectedFilm !== film) return;
      const integration = window.FirstRollIntegrations?.requestHeaders?.("youtube") || {};
      const response = await fetch(
        `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/videos`,
        {
          method: "POST",
          headers: { ...authorisation, ...integration },
          signal: state.discovery.detailController?.signal,
        },
      );
      if (!response.ok) throw new Error(await readApiError(response));
      const data = await response.json();
      if (state.discovery.selectedFilm !== film) return;
      film.video_sources = film.video_sources || {};
      film.video_sources.bundle = data.video_sources;
      output.innerHTML = filmVideosMarkup(data.video_sources);
      focusInterfaceState(output);
      button.textContent = "Find more videos";
    } catch (error) {
      if (error?.name === "AbortError" || state.discovery.selectedFilm !== film) return;
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
      if (state.discovery.selectedFilm === film) {
        output.setAttribute("aria-busy", "false");
        button.disabled = false;
      }
    }
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

  return {
    loadFilmVideos,
    selectVideoCategory,
  };
}
