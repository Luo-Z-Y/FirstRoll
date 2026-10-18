// Listing markup. Every interpolated value is escaped; links are HTTPS-only by decoding.
import { escapeHtml } from "../shared/html";
import { beyondCoverage, clockTime, dayLabel, dayRange, kindIncludes, stampLabel } from "./model";
import type { FilmGroup, KindFilter, Listings, Screening, SourceStatus } from "./model";

const KIND_LABELS: Record<SourceStatus["kind"], string> = {
  multiplex: "Multiplex",
  independent: "Independent",
  cinematheque: "Archive",
  museum: "Museum",
  cultural: "Cultural",
  festival: "Festival",
};
const MAX_TIMES = 12;
const NEW_TAB = 'target="_blank" rel="noopener noreferrer"';

function sentence(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function plural(count: number, one: string, many = `${one}s`) {
  return `${count} ${count === 1 ? one : many}`;
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (_) {
    return "";
  }
}

function initial(title: string): string {
  return Array.from(title.trim())[0] || "";
}

export function loadingMarkup(): string {
  return `<p class="screenings-empty" data-interface-state>Gathering listings from Singapore venues…</p>`;
}

export function failureMarkup(timedOut: boolean): string {
  const reason = timedOut
    ? "Listings took too long to arrive. The venues may be slow to respond."
    : "Listings could not be loaded. The FirstRoll API may be offline.";
  return `<div class="screenings-empty" data-interface-state>
        <p>${escapeHtml(reason)}</p>
        <button type="button" class="ghost-btn inline screenings-retry" data-screenings-retry>Try again</button>
      </div>`;
}

export function emptyMarkup(query: string): string {
  const message = query
    ? `No screenings match “${query}” on this day and filter.`
    : "No screenings match this day and filter.";
  return `<p class="screenings-empty">${escapeHtml(message)}</p>`;
}

export function dayPillsMarkup(days: string[], today: string, selected: string | null, counts: Map<string, number>): string {
  return days.map((day) => {
    const count = counts.get(day) || 0;
    const label = dayLabel(day, today);
    const quiet = count ? "" : ' class="is-quiet"';
    return `<button type="button" data-screenings-day="${escapeHtml(day)}" aria-pressed="${selected === day}" aria-label="${escapeHtml(`${label}, ${plural(count, "film")}`)}"${quiet}>${escapeHtml(label)}<span aria-hidden="true">${count}</span></button>`;
  }).join("");
}

function timeMarkup(screening: Screening): string {
  const label = clockTime(screening) || "Times on venue site";
  const detail = screening.details ? ` title="${escapeHtml(screening.details)}"` : "";
  if (!screening.url) return `<span${detail}>${escapeHtml(label)}</span>`;
  const spoken = `${label} at ${screening.venue}, book with the venue (opens in a new tab)`;
  return `<a href="${escapeHtml(screening.url)}" ${NEW_TAB}${detail} aria-label="${escapeHtml(spoken)}">${escapeHtml(label)}</a>`;
}

// A plain link to the venue's own site: FirstRoll reads none of its listings.
function elsewhereMarkup(source: SourceStatus): string {
  const host = hostname(source.url);
  if (!host) return "";
  const label = `Check ${source.name} times on ${host} (opens in a new tab; not read by FirstRoll)`;
  return `<li class="is-elsewhere"><div class="screenings-venue"><strong>${escapeHtml(source.name)}</strong><small>${escapeHtml(KIND_LABELS[source.kind])} · times not read</small></div><div class="screenings-times"><a class="screenings-elsewhere" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(label)}">Times on ${escapeHtml(host)} ↗</a></div></li>`;
}

export function posterFallbackMarkup(letter: string): string {
  return `<span aria-hidden="true">${escapeHtml(letter)}</span>`;
}

// Posters come only from FirstRoll's own proxy path, prefixed with the configured API base.
function posterMarkup(group: FilmGroup, apiBase: string): string {
  const letter = initial(group.title);
  if (!group.poster) return posterFallbackMarkup(letter);
  return `<img src="${escapeHtml(`${apiBase}${group.poster}`)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-screenings-poster data-screenings-initial="${escapeHtml(letter)}" />`;
}

export function filmMarkup(group: FilmGroup, apiBase: string): string {
  const venues = group.venues.map((entry) => {
    const shown = entry.showings.slice(0, MAX_TIMES).map(timeMarkup).join("");
    const more = entry.showings.length > MAX_TIMES && entry.source?.url
      ? `<a class="screenings-more" href="${escapeHtml(entry.source.url)}" ${NEW_TAB}>+${entry.showings.length - MAX_TIMES} more</a>`
      : "";
    const kind = entry.source ? `<small>${escapeHtml(KIND_LABELS[entry.source.kind])}</small>` : "";
    return `<li><div class="screenings-venue"><strong>${escapeHtml(entry.venue)}</strong>${kind}</div><div class="screenings-times">${shown}${more}</div></li>`;
  }).join("") + group.elsewhere.map(elsewhereMarkup).join("");
  return `<article class="screenings-film${group.programmed ? " is-programmed" : ""}">
      <div class="screenings-poster">${posterMarkup(group, apiBase)}</div>
      <div class="screenings-film-body">
        <header>
          <h3>${escapeHtml(group.title)}</h3>
          <button type="button" class="screenings-study" data-screenings-study="${escapeHtml(group.title)}">Study this film</button>
        </header>
        ${group.details ? `<p class="screenings-details">${escapeHtml(group.details)}</p>` : ""}
        <ul class="screenings-venues">${venues}</ul>
      </div>
    </article>`;
}

function sourceStatus(source: SourceStatus): string {
  if (source.state === "ok") return plural(source.count, "screening");
  if (source.state === "empty") return "No listings in range";
  return sentence(source.message || (source.state === "unlisted" ? "Times not read" : "Unavailable"));
}

export function coverageLabel(days: number): string {
  return days === 1 ? "Today only" : `Next ${days} days`;
}

// The API explains a stale source (slow or failed refresh); add when its listings were read.
// An error's message is already the status line, so it is not repeated here.
export function staleLabel(source: SourceStatus): string {
  const stamp = stampLabel(source.fetchedAt);
  const message = source.state === "error" ? "" : source.message || "";
  const reason = sentence(message || "Showing the listings read earlier.");
  const ended = /[.!?]$/.test(reason) ? reason : `${reason}.`;
  return stamp ? `${ended} Read ${stamp}.` : ended;
}

export function sourcesMarkup(listings: Listings): string {
  // Coverage matters only where a source stops short of the whole listing range.
  const span = dayRange(listings.from, listings.to).length;
  return listings.sources.map((source) => {
    const name = source.url
      ? `<a href="${escapeHtml(source.url)}" ${NEW_TAB}>${escapeHtml(source.name)}</a>`
      : escapeHtml(source.name);
    const coverage = source.coverageDays !== null && source.state !== "unlisted" && (!span || source.coverageDays < span)
      ? `<small class="screenings-source-coverage">${escapeHtml(coverageLabel(source.coverageDays))}</small>`
      : "";
    const stale = source.stale
      ? `<small class="screenings-source-stale">${escapeHtml(staleLabel(source))}</small>`
      : "";
    const classes = [`is-${source.state}`, source.stale ? "is-stale" : ""].filter(Boolean).join(" ");
    return `<li class="${escapeHtml(classes)}">${name}<span>${escapeHtml(sourceStatus(source))}</span>${coverage}${stale}</li>`;
  }).join("");
}

// Venues people expect but whose times are not read are named up front, not buried.
export function unlistedNote(listings: Listings): string {
  const unlisted = listings.sources.filter((source) => source.state === "unlisted");
  return unlisted.length
    ? `Not included: ${unlisted.map((source) => `${source.name} (${source.message || "times not read"})`).join("; ")}.`
    : "";
}

export function summaryText(listings: Listings, films: FilmGroup[], day: string | null, kind: KindFilter): string {
  const venueCount = new Set(films.flatMap((film) => film.venues.map((entry) => entry.venue))).size;
  const failed = listings.sources.filter((source) => source.state === "error").length;
  const stale = listings.sources.filter((source) => source.stale).length;
  const short = listings.sources.filter((source) => source.state !== "unlisted"
    && kindIncludes(kind, source.kind) && beyondCoverage(source, day, listings.from));
  return [
    `${plural(films.length, "film")} at ${plural(venueCount, "venue")}`,
    failed ? `${plural(failed, "source")} unavailable` : "",
    stale ? `${plural(stale, "source")} showing earlier listings` : "",
    ...short.map((source) => `${source.name}: times read for the next ${plural(source.coverageDays || 0, "day")}`),
  ].filter(Boolean).join(" · ");
}
