import { isProductView, isThemePreference } from "./types";
import type { NavigationContext, NavigationServices, ProductViewOptions, ThemePreference } from "./types";

// Navigation, theme and build identity with validated storage/DOM-derived choices.
const THEME_STORAGE_KEY = "firstroll.theme";

export function createNavigation(context: NavigationContext, services: NavigationServices) {
  const { state, refs, runtimeConfig, systemThemeMedia } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const persistProductSession = () => services.session.persistProductSession();

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

  function readThemePreference(): ThemePreference {
    try {
      const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
      return isThemePreference(stored) ? stored : "system";
    } catch (_) {
      return "system";
    }
  }

  function setThemePreference(preference: unknown) {
    const selected = isThemePreference(preference)
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

  function setProductView(viewKey: unknown, options: ProductViewOptions = {}) {
    if (!isProductView(viewKey) || !refs.productViews[viewKey]) return;
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

  return {
    renderBuildIdentity,
    applyRuntimeMode,
    toggleTheme,
    readThemePreference,
    setThemePreference,
    syncThemeToggle,
    setProductView,
  };
}
