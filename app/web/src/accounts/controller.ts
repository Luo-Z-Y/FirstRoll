import { errorInfo } from "../api/decode";
import type { AppContext } from "../context";
import type { Services } from "../services";
import { eventElement } from "../shared/dom";
import { escapeHtml, safeHttpUrl } from "../shared/html";
import type { SavedFilm } from "./types";

// Account UI integration; authentication remains in the existing provider adapter.
export function createAccounts(context: AppContext, services: () => Services) {
  const { state, refs, runtimeConfig } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const videoProviderStatusMarkup: Services["videoViews"]["videoProviderStatusMarkup"] = (...args) => services().videoViews.videoProviderStatusMarkup(...args);
  const focusInterfaceState: Services["ui"]["focusInterfaceState"] = (...args) => services().ui.focusInterfaceState(...args);

  function updateAccountFilmState(): void {
    updateDeepStudyAuthState();
    updateSavedFilmButton();
    renderSavedFilms(window.FirstRollAuth?.savedFilms?.() || []);
  }

  function updateDeepStudyAuthState(): void {
    const button = refs.filmDetail.querySelector<HTMLElement>("[data-generate-study]");
    if (!button || !runtimeConfig.accountUi || state.discovery.studyController) return;
    button.textContent = window.FirstRollAuth?.currentUser()
      ? "Generate study"
      : "Sign in to Deep Study";
  }

  function updateSavedFilmButton(): void {
    const button = refs.filmDetail.querySelector<HTMLElement>("[data-save-film]");
    const film = state.discovery.selectedFilm;
    if (!button || !film) return;
    const signedIn = Boolean(window.FirstRollAuth?.currentUser?.());
    const saved = Boolean(window.FirstRollAuth?.isFilmSaved?.(film.id));
    button.dataset.saved = String(saved);
    button.textContent = signedIn
      ? (saved ? "Remove from saved films" : "Save to account")
      : "Sign in to save";
  }

  function renderSavedFilms(films: SavedFilm[]): void {
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

  async function onSavedFilmsClick(event: MouseEvent): Promise<void> {
    const target = eventElement(event);
    if (!target) return;
    const retry = target.closest<HTMLButtonElement>("[data-retry-saved-films]");
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
    const button = target.closest<HTMLButtonElement>("[data-remove-saved-film]");
    if (!button || !button.dataset.removeSavedFilm) return;
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

  function updateIntegrationDependentState(): void {
    const film = state.discovery.selectedFilm;
    const output = refs.filmDetail.querySelector<HTMLElement>("[data-film-videos-output]");
    if (film && output && !film.video_sources?.bundle) {
      output.innerHTML = videoProviderStatusMarkup(film.video_sources?.providers);
    }
  }

  async function toggleSavedFilm(button: HTMLButtonElement): Promise<void> {
    const film = state.discovery.selectedFilm;
    if (!film) return;
    if (!window.FirstRollAuth?.currentUser?.()) {
      window.FirstRollAuth?.open?.("sign-in");
      return;
    }
    button.disabled = true;
    try {
      if (!window.FirstRollAuth.saveFilm || !window.FirstRollAuth.removeSavedFilm || !window.FirstRollAuth.isFilmSaved) {
        throw new Error("Saved films are not supported by this account provider.");
      }
      if (window.FirstRollAuth.isFilmSaved(film.id)) {
        await window.FirstRollAuth.removeSavedFilm(film.id);
      } else {
        await window.FirstRollAuth.saveFilm(film);
      }
      updateSavedFilmButton();
    } catch (error) {
      button.textContent = errorInfo(error).message || "Could not update saved films";
    } finally {
      button.disabled = false;
    }
  }

  return {
    updateAccountFilmState,
    updateDeepStudyAuthState,
    updateSavedFilmButton,
    renderSavedFilms,
    onSavedFilmsClick,
    updateIntegrationDependentState,
    toggleSavedFilm,
  };
}
