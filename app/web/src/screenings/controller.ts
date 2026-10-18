import { availableDays, dayLabel, dayRange, decodeListings, groupFilms, initialDay, isIsoDay } from "./model";
import type { KindFilter, Listings } from "./model";
import {
  dayPillsMarkup, emptyMarkup, failureMarkup, filmMarkup, loadingMarkup, posterFallbackMarkup,
  sourcesMarkup, summaryText, unlistedNote,
} from "./views";

const FETCH_TIMEOUT_MS = 30_000;
const QUERY_DEBOUNCE_MS = 200;
const MAX_QUERY_LENGTH = 80;

export interface ScreeningsOptions {
  apiBase: string;
  fetcher?: typeof fetch;
  timeoutMs?: number;
  debounceMs?: number;
}

export interface ScreeningsState {
  phase: "idle" | "loading" | "ready" | "failed";
  listings: Listings | null;
  day: string | null;
  kind: KindFilter;
  query: string;
}

function isKindFilter(value: unknown): value is KindFilter {
  return value === "all" || value === "multiplex" || value === "programmed";
}

function normaliseQuery(value: string): string {
  return value.trim().slice(0, MAX_QUERY_LENGTH);
}

// Submit Discover's form; Safari before 16 has no requestSubmit, so dispatch the event
// its handler listens for instead (a synthetic submit event never navigates).
function submitForm(form: HTMLFormElement) {
  if (typeof form.requestSubmit === "function") {
    form.requestSubmit();
    return;
  }
  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

// Optional listing view: loads once, on first visit, from the FirstRoll API only.
export function mountScreenings(section: HTMLElement, options: ScreeningsOptions) {
  const refs = {
    kinds: section.querySelector<HTMLElement>("[data-screenings-kinds]"),
    query: section.querySelector<HTMLInputElement>("[data-screenings-query]"),
    days: section.querySelector<HTMLElement>("[data-screenings-days]"),
    dayTitle: section.querySelector<HTMLElement>("[data-screenings-day-title]"),
    summary: section.querySelector<HTMLElement>("[data-screenings-summary]"),
    list: section.querySelector<HTMLElement>("[data-screenings-list]"),
    sources: section.querySelector<HTMLElement>("[data-screenings-source-list]"),
    note: section.querySelector<HTMLElement>("[data-screenings-note]"),
  };
  if (!refs.kinds || !refs.query || !refs.days || !refs.dayTitle || !refs.summary || !refs.list || !refs.sources || !refs.note) return null;
  const { kinds, query, days, dayTitle, summary, list, sources, note } = refs;
  const fetcher = options.fetcher || window.fetch.bind(window);
  const timeoutMs = options.timeoutMs ?? FETCH_TIMEOUT_MS;
  const debounceMs = options.debounceMs ?? QUERY_DEBOUNCE_MS;
  const state: ScreeningsState = { phase: "idle", listings: null, day: null, kind: "all", query: "" };
  let queryTimer: number | null = null;

  // The summary is a polite live region: write it only when its words change.
  function announce(text: string) {
    if (summary.textContent !== text) summary.textContent = text;
  }

  async function load(): Promise<void> {
    if (state.phase === "loading") return;
    state.phase = "loading";
    list.setAttribute("aria-busy", "true");
    list.innerHTML = loadingMarkup();
    announce("");
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetcher(`${options.apiBase}/api/screenings/singapore`, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const listings = decodeListings(await response.json());
      state.listings = listings;
      state.phase = "ready";
      state.day = initialDay(listings);
      state.query = normaliseQuery(query.value || "");
      sources.innerHTML = sourcesMarkup(listings);
      const unlisted = unlistedNote(listings);
      note.hidden = !unlisted;
      note.textContent = unlisted;
      render();
    } catch (_) {
      state.phase = "failed";
      list.innerHTML = failureMarkup(controller.signal.aborted);
      announce("Listings unavailable");
    } finally {
      window.clearTimeout(timer);
      list.removeAttribute("aria-busy");
    }
  }

  function renderDays(listings: Listings) {
    const counts = availableDays(listings, { kind: state.kind, query: state.query });
    // Re-rendering replaces the pressed pill, so keep keyboard focus on the chosen day.
    const active = document.activeElement as HTMLElement | null;
    const focusDay = active && days.contains(active) ? active.dataset?.screeningsDay : undefined;
    days.innerHTML = dayPillsMarkup(dayRange(listings.from, listings.to), listings.from, state.day, counts);
    if (isIsoDay(focusDay)) days.querySelector<HTMLElement>(`[data-screenings-day="${focusDay}"]`)?.focus();
  }

  function render() {
    const listings = state.listings;
    if (!listings || state.phase !== "ready") return;
    renderDays(listings);
    kinds.querySelectorAll<HTMLElement>("[data-screenings-kind]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.screeningsKind === state.kind));
    });
    const films = groupFilms(listings, { day: state.day, kind: state.kind, query: state.query });
    dayTitle.textContent = state.day ? dayLabel(state.day, listings.from) : "Showing";
    list.innerHTML = films.length
      ? films.map((film) => filmMarkup(film, options.apiBase)).join("")
      : emptyMarkup(state.query);
    announce(summaryText(listings, films, state.day, state.kind));
  }

  // Hand a title to Discover's existing search rather than building a second lookup.
  function studyFilm(title: string) {
    const form = document.getElementById("discoveryForm") as HTMLFormElement | null;
    const field = document.getElementById("filmTitle") as HTMLInputElement | null;
    const nav = document.querySelector<HTMLElement>('.nav-link[data-product-view="discovery"]');
    if (!form || !field || !nav) return;
    field.value = title;
    for (const id of ["filmYear", "filmDirector"]) {
      const other = document.getElementById(id) as HTMLInputElement | null;
      if (other) other.value = "";
    }
    nav.click();
    submitForm(form);
  }

  function applyQuery() {
    queryTimer = null;
    const next = normaliseQuery(query.value || "");
    if (next === state.query) return;
    state.query = next;
    render();
  }

  days.addEventListener("click", (event) => {
    const button = (event.target as Element | null)?.closest<HTMLElement>("[data-screenings-day]");
    const day = button?.dataset.screeningsDay;
    if (!state.listings || !isIsoDay(day) || !dayRange(state.listings.from, state.listings.to).includes(day)) return;
    state.day = day;
    render();
  });
  kinds.addEventListener("click", (event) => {
    const kind = (event.target as Element | null)?.closest<HTMLElement>("[data-screenings-kind]")?.dataset.screeningsKind;
    if (!isKindFilter(kind)) return;
    state.kind = kind;
    render();
  });
  // Filtering waits for a pause in typing, so the live summary is not read per keystroke.
  query.addEventListener("input", () => {
    if (queryTimer !== null) window.clearTimeout(queryTimer);
    queryTimer = window.setTimeout(applyQuery, debounceMs);
  });
  list.addEventListener("click", (event) => {
    const target = event.target as Element | null;
    if (!target) return;
    if (target.closest("[data-screenings-retry]")) {
      // Loading removes the focused retry button. If focus fell to the page, a repeat failure
      // puts it on the new button and a success on the day heading; a visitor who moved on
      // during the load keeps focus where they put it.
      void load().then(() => {
        const active = document.activeElement;
        if (active && active !== document.body) return;
        const next = state.phase === "failed"
          ? list.querySelector<HTMLElement>("[data-screenings-retry]")
          : state.phase === "ready" ? dayTitle : null;
        next?.focus();
      });
      return;
    }
    const study = target.closest<HTMLElement>("[data-screenings-study]");
    if (study?.dataset.screeningsStudy) studyFilm(study.dataset.screeningsStudy);
  });
  // A poster FirstRoll cannot serve (expired or upstream failure) falls back to the initial.
  list.addEventListener("error", (event) => {
    const image = event.target as HTMLElement | null;
    if (!image || image.tagName !== "IMG" || image.dataset?.screeningsPoster === undefined) return;
    const holder = image.parentElement;
    if (holder) holder.innerHTML = posterFallbackMarkup(image.dataset.screeningsInitial || "");
  }, true);

  function onVisible() {
    if (state.phase === "idle") void load();
  }
  document.addEventListener("firstroll:view-changed", (event) => {
    if (event.detail?.view === "screenings") onVisible();
  });
  if (section.classList.contains("active")) onVisible();

  return { load, state };
}
