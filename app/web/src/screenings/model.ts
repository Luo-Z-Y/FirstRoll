// Pure listing model: decoding, day filters and grouping by film. No DOM access.
import { filmKey, searchKey } from "./titles";

export { filmKey, searchKey } from "./titles";

export type VenueKind = "multiplex" | "independent" | "cinematheque" | "museum" | "cultural" | "festival";
// "all" or the id of one source that has listings (shaw, sgiff, filmhouse and so on).
export type VenueFilter = string;
export type SourceState = "ok" | "empty" | "error" | "unlisted";

export interface Screening {
  title: string;
  venue: string;
  source: string;
  startsAt: string | null;
  date: string;
  url: string | null;
  // Always a FirstRoll path (see POSTER_PATH); never a venue's own image host.
  poster: string | null;
  details: string | null;
}

export interface SourceStatus {
  id: string;
  name: string;
  kind: VenueKind;
  url: string;
  state: SourceState;
  count: number;
  message: string | null;
  // How many days ahead FirstRoll reads this source, when the API reports it (Shaw: 7).
  coverageDays: number | null;
  // True when FirstRoll is serving an earlier copy because the latest read failed.
  stale: boolean;
  fetchedAt: string | null;
}

export interface Listings {
  generatedAt: string;
  from: string;
  to: string;
  sources: SourceStatus[];
  screenings: Screening[];
}

export interface VenueShowings {
  venue: string;
  source: SourceStatus | null;
  showings: Screening[];
}

export interface FilmGroup {
  key: string;
  title: string;
  poster: string | null;
  details: string | null;
  programmed: boolean;
  venues: VenueShowings[];
  // Multiplexes whose times are not read, offered as a link out for commercial releases.
  elsewhere: SourceStatus[];
}

export interface ListingFilter {
  // null shows every day in the listing range at once.
  day: string | null;
  venue: VenueFilter;
  query: string;
}

export interface VenueOption {
  id: string;
  label: string;
}

// Short pill labels for the sources people name in conversation; others use the API name.
const VENUE_LABELS: Record<string, string> = {
  shaw: "Shaw",
  sgiff: "SGIFF",
  filmhouse: "Filmhouse",
  afa: "Film Archive",
  peatix: "Objectifs",
  "alliance-francaise": "Alliance Française",
  gv: "GV",
};

export function venueLabel(source: Pick<SourceStatus, "id" | "name">): string {
  return Object.prototype.hasOwnProperty.call(VENUE_LABELS, source.id) ? VENUE_LABELS[source.id] : source.name;
}

