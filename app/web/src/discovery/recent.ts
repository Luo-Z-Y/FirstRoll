import { escapeHtml } from "../shared/html";
import type { DiscoveryQuery } from "./types";

// Recent-query storage and controls.
const RECENT_SEARCHES_KEY = "firstroll.recent-searches";

const MAX_RECENT_SEARCHES = 5;

export interface RecentContext {
  state: { discovery: { recentSearches: DiscoveryQuery[] } };
  refs: {
    recentSearches: HTMLElement;
    filmTitle: HTMLInputElement; filmYear: HTMLInputElement; filmDirector: HTMLInputElement;
    discoveryForm: HTMLFormElement;
  };
}

export function createRecent(context: RecentContext, _services?: unknown) {
  const { state, refs } = context;

  function readRecentSearches(): DiscoveryQuery[] {
    try {
      const searches: unknown = JSON.parse(window.localStorage.getItem(RECENT_SEARCHES_KEY) || "[]");
      if (!Array.isArray(searches)) return [];
      return searches
        .filter((search: unknown): search is { title: string; year?: unknown; director?: unknown } =>
          search !== null && typeof search === "object" && !Array.isArray(search)
          && "title" in search && typeof search.title === "string" && Boolean(search.title.trim()))
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

  function saveRecentSearch(search: DiscoveryQuery) {
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

  function persistRecentSearches(searches: readonly DiscoveryQuery[]) {
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

  function renderRecentSearches(searches: readonly DiscoveryQuery[] = readRecentSearches()) {
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

  function onRecentSearchClick(event: MouseEvent) {
    if (!(event.target instanceof Element)) return;
    const removeButton = event.target.closest<HTMLElement>("[data-remove-recent-search]");
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
    const button = event.target.closest<HTMLElement>("[data-recent-search]");
    if (!button) return;
    const search = state.discovery.recentSearches[Number(button.dataset.recentSearch)];
    if (!search) return;
    refs.filmTitle.value = search.title;
    refs.filmYear.value = search.year;
    refs.filmDirector.value = search.director;
    refs.discoveryForm.requestSubmit();
  }

  return {
    readRecentSearches,
    saveRecentSearch,
    persistRecentSearches,
    renderRecentSearches,
    onRecentSearchClick,
  };
}
