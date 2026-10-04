import { errorInfo, json, shape } from "../api/decode";
import { readApiError } from "../api/errors";
import { criticismBundle } from "../api/models";
import type { AppContext } from "../context";
import type { Services } from "../services";
import { escapeHtml } from "../shared/html";

// Criticism retrieval/structuring and active-provider controls.
export function createCriticism(context: AppContext, services: () => Services) {
  const { state, refs, runtimeConfig } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const criticalResearchMarkup: Services["criticismViews"]["criticalResearchMarkup"] = (...args) => services().criticismViews.criticalResearchMarkup(...args);
  const criticismSource: Services["criticismViews"]["criticismSource"] = (...args) => services().criticismViews.criticismSource(...args);
  const criticismBundleForRoute: Services["criticismViews"]["criticismBundleForRoute"] = (...args) => services().criticismViews.criticismBundleForRoute(...args);
  const discoveryApiBase: Services["ui"]["discoveryApiBase"] = (...args) => services().ui.discoveryApiBase(...args);
  const fetchProgressMarkup: Services["ui"]["fetchProgressMarkup"] = (...args) => services().ui.fetchProgressMarkup(...args);
  const focusElement: Services["ui"]["focusElement"] = (...args) => services().ui.focusElement(...args);
  const focusInterfaceState: Services["ui"]["focusInterfaceState"] = (...args) => services().ui.focusInterfaceState(...args);

  async function selectCriticismSource(button: HTMLButtonElement): Promise<void> {
    const provider = button.dataset.criticismSource;
    const film = state.discovery.selectedFilm;
    const output = refs.filmDetail.querySelector<HTMLElement>("[data-critical-output]");
    if (!film || !output || !provider) return;
    state.discovery.activeCriticismProvider = provider;
    updateCriticismSourceTabs(provider);
    const bundle = criticismBundleForRoute(film.critical_research?.bundles || {}, provider);
    if (bundle) {
      output.setAttribute("aria-busy", "false");
      output.innerHTML = criticalResearchMarkup(bundle);
      return;
    }
    await loadProviderCriticism(button, provider);
  }

  async function loadProviderCriticism(button: HTMLButtonElement, providerOverride: string | null | undefined = null): Promise<void> {
    const film = state.discovery.selectedFilm;
    const output = refs.filmDetail.querySelector<HTMLElement>("[data-critical-output]");
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
        { method: "POST", signal: state.discovery.detailController?.signal },
      );
      if (!response.ok) throw new Error(await readApiError(response));
      const data = await json(response, shape({ critical_research: criticismBundle }));
      if (!data.critical_research) throw new Error("The criticism response is missing.");
      if (state.discovery.selectedFilm !== film) return;
      const bundle = data.critical_research;
      const research = film.critical_research ||= {};
      research.bundles = research.bundles || {};
      research.bundles[String(bundle.provider || provider).toLowerCase()] = bundle;
      if (state.discovery.activeCriticismProvider === provider) {
        output.innerHTML = criticalResearchMarkup(bundle);
      }
      updateCriticismSourceTabs(state.discovery.activeCriticismProvider);
      if (!runtimeConfig.publicMode) {
        const structureButton = state.discovery.activeCriticismProvider === provider
          ? output.querySelector<HTMLButtonElement>(`[data-structure-criticism="${provider}"]`)
          : null;
        await structureProviderCriticism(provider, structureButton);
      }
    } catch (error) {
      if (errorInfo(error).name === "AbortError" || state.discovery.selectedFilm !== film) return;
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
      if (state.discovery.selectedFilm === film) {
        if (state.discovery.activeCriticismProvider === provider) {
          output.setAttribute("aria-busy", "false");
        }
        button.disabled = false;
        button.textContent = originalLabel;
      }
    }
  }

  async function structureProviderCriticism(provider: string | undefined, button: HTMLButtonElement | null = null): Promise<void> {
    const film = state.discovery.selectedFilm;
    const output = refs.filmDetail.querySelector<HTMLElement>("[data-critical-output]");
    if (!film || !output || !provider) return;
    const status = output.querySelector<HTMLElement>(`[data-structure-status="${provider}"]`);
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
      output.querySelector<HTMLElement>("[data-active-fetch-progress]")?.remove();
      output.insertAdjacentHTML("afterbegin", fetchProgressMarkup("DeepSeek is structuring the fetched reviews…"));
    }
    try {
      const response = await fetch(
        `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/criticism/${provider}/structure`,
        { method: "POST", signal: state.discovery.detailController?.signal },
      );
      if (!response.ok) throw new Error(await readApiError(response));
      const data = await json(response, shape({ critical_research: criticismBundle }));
      if (!data.critical_research) throw new Error("The criticism response is missing.");
      if (state.discovery.selectedFilm !== film) return;
      const bundle = data.critical_research;
      const research = film.critical_research ||= {};
      research.bundles = research.bundles || {};
      research.bundles[String(bundle.provider || provider).toLowerCase()] = bundle;
      if (state.discovery.activeCriticismProvider === provider) {
        output.innerHTML = criticalResearchMarkup(bundle);
      }
    } catch (error) {
      if (errorInfo(error).name === "AbortError" || state.discovery.selectedFilm !== film) return;
      console.warn("Criticism structuring did not complete", error);
      if (state.discovery.activeCriticismProvider !== provider) return;
      output.querySelector<HTMLElement>("[data-active-fetch-progress]")?.remove();
      const currentStatus = output.querySelector<HTMLElement>(`[data-structure-status="${provider}"]`);
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
      if (state.discovery.selectedFilm === film && state.discovery.activeCriticismProvider === provider) {
        output.setAttribute("aria-busy", "false");
      }
    }
  }

  function updateCriticismSourceTabs(activeProvider: string | null): void {
    const film = state.discovery.selectedFilm;
    const bundles = film?.critical_research?.bundles || {};
    refs.filmDetail.querySelectorAll<HTMLElement>("[data-criticism-source]").forEach((button) => {
      const active = button.dataset.criticismSource === activeProvider;
      const loaded = Boolean(criticismBundleForRoute(bundles, button.dataset.criticismSource));
      button.classList.toggle("is-active", active);
      button.classList.toggle("is-loaded", loaded);
      button.setAttribute("aria-selected", String(active));
      button.setAttribute("tabindex", active ? "0" : "-1");
    });
    const activeTab = refs.filmDetail.querySelector<HTMLElement>(
      `[data-criticism-source="${CSS.escape(activeProvider || "")}"]`,
    );
    const panel = refs.filmDetail.querySelector<HTMLElement>("#dossier-criticism-panel");
    if (activeTab && panel) {
      panel.setAttribute("aria-labelledby", activeTab.id);
      panel.removeAttribute("aria-label");
    }
  }

  return {
    selectCriticismSource,
    loadProviderCriticism,
    structureProviderCriticism,
    updateCriticismSourceTabs,
  };
}