const KINDS: readonly VenueKind[] = ["multiplex", "independent", "cinematheque", "museum", "cultural", "festival"];
const STATES: readonly SourceState[] = ["ok", "empty", "error", "unlisted"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
const MAX_DAYS = 31;
// FirstRoll proxies every poster, so visitors' browsers never contact venue image hosts.
export const POSTER_PATH = /^\/api\/screenings\/posters\/[0-9a-f]{32}$/;

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function optionalText(value: unknown): string | null {
  return text(value) || null;
}

function record(value: unknown): Record<string, unknown> {
  return (value && typeof value === "object" && !Array.isArray(value) ? value : {}) as Record<string, unknown>;
}

export function isIsoDay(value: unknown): value is string {
  return typeof value === "string" && ISO_DAY.test(value);
}

// Booking and venue links are user navigation, so only plain HTTPS addresses are kept.
export function httpsUrl(value: unknown): string | null {
  const raw = text(value);
  if (!raw) return null;
  try {
    const url = new URL(raw);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch (_) {
    return null;
  }
}

export function posterPath(value: unknown): string | null {
  return typeof value === "string" && POSTER_PATH.test(value) ? value : null;
}

function coverage(value: unknown): number | null {
  const days = typeof value === "number" ? value : Number.NaN;
  return Number.isInteger(days) && days > 0 && days <= MAX_DAYS ? days : null;
}

function decodeSource(raw: unknown): SourceStatus[] {
  const item = record(raw);
  const id = text(item.id);
  const kind = KINDS.find((candidate) => candidate === item.kind);
  const state = STATES.find((candidate) => candidate === item.state);
  if (!id || !kind || !state) return [];
  const fetchedAt = text(item.fetched_at);
  return [{
    id, kind, state,
    name: text(item.name) || id,
    url: httpsUrl(item.url) || "",
    count: Math.max(0, Math.floor(Number(item.count)) || 0),
    message: optionalText(item.message),
    coverageDays: coverage(item.coverage_days),
    stale: item.stale === true,
    fetchedAt: fetchedAt && !Number.isNaN(Date.parse(fetchedAt)) ? fetchedAt : null,
  }];
}

function decodeScreening(raw: unknown): Screening[] {
  const item = record(raw);
  const title = text(item.title);
  const date = text(item.date);
  const startsAt = text(item.starts_at);
  if (!title || !isIsoDay(date)) return [];
  return [{
    title, date,
    venue: text(item.venue) || text(item.source),
    source: text(item.source),
    startsAt: startsAt && !Number.isNaN(Date.parse(startsAt)) ? startsAt : null,
    url: httpsUrl(item.url),
    poster: posterPath(item.poster),
    details: optionalText(item.details),
  }];
}

export function decodeListings(payload: unknown): Listings {
  const body = record(payload);
  const range = record(body.range);
  const from = text(range.from);
  const to = text(range.to);
  return {
    generatedAt: text(body.generated_at),
    from: isIsoDay(from) ? from : "",
    to: isIsoDay(to) ? to : "",
    sources: (Array.isArray(body.sources) ? body.sources : []).flatMap(decodeSource),
    screenings: (Array.isArray(body.screenings) ? body.screenings : []).flatMap(decodeScreening),
  };
}

// Calendar arithmetic on Singapore dates, independent of the viewer's time zone.
export function addDays(isoDay: string, days: number): string {
  const [year, month, day] = isoDay.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

export function dayRange(from: string, to: string): string[] {
  if (!from || !to || from > to) return [];
  const days: string[] = [];
  for (let day = from; day <= to && days.length < MAX_DAYS; day = addDays(day, 1)) days.push(day);
  return days;
}

export function dayLabel(isoDay: string, today: string): string {
  if (isoDay === today) return "Today";
  if (isoDay === addDays(today, 1)) return "Tomorrow";
  const [year, month, day] = isoDay.split("-").map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  return `${WEEKDAYS[weekday]} ${day} ${MONTHS[month - 1]}`;
}

// Venue listings carry clock times in Singapore; read them from the ISO text directly.
export function clockTime(screening: Screening): string {
  const match = screening.startsAt?.match(/T(\d{2}):(\d{2})/);
  return match ? `${match[1]}:${match[2]}` : "";
}

// "16 Oct, 14:05" as written in the API's Singapore timestamp, or "" when unreadable.
export function stampLabel(iso: string | null): string {
  const match = iso?.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return "";
  const month = MONTHS[Number(match[2]) - 1];
  return month ? `${Number(match[3])} ${month}, ${match[4]}:${match[5]}` : "";
}

export function isProgrammed(kind: VenueKind | undefined): boolean {
  return kind !== undefined && kind !== "multiplex";
}

// One pill per source that has anything listed, in the API's source order.
export function venueOptions(listings: Listings): VenueOption[] {
  const listed = new Set(listings.screenings.map((screening) => screening.source));
  return listings.sources
    // "all" is the All venues pill, so a source can never take that id.
    .filter((source) => source.id !== "all" && source.state !== "unlisted" && listed.has(source.id))
    .map((source) => ({ id: source.id, label: venueLabel(source) }));
}

// Multiplexes FirstRoll does not read (Golden Village) are offered beside the pills as links.
export function unreadMultiplexes(listings: Listings): SourceStatus[] {
  return listings.sources.filter((source) => source.state === "unlisted" && source.kind === "multiplex"
    && Boolean(source.url));
}

export function isVenueFilter(listings: Listings, value: unknown): value is VenueFilter {
  return value === "all" || venueOptions(listings).some((option) => option.id === value);
}

// True when a source stops short of what is shown: past its last read day for a chosen
// day, or short of the whole range when every date is shown at once.
export function beyondCoverage(source: SourceStatus, day: string | null, from: string, to = ""): boolean {
  if (!from || source.coverageDays === null) return false;
  const lastRead = addDays(from, source.coverageDays);
  return day ? day >= lastRead : Boolean(to) && to >= lastRead;
}

function screeningKey(screening: Screening): string {
  return filmKey(screening.title) || searchKey(screening.title) || screening.title.toLowerCase();
}

// One predicate for the list and the day counts, so a day's count matches what it shows.
function matcher(listings: Listings, filter: Omit<ListingFilter, "day">) {
  const sources = new Map(listings.sources.map((source) => [source.id, source]));
  const query = searchKey(filter.query);
  return (screening: Screening) => {
    if (filter.venue !== "all" && screening.source !== filter.venue) return null;
    if (query && !searchKey(screening.title).includes(query)) return null;
    return { source: sources.get(screening.source) || null };
  };
}

export function availableDays(
  listings: Listings,
  filter: Omit<ListingFilter, "day"> = { venue: "all", query: "" },
): Map<string, number> {
  const matches = matcher(listings, filter);
  const counts = new Map<string, Set<string>>();
  for (const screening of listings.screenings) {
    if (!matches(screening)) continue;
    const films = counts.get(screening.date) || new Set<string>();
    films.add(screeningKey(screening));
    counts.set(screening.date, films);
  }
  return new Map(Array.from(counts, ([day, films]) => [day, films.size]));
}

// Distinct films across every day, matching what the "All dates" view lists.
export function filmCount(listings: Listings, filter: Omit<ListingFilter, "day"> = { venue: "all", query: "" }): number {
  const matches = matcher(listings, filter);
  return new Set(listings.screenings.filter((screening) => matches(screening)).map(screeningKey)).size;
}

// Sort key for a film's soonest showing; undated times sort after timed ones that day.
function soonest(group: FilmGroup): string {
  let first = "";
  for (const entry of group.venues) {
    for (const screening of entry.showings) {
      const key = screening.startsAt || `${screening.date}T99`;
      if (!first || key < first) first = key;
    }
  }
  return first;
}

export function groupFilms(listings: Listings, filter: ListingFilter): FilmGroup[] {
  const matches = matcher(listings, filter);
  const unlistedMultiplexes = unreadMultiplexes(listings);
  const groups = new Map<string, FilmGroup>();
  for (const screening of listings.screenings) {
    if (filter.day && screening.date !== filter.day) continue;
    const match = matches(screening);
    if (!match) continue;
    const { source } = match;
    const programmed = isProgrammed(source?.kind);
    const key = screeningKey(screening);
    let group = groups.get(key);
    if (!group) {
      group = { key, title: screening.title, poster: null, details: null, programmed: false, venues: [], elsewhere: [] };
      groups.set(key, group);
    }
    if (screening.title.length < group.title.length) group.title = screening.title;
    group.poster = group.poster || screening.poster;
    group.details = group.details || screening.details;
    group.programmed = group.programmed || programmed;
    if (source?.kind === "multiplex") group.elsewhere = unlistedMultiplexes;
    let venue = group.venues.find((entry) => entry.venue === screening.venue);
    if (!venue) {
      venue = { venue: screening.venue, source, showings: [] };
      group.venues.push(venue);
    }
    venue.showings.push(screening);
  }
  const ordered = Array.from(groups.values());
  for (const group of ordered) {
    group.venues.sort((a, b) => Number(isProgrammed(b.source?.kind)) - Number(isProgrammed(a.source?.kind))
      || a.venue.localeCompare(b.venue));
  }
  // Across every date, programmed films still lead (otherwise dozens of multiplex releases
  // with morning sessions bury them), and within each group the soonest showing comes first.
  if (!filter.day) {
    const first = new Map(ordered.map((group) => [group, soonest(group)]));
    return ordered.sort((a, b) => Number(b.programmed) - Number(a.programmed)
      || (first.get(a) || "").localeCompare(first.get(b) || "")
      || a.title.localeCompare(b.title));
  }
  // Within a day, programmed (archive, museum and independent) screenings are rarer, so they lead.
  return ordered.sort((a, b) => Number(b.programmed) - Number(a.programmed)
    || b.venues.length - a.venues.length
    || a.title.localeCompare(b.title));
}
