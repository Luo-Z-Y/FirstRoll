const assert = require("node:assert/strict");
const { test } = require("node:test");
const vm = require("node:vm");
const { buildSync } = require("esbuild");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
function moduleExports(entry) {
  const code = buildSync({ absWorkingDir: root, entryPoints: [entry], bundle: true, format: "cjs", write: false }).outputFiles[0].text;
  const context = { module: { exports: {} }, URL, Date };
  vm.runInNewContext(code, context);
  return context.module.exports;
}
const model = moduleExports("app/web/src/screenings/model.ts");
const views = moduleExports("app/web/src/screenings/views.ts");
// Values built inside the VM carry its prototypes; compare plain copies.
const plain = (value) => JSON.parse(JSON.stringify(value));
const POSTER = "/api/screenings/posters/0123456789abcdef0123456789abcdef";

const payload = {
  generated_at: "2026-10-16T12:00:00+08:00",
  range: { from: "2026-10-16", to: "2026-10-29" },
  sources: [
    { id: "afa", name: "Asian Film Archive", kind: "cinematheque", url: "https://asianfilmarchive.org/", state: "ok", count: 1 },
    { id: "shaw", name: "Shaw Theatres", kind: "multiplex", url: "https://shaw.sg/", state: "ok", count: 3, coverage_days: 7 },
    { id: "gv", name: "Golden Village", kind: "multiplex", url: "https://www.gv.com.sg/", state: "unlisted", message: "blocked" },
    { id: "bad", name: "Bad", kind: "unknown", url: "https://bad.example/", state: "ok" },
  ],
  screenings: [
    { title: "The Kiss (くちづけ, 1957)", venue: "Asian Film Archive · Oldham Theatre", source: "afa", starts_at: "2026-10-16T20:00+08:00", date: "2026-10-16", url: "https://asianfilmarchive.org/e/", poster: POSTER },
    { title: "Crawlers", venue: "Shaw Theatres Lot One", source: "shaw", starts_at: "2026-10-16T18:00+08:00", date: "2026-10-16", url: "javascript:alert(1)", poster: "http://insecure.example/p.jpg" },
    { title: "Crawlers", venue: "Shaw Theatres Jem", source: "shaw", starts_at: "2026-10-16T19:00+08:00", date: "2026-10-16" },
    { title: "Crawlers", venue: "Shaw Theatres Jem", source: "shaw", starts_at: "2026-10-17T19:00+08:00", date: "2026-10-17" },
    { title: "", venue: "x", source: "shaw", date: "2026-10-16" },
    { title: "No date", venue: "x", source: "shaw", date: "16 Oct" },
  ],
};

test("decoding keeps valid screenings and drops unsafe links and unknown source kinds", () => {
  const listings = model.decodeListings(payload);
  assert.equal(listings.screenings.length, 4);
  assert.deepEqual(plain(listings.sources.map((s) => s.id)), ["afa", "shaw", "gv"]);
  assert.equal(listings.sources[2].state, "unlisted");
  const crawlers = listings.screenings[1];
  assert.equal(crawlers.url, null);
  assert.equal(crawlers.poster, null);
  assert.equal(model.clockTime(crawlers), "18:00");
  assert.deepEqual(plain(model.decodeListings(null).screenings), []);
  assert.deepEqual(plain(model.decodeListings({ sources: "x", screenings: {} })), {
    generatedAt: "", from: "", to: "", sources: [], screenings: [],
  });
});

test("posters are accepted only as FirstRoll proxy paths, never as venue or absolute URLs", () => {
  assert.equal(model.decodeListings(payload).screenings[0].poster, POSTER);
  const hex = "0123456789abcdef0123456789abcdef";
  for (const hostile of [
    `https://cdn.peatix.com/${hex}.jpg`,
    `https://firstroll.example${POSTER}`,
    `//evil.example${POSTER}`,
    `${POSTER}?redirect=https://evil.example/`,
    `${POSTER}/../../evil`,
    ` ${POSTER}`,
    "/api/screenings/posters/0123456789ABCDEF0123456789ABCDEF",
    `/api/screenings/posters/${hex.slice(1)}`,
    `/api/screenings/posters/${hex}0`,
    "javascript:alert(1)",
    "data:image/svg+xml,<svg onload=alert(1)>",
    42, null, { src: POSTER },
  ]) {
    assert.equal(model.posterPath(hostile), null, String(hostile));
    const decoded = model.decodeListings({ ...payload, screenings: [{ ...payload.screenings[0], poster: hostile }] });
    assert.equal(decoded.screenings[0].poster, null, String(hostile));
  }
});

test("booking and venue links keep only plain HTTPS addresses", () => {
  for (const hostile of ["javascript:alert(1)", "JAVASCRIPT:alert(1)", " javascript:alert(1)", "data:text/html,x",
    "http://shaw.sg/", "https://user:secret@shaw.sg/", "//shaw.sg/", "/relative", "vbscript:x"]) {
    assert.equal(model.httpsUrl(hostile), null, hostile);
  }
  assert.equal(model.httpsUrl("https://shaw.sg/movie-details/1811"), "https://shaw.sg/movie-details/1811");
  // Normalisation percent-encodes characters that could end an attribute.
  assert.equal(model.httpsUrl('https://shaw.sg/a"onmouseover="x'), "https://shaw.sg/a%22onmouseover=%22x");
});

test("source coverage and stale copies are decoded defensively", () => {
  const listings = model.decodeListings({
    ...payload,
    sources: [
      { id: "shaw", name: "Shaw Theatres", kind: "multiplex", url: "https://shaw.sg/", state: "ok", count: 3,
        coverage_days: 7, stale: true, fetched_at: "2026-10-16T09:05:00+08:00" },
      { id: "afa", name: "AFA", kind: "cinematheque", url: "https://asianfilmarchive.org/", state: "ok",
        coverage_days: "7", stale: "yes", fetched_at: "soon" },
      { id: "x", name: "X", kind: "museum", url: "", state: "empty", coverage_days: 0 },
      { id: "y", name: "Y", kind: "museum", url: "", state: "empty", coverage_days: 2.5 },
    ],
  });
  const [shaw, afa, x, y] = listings.sources;
  assert.equal(shaw.coverageDays, 7);
  assert.equal(shaw.stale, true);
  assert.equal(shaw.fetchedAt, "2026-10-16T09:05:00+08:00");
  assert.equal(afa.coverageDays, null);
  assert.equal(afa.stale, false);
  assert.equal(afa.fetchedAt, null);
  assert.equal(x.coverageDays, null);
  assert.equal(y.coverageDays, null);
  assert.equal(model.beyondCoverage(shaw, "2026-10-22", listings.from), false);
  assert.equal(model.beyondCoverage(shaw, "2026-10-23", listings.from), true);
  assert.equal(model.beyondCoverage(afa, "2026-10-29", listings.from), false);
  // A chosen day decides on its own, whatever the range.
  assert.equal(model.beyondCoverage(shaw, "2026-10-20", listings.from, "2026-10-29"), false);
  assert.equal(model.beyondCoverage(shaw, "2026-10-23", listings.from, "2026-10-22"), true);
  assert.equal(model.stampLabel(shaw.fetchedAt), "16 Oct, 09:05");
  assert.equal(model.stampLabel(null), "");
});

test("films group across venues, and programmed venues lead the day", () => {
  const listings = model.decodeListings(payload);
  const today = model.groupFilms(listings, { day: "2026-10-16", venue: "all", query: "" });
  assert.deepEqual(plain(today.map((film) => film.title)), ["The Kiss (くちづけ, 1957)", "Crawlers"]);
  assert.equal(today[0].programmed, true);
  assert.equal(today[0].poster, POSTER);
  assert.deepEqual(plain(today[1].venues.map((v) => v.venue)), ["Shaw Theatres Jem", "Shaw Theatres Lot One"]);
  const shaw = model.groupFilms(listings, { day: "2026-10-16", venue: "shaw", query: "" });
  assert.deepEqual(plain(shaw.map((film) => film.title)), ["Crawlers"]);
  assert.equal(shaw[0].programmed, false);
  assert.deepEqual(plain(model.groupFilms(listings, { day: "2026-10-16", venue: "afa", query: "" }).map((film) => film.title)),
    ["The Kiss (くちづけ, 1957)"]);
  // A venue filter keeps only that source's showings, even for a film shown elsewhere too.
  assert.deepEqual(plain(model.groupFilms(listings, { day: null, venue: "afa", query: "crawl" })), []);
  assert.equal(model.groupFilms(listings, { day: null, venue: "all", query: "crawl" })[0].venues[0].showings.length, 2);
  assert.equal(model.groupFilms(listings, { day: null, venue: "all", query: "くちづけ" }).length, 1);
  assert.equal(model.availableDays(listings).get("2026-10-16"), 2);
  // Across every date programmed films still lead, though Crawlers' 18:00 showing is sooner than The Kiss at 20:00.
  assert.deepEqual(plain(model.groupFilms(listings, { day: null, venue: "all", query: "" }).map((film) => film.title)),
    ["The Kiss (くちづけ, 1957)", "Crawlers"]);
});

test("day counts and the all-dates total respect the venue and title query that the list applies", () => {
  const listings = model.decodeListings(payload);
  const count = (venue, query) => plain(Object.fromEntries(model.availableDays(listings, { venue, query })));
  assert.deepEqual(count("all", ""), { "2026-10-16": 2, "2026-10-17": 1 });
  assert.deepEqual(count("afa", ""), { "2026-10-16": 1 });
  assert.deepEqual(count("shaw", ""), { "2026-10-16": 1, "2026-10-17": 1 });
  assert.deepEqual(count("all", "kiss"), { "2026-10-16": 1 });
  assert.deepEqual(count("afa", "crawlers"), {});
  assert.deepEqual(count("gv", ""), {});
  assert.equal(model.filmCount(listings), 2);
  assert.equal(model.filmCount(listings, { venue: "shaw", query: "" }), 1);
  assert.equal(model.filmCount(listings, { venue: "afa", query: "crawl" }), 0);
  // Each day's count, and the all-dates total, equal the number of films that list shows.
  for (const venue of ["all", "afa", "shaw", "gv", "invented"]) {
    for (const query of ["", "crawl", "CRAWLERS", "kiss", "くちづけ", "zzz"]) {
      const counts = model.availableDays(listings, { venue, query });
      for (const day of model.dayRange(listings.from, listings.to)) {
        assert.equal(counts.get(day) || 0, model.groupFilms(listings, { day, venue, query }).length, `${venue} ${query} ${day}`);
      }
      assert.equal(model.filmCount(listings, { venue, query }), model.groupFilms(listings, { day: null, venue, query }).length,
        `${venue} ${query} all dates`);
    }
  }
});

test("every date at once lists programmed films first, then each film by soonest showing, then by title", () => {
  const at = (title, source, venue, date, time) => ({
    title, source, venue, date, ...(time ? { starts_at: `${date}T${time}+08:00` } : {}),
  });
  const listings = model.decodeListings({
    ...payload,
    screenings: [
      at("Zeta", "shaw", "Shaw Theatres Jem", "2026-10-16", "21:00"),
      at("Zeta", "shaw", "Shaw Theatres Lot One", "2026-10-16", "22:00"),
      at("Beta", "shaw", "Shaw Theatres Jem", "2026-10-17", "10:00"),
      // Undated showings sort after every timed one that day, but before the next day.
      at("Foxtrot", "shaw", "Shaw Theatres Jem", "2026-10-16"),
      at("Alpha", "afa", "Asian Film Archive", "2026-10-16"),
      at("Charlie", "shaw", "Shaw Theatres Jem", "2026-10-16", "21:00"),
      // A morning multiplex session is the soonest of all, yet it must not bury the programmed films.
      at("Golf", "shaw", "Shaw Theatres Jem", "2026-10-16", "07:00"),
      // A film's soonest showing counts, whichever venue and position it has.
      at("Echo", "shaw", "Shaw Theatres Lot One", "2026-10-20", "12:00"),
      at("Echo (NC16)", "afa", "Asian Film Archive", "2026-10-16", "09:00"),
      at("Delta", "afa", "Asian Film Archive", "2026-10-18"),
      at("Delta", "shaw", "Shaw Theatres Jem", "2026-10-18", "23:30"),
    ],
  });
  const titles = (filter) => plain(model.groupFilms(listings, filter).map((film) => film.title));
  const all = model.groupFilms(listings, { day: null, venue: "all", query: "" });
  // Programmed films (Echo, Alpha, Delta) lead even though Golf, Charlie and Zeta show sooner than Delta;
  // within each part the soonest showing leads, an undated one after the timed ones that day, and
  // Charlie and Zeta tie at 21:00, so title decides and Zeta's second venue does not.
  assert.deepEqual(plain(all.map((film) => film.title)),
    ["Echo", "Alpha", "Delta", "Golf", "Charlie", "Zeta", "Foxtrot", "Beta"]);
  assert.deepEqual(plain(all.map((film) => film.programmed)), [true, true, true, false, false, false, false, false]);
  assert.equal(model.filmCount(listings), 8);
  const echo = model.groupFilms(listings, { day: null, venue: "all", query: "echo" })[0];
  assert.deepEqual(plain(echo.venues.map((entry) => entry.venue)), ["Asian Film Archive", "Shaw Theatres Lot One"]);
  assert.equal(echo.programmed, true);
  // Narrowing to one multiplex leaves nothing programmed, so its own soonest showing alone ranks the films.
  assert.deepEqual(titles({ day: null, venue: "shaw", query: "" }), ["Golf", "Charlie", "Zeta", "Foxtrot", "Beta", "Delta", "Echo"]);
  // A group takes the shortest title among the showings it holds, so the archive's tagged title stands alone here.
  assert.deepEqual(titles({ day: null, venue: "afa", query: "" }), ["Echo (NC16)", "Alpha", "Delta"]);
  // A chosen day keeps programmed films first, then the most venues (Zeta's two), then title.
  assert.deepEqual(titles({ day: "2026-10-16", venue: "all", query: "" }),
    ["Alpha", "Echo (NC16)", "Zeta", "Charlie", "Foxtrot", "Golf"]);
  assert.deepEqual(titles({ day: null, venue: "all", query: "zzz" }), []);
  assert.equal(model.filmCount(model.decodeListings({ ...payload, screenings: [] })), 0);
});

test("with every date shown, a source is flagged only when the range runs past its coverage", () => {
  const [, shaw] = model.decodeListings(payload).sources;
  const afa = model.decodeListings(payload).sources[0];
  const once = { ...shaw, coverageDays: 1 };
  const from = "2026-10-16";
  assert.equal(shaw.coverageDays, 7);
  assert.equal(model.beyondCoverage(shaw, null, from, "2026-10-29"), true);
  // Seven days from the 16th end on the 22nd; one more day is past what FirstRoll reads.
  assert.equal(model.beyondCoverage(shaw, null, from, "2026-10-22"), false);
  assert.equal(model.beyondCoverage(shaw, null, from, "2026-10-23"), true);
  assert.equal(model.beyondCoverage(once, null, from, from), false);
  assert.equal(model.beyondCoverage(once, null, from, "2026-10-17"), true);
  // Without a known range, coverage, or start day, nothing is claimed.
  assert.equal(model.beyondCoverage(shaw, null, from, ""), false);
  assert.equal(model.beyondCoverage(shaw, null, from), false);
  assert.equal(model.beyondCoverage(shaw, null, "", "2026-10-29"), false);
  assert.equal(model.beyondCoverage(afa, null, from, "2026-10-29"), false);
});

test("venue options name each source with listings, in the API's order, with short labels", () => {
  const source = (id, name, kind, state = "ok", extra = {}) => ({ id, name, kind, url: "https://venue.example/", state, ...extra });
  const showing = (source) => ({ title: `At ${source}`, venue: `${source} hall`, source, date: "2026-10-16" });
  const listings = model.decodeListings({
    ...payload,
    sources: [
      source("filmhouse", "Filmhouse", "independent"),
      source("gv", "Golden Village", "multiplex", "unlisted", { message: "blocked" }),
      source("shaw", "Shaw Theatres", "multiplex"),
      // A failed read that still serves an earlier copy keeps its pill.
      source("sgiff", "Singapore International Film Festival", "festival", "error", { stale: true }),
      source("afa", "Asian Film Archive", "cinematheque"),
      source("peatix", "Objectifs (via Peatix)", "independent"),
      source("alliance-francaise", "Alliance Française de Singapour", "cultural"),
      source("projector", "The Projector", "independent"),
      source("oldham", "Oldham Theatre", "cinematheque", "empty"),
      // "all" belongs to the All venues pill, so a source with that id is never offered.
      source("all", "Every Cinema", "independent"),
      // Ids that name Object built-ins take the API name, never an inherited value.
      source("constructor", "Constructor Hall", "cultural"),
      source("toString", "String Theatre", "museum"),
      source("__proto__", "Proto House", "independent"),
    ],
    // Screening order differs from source order, and some screenings name no listed source.
    screenings: ["projector", "alliance-francaise", "peatix", "afa", "sgiff", "shaw", "gv", "filmhouse", "cathay", "shaw",
      "__proto__", "toString", "constructor", "all"]
      .map(showing),
  });
  assert.deepEqual(plain(model.venueOptions(listings)), [
    { id: "filmhouse", label: "Filmhouse" },
    { id: "shaw", label: "Shaw" },
    { id: "sgiff", label: "SGIFF" },
    { id: "afa", label: "Film Archive" },
    { id: "peatix", label: "Objectifs" },
    { id: "alliance-francaise", label: "Alliance Française" },
    { id: "projector", label: "The Projector" },
    { id: "constructor", label: "Constructor Hall" },
    { id: "toString", label: "String Theatre" },
    { id: "__proto__", label: "Proto House" },
  ]);
  for (const option of model.venueOptions(listings)) assert.equal(typeof option.label, "string", option.id);
  // The All venues pill is still the only "all"; the built-in ids filter like any other source.
  assert.equal(model.isVenueFilter(listings, "all"), true);
  assert.equal(model.isVenueFilter(listings, "constructor"), true);
  assert.deepEqual(plain(model.groupFilms(listings, { day: null, venue: "constructor", query: "" }).map((film) => film.title)),
    ["At constructor"]);
  assert.deepEqual(plain(model.venueOptions(model.decodeListings({ ...payload, screenings: [] }))), []);
  assert.deepEqual(plain(model.venueOptions(model.decodeListings(payload)).map((option) => option.id)), ["afa", "shaw"]);
});

test("venue labels are looked up as own entries, and unread multiplexes are the unlisted ones with a link", () => {
  assert.equal(model.venueLabel({ id: "gv", name: "Golden Village" }), "GV");
  assert.equal(model.venueLabel({ id: "afa", name: "Asian Film Archive" }), "Film Archive");
  for (const id of ["constructor", "toString", "__proto__", "hasOwnProperty", "valueOf"]) {
    assert.equal(model.venueLabel({ id, name: `Named ${id}` }), `Named ${id}`, id);
  }
  assert.equal(model.venueLabel({ id: "projector", name: "The Projector" }), "The Projector");
  const source = (id, kind, state, url = "https://venue.example/") => ({ id, name: id, kind, url, state });
  const listings = model.decodeListings({
    ...payload,
    sources: [
      source("shaw", "multiplex", "ok"),
      source("gv", "multiplex", "unlisted"),
      // An unlisted museum is named in the note, not offered as a multiplex to check.
      source("artscience", "museum", "unlisted"),
      // Without a usable HTTPS address there is nowhere to link to.
      source("eng-wah", "multiplex", "unlisted", "http://insecure.example/"),
      source("cathay", "multiplex", "error"),
    ],
  });
  assert.deepEqual(plain(model.unreadMultiplexes(listings).map((item) => [item.id, item.url])), [["gv", "https://venue.example/"]]);
  assert.deepEqual(plain(model.unreadMultiplexes(model.decodeListings(payload)).map((item) => item.id)), ["gv"]);
  assert.deepEqual(plain(model.unreadMultiplexes(model.decodeListings({ ...payload, sources: [] }))), []);
});

test("only All venues or a source with listings is a venue filter", () => {
  const listings = model.decodeListings(payload);
  for (const valid of ["all", "afa", "shaw"]) assert.equal(model.isVenueFilter(listings, valid), true, valid);
  // Unlisted, dropped, unknown and differently written ids are refused, as are non-strings.
  for (const invalid of ["gv", "bad", "sgiff", "invented", "Shaw", "shaw ", "ALL", "", "__proto__", "constructor", "toString",
    null, undefined, 42, ["shaw"], { id: "shaw" }]) {
    assert.equal(model.isVenueFilter(listings, invalid), false, String(invalid));
  }
  const empty = model.decodeListings({ ...payload, screenings: [] });
  assert.equal(model.isVenueFilter(empty, "all"), true);
  assert.equal(model.isVenueFilter(empty, "shaw"), false);
});

test("multiplex films link out to unread multiplexes; programmed-only films do not", () => {
  const listings = model.decodeListings(payload);
  const today = model.groupFilms(listings, { day: "2026-10-16", venue: "all", query: "" });
  const kiss = today.find((film) => film.title.startsWith("The Kiss"));
  const crawlers = today.find((film) => film.title === "Crawlers");
  assert.deepEqual(plain(kiss.elsewhere), []);
  assert.deepEqual(plain(crawlers.elsewhere.map((source) => [source.id, source.url])), [["gv", "https://www.gv.com.sg/"]]);
  // The link is not a venue with times, so it never counts as a showing.
  assert.equal(crawlers.venues.length, 2);
  const noGv = model.decodeListings({ ...payload, sources: payload.sources.filter((source) => source.id !== "gv") });
  assert.deepEqual(plain(model.groupFilms(noGv, { day: "2026-10-16", venue: "all", query: "" })[1].elsewhere), []);
  // Across every date the same holds, and a programmed-only venue filter drops the link with the multiplex.
  const all = model.groupFilms(listings, { day: null, venue: "all", query: "" });
  assert.deepEqual(plain(all.map((film) => [film.title, film.elsewhere.map((item) => item.id)])),
    [["The Kiss (くちづけ, 1957)", []], ["Crawlers", ["gv"]]]);
  assert.deepEqual(plain(model.groupFilms(listings, { day: null, venue: "afa", query: "" })[0].elsewhere), []);
});

test("film keys drop only bracketed rating, format and event tags", () => {
  const key = model.filmKey;
  assert.equal(key("Dune (NC16)"), "dune");
  for (const variant of ["Dune [IMAX]", "Dune (IMAX 3D)", "Dune (Dolby Atmos)", "Dune (Gold Class)", "Dune [Lux]",
    "Dune (Dreamers)", "Dune [Premiere]", "Dune (Mandarin Dub)", "Dune (With English Subtitles)",
    "Dune (PG-13)", "Dune [Sold Out]", "[4DX] Dune", "Dune (Ultra-Screen / Atmos)", "Dune（IMAX）"]) {
    assert.equal(key(variant), "dune", variant);
  }
  assert.equal(key("Amélie"), "amelie");
});

test("film keys never merge distinct films by stripping ordinary title words", () => {
  const key = model.filmKey;
  assert.equal(key("The Dreamers"), "the dreamers");
  assert.equal(key("Premiere"), "premiere");
  assert.equal(key("Lux Aeterna"), "lux aeterna");
  assert.equal(key("Gold"), "gold");
  assert.notEqual(key("Lux Aeterna"), key("Aeterna"));
  assert.notEqual(key("The Dreamers"), key("The"));
  assert.notEqual(key("Atmos Premiere"), key(""));
  assert.equal(key("IMAX: The Dreamers"), "imax the dreamers");
  // A bracket holding anything other than tags is part of the title.
  assert.equal(key("The Kiss (くちづけ, 1957)"), "the kiss くちづけ 1957");
  assert.notEqual(key("Darah-ku (My Blood, 1963)"), key("Darah-ku"));
  assert.notEqual(key("Nosferatu (1922)"), key("Nosferatu (2024)"));
  assert.notEqual(key("Dune (Part Two)"), key("Dune"));
  assert.notEqual(key("Love (and Death)"), key("Love"));
  const listings = model.decodeListings({
    ...payload,
    screenings: ["The Dreamers", "Dreamers", "Dreamers (Dreamers)"].map((title, index) => ({
      title, venue: `Shaw ${index}`, source: "shaw", date: "2026-10-16",
    })),
  });
  assert.deepEqual(plain(model.groupFilms(listings, { day: null, venue: "all", query: "" }).map((film) => film.title)),
    ["Dreamers", "The Dreamers"]);
});

test("day labels and ranges use Singapore calendar dates", () => {
  assert.equal(model.dayLabel("2026-10-16", "2026-10-16"), "Today");
  assert.equal(model.dayLabel("2026-10-17", "2026-10-16"), "Tomorrow");
  assert.equal(model.dayLabel("2026-10-18", "2026-10-16"), "Sun 18 Oct");
  assert.equal(model.addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(model.dayRange("2026-10-16", "2026-10-29").length, 14);
  assert.deepEqual(plain(model.dayRange("", "2026-10-29")), []);
  assert.equal(model.dayRange("2026-01-01", "2026-12-31").length, 31);
});

const MARKUP = '<img src=x onerror="alert(1)">';
const hostile = {
  generated_at: "2026-10-16T12:00:00+08:00",
  range: { from: "2026-10-16", to: "2026-10-20" },
  sources: [
    { id: "evil", name: `Evil ${MARKUP}`, kind: "multiplex", url: "javascript:alert(1)", state: "error",
      message: `<script>alert("m")</script>`, coverage_days: 3, stale: true, fetched_at: "2026-10-16T08:00:00+08:00" },
    { id: "full", name: "Full", kind: "independent", url: "https://filmhouse.sg/", state: "ok", count: 0, coverage_days: 5 },
    { id: "gv", name: `GV "quoted' ${MARKUP}`, kind: "multiplex", url: "https://www.gv.com.sg/", state: "unlisted",
      message: `<b>blocked</b>` },
  ],
  screenings: [{
    title: `Crawlers ${MARKUP}`, venue: `Hall "1" ${MARKUP}`, source: "evil", starts_at: "2026-10-16T18:00+08:00",
    date: "2026-10-16", url: "javascript:alert(1)", poster: "https://evil.example/p.jpg", details: `"><svg onload=alert(1)>`,
  }, {
    title: "Second", venue: "Hall 2", source: "evil", starts_at: "2026-10-16T19:00+08:00", date: "2026-10-16",
    url: 'https://shaw.sg/book?x="><script>alert(1)</script>', poster: POSTER,
  }],
};

// Escaped provider text holds no "<", so every tag left is ours: check each tag and attribute
// against what the views render, and that no attribute value smuggles a scheme or handler.
const TAGS = new Set(["article", "div", "span", "img", "header", "h3", "button", "p", "ul", "li", "strong", "small", "a"]);
const ATTRIBUTES = /^(?:class|href|target|rel|title|type|src|alt|loading|decoding|referrerpolicy|aria-(?:label|hidden|pressed)|data-screenings-[a-z-]+)$/;
function assertInert(html) {
  for (const [, name, attributes] of html.matchAll(/<\/?([a-z0-9]+)([^>]*)>/gi)) {
    assert.ok(TAGS.has(name), `unexpected <${name}>`);
    const rest = attributes.replace(/\s+([a-z-]+)(?:="([^"<>]*)")?/g, (_, attribute, value = "") => {
      assert.match(attribute, ATTRIBUTES, `unexpected ${attribute} on <${name}>`);
      if (attribute === "href") assert.match(value, /^https:\/\//);
      if (attribute === "src") assert.match(value, /^(?:https:\/\/api\.firstroll\.example)?\/api\/screenings\/posters\/[0-9a-f]{32}$/);
      return "";
    });
    assert.match(rest, /^\s*\/?$/, `unparsed attributes on <${name}>: ${rest}`);
  }
  assert.doesNotMatch(html, /javascript:/i);
}

test("film markup escapes titles, venues and details and renders only proxied posters", () => {
  const listings = model.decodeListings(hostile);
  const films = model.groupFilms(listings, { day: "2026-10-16", venue: "all", query: "" });
  const html = films.map((film) => views.filmMarkup(film, "https://api.firstroll.example")).join("");
  assertInert(html);
  assert.ok(html.includes("Crawlers &lt;img src=x onerror=&quot;alert(1)&quot;&gt;"));
  assert.ok(html.includes("Hall &quot;1&quot; &lt;img"));
  assert.ok(html.includes('title="&quot;&gt;&lt;svg onload=alert(1)&gt;"'));
  assert.ok(html.includes('data-screenings-study="Crawlers &lt;img src=x onerror=&quot;alert(1)&quot;&gt;"'));
  assert.ok(html.includes('href="https://shaw.sg/book?x=%22%3E%3Cscript%3Ealert(1)%3C/script%3E"'));
  assert.equal((html.match(/<img /g) || []).length, 1);
  assert.match(html, /<img src="https:\/\/api\.firstroll\.example\/api\/screenings\/posters\/0123456789abcdef0123456789abcdef" alt="" loading="lazy" decoding="async"/);
  // Booking links stay external navigation in a new tab, without an opener or referrer.
  for (const link of html.match(/<a [^>]+>/g)) assert.match(link, /target="_blank" rel="noopener noreferrer"/);
  // The venue-less multiplex link out is escaped too.
  assert.ok(html.includes("GV &quot;quoted&#039; &lt;img"));
  // Same-origin deployments load posters from a relative FirstRoll path.
  assert.match(views.filmMarkup(films.find((film) => film.poster), ""), /<img src="\/api\/screenings\/posters\/[0-9a-f]{32}"/);
  // Day labels added across every date are escaped like the rest.
  const allDates = model.groupFilms(listings, { day: null, venue: "all", query: "" })
    .map((film) => views.filmMarkup(film, "https://api.firstroll.example", { allDates: true, today: listings.from })).join("");
  assertInert(allDates);
  assert.ok(allDates.includes("Crawlers &lt;img src=x onerror=&quot;alert(1)&quot;&gt;"));
  assert.ok(allDates.includes('aria-label="Today · 19:00 at Hall 2, book with the venue (opens in a new tab)">Today · 19:00</a>'));
  assert.ok(allDates.includes('<span title="&quot;&gt;&lt;svg onload=alert(1)&gt;">Today · 18:00</span>'));
});

test("across every date each time carries its day; a multiplex venue shows its soonest three, others six", () => {
  const days = model.dayRange("2026-10-16", "2026-10-23");
  const booking = "https://shaw.sg/movie-details/1811";
  const listings = model.decodeListings({
    ...payload,
    screenings: [
      ...days.map((date) => ({ title: "Crawlers", venue: "Shaw Theatres Jem", source: "shaw", starts_at: `${date}T19:30+08:00`,
        date, url: booking })),
      ...Array.from({ length: 13 }, (_, hour) => ({ title: "Crawlers", venue: "Shaw Theatres Lot One", source: "shaw",
        starts_at: `2026-10-16T${String(10 + hour).padStart(2, "0")}:00+08:00`, date: "2026-10-16" })),
      ...days.map((date) => ({ title: "Tokyo Story", venue: "Asian Film Archive", source: "afa", starts_at: `${date}T14:00+08:00`,
        date, url: "https://asianfilmarchive.org/e/tokyo" })),
      // The cap follows the venue's own kind, so a programmed film's multiplex showings still stop at three.
      ...days.slice(0, 5).map((date) => ({ title: "Tokyo Story", venue: "Shaw Theatres Jem", source: "shaw",
        starts_at: `${date}T21:00+08:00`, date })),
      { title: "The Kiss", venue: "Asian Film Archive", source: "afa", date: "2026-10-17" },
      { title: "The Kiss", venue: "Asian Film Archive", source: "afa", date: "2026-10-18", url: "https://asianfilmarchive.org/e/" },
    ],
  });
  const mode = { allDates: true, today: listings.from };
  const films = model.groupFilms(listings, { day: null, venue: "all", query: "" });
  // Programmed films lead, though Crawlers' 10:00 showing is the soonest of all.
  assert.deepEqual(plain(films.map((film) => film.title)), ["Tokyo Story", "The Kiss", "Crawlers"]);
  const [tokyo, kiss, crawlers] = films;
  // Each venue's markup by name, its time labels (without the "more" link) and its "more" link.
  const venues = (html) => Object.fromEntries(html.split(/<li(?=[ >])/).slice(1)
    .map((item) => [item.match(/<strong>([^<]+)<\/strong>/)[1], item]));
  const times = (item) => Array.from(item.matchAll(/<(a|span)((?: [^>]*)?)>([^<]+)<\/\1>/g))
    .filter((match) => !match[2].includes("screenings-more")).map((match) => match[3]);
  const more = (item) => {
    const match = item.match(/<a class="screenings-more" href="([^"]+)" target="_blank" rel="noopener noreferrer">\+(\d+) more<\/a>/);
    return match ? [match[1], Number(match[2])] : null;
  };

  const html = views.filmMarkup(crawlers, "", mode);
  assertInert(html);
  const { "Shaw Theatres Jem": jem, "Shaw Theatres Lot One": lotOne, "Golden Village": elsewhere } = venues(html);
  // The unread multiplex is a link out with no times of its own, so it has no cap or "more" link.
  assert.deepEqual(times(elsewhere), ["Times on gv.com.sg ↗"]);
  assert.equal(more(elsewhere), null);
  assert.deepEqual(times(jem), ["Today · 19:30", "Tomorrow · 19:30", "Sun 18 Oct · 19:30"]);
  assert.equal((jem.match(/<a href="https:\/\/shaw\.sg\/movie-details\/1811"/g) || []).length, 3);
  assert.ok(jem.includes('aria-label="Today · 19:30 at Shaw Theatres Jem, book with the venue (opens in a new tab)"'));
  assert.deepEqual(more(jem), ["https://shaw.sg/", 5]);
  assert.doesNotMatch(jem, /Mon 19 Oct|Fri 23 Oct/);
  assert.deepEqual(times(lotOne), ["Today · 10:00", "Today · 11:00", "Today · 12:00"]);
  assert.deepEqual(more(lotOne), ["https://shaw.sg/", 10]);

  const tokyoHtml = views.filmMarkup(tokyo, "", mode);
  assertInert(tokyoHtml);
  const { "Asian Film Archive": archive, "Shaw Theatres Jem": tokyoJem } = venues(tokyoHtml);
  assert.deepEqual(times(archive), ["Today · 14:00", "Tomorrow · 14:00", "Sun 18 Oct · 14:00", "Mon 19 Oct · 14:00",
    "Tue 20 Oct · 14:00", "Wed 21 Oct · 14:00"]);
  assert.deepEqual(more(archive), ["https://asianfilmarchive.org/", 2]);
  assert.deepEqual(times(tokyoJem), ["Today · 21:00", "Tomorrow · 21:00", "Sun 18 Oct · 21:00"]);
  assert.deepEqual(more(tokyoJem), ["https://shaw.sg/", 2]);

  // An undated showing names its day and points to the venue site across every date.
  const kissHtml = views.filmMarkup(kiss, "", mode);
  assertInert(kissHtml);
  assert.deepEqual(times(kissHtml.split("<li>")[1]), ["Tomorrow · times on venue site", "Sun 18 Oct · times on venue site"]);
  assert.ok(kissHtml.includes("<span>Tomorrow · times on venue site</span>"));
  assert.ok(kissHtml.includes('aria-label="Sun 18 Oct · times on venue site at Asian Film Archive, book with the venue (opens in a new tab)">'
    + "Sun 18 Oct · times on venue site</a>"));
  assert.equal(more(kissHtml), null);
  // Without every date, an undated showing simply points to the venue site.
  assert.deepEqual(times(views.filmMarkup(kiss, "").split("<li>")[1]), ["Times on venue site", "Times on venue site"]);

  // A single day shows plain clock times, up to twelve per venue whatever its kind.
  const day = model.groupFilms(listings, { day: "2026-10-16", venue: "all", query: "" })
    .find((film) => film.title === "Crawlers");
  const dayHtml = views.filmMarkup(day, "", { allDates: false, today: listings.from });
  assert.doesNotMatch(dayHtml, /Today/);
  const lotOneDay = venues(dayHtml)["Shaw Theatres Lot One"];
  assert.deepEqual(times(lotOneDay), Array.from({ length: 12 }, (_, hour) => `${String(10 + hour).padStart(2, "0")}:00`));
  assert.deepEqual(more(lotOneDay), ["https://shaw.sg/", 1]);
  // Across the whole range, a single-day view of the same film keeps twelve per venue and no day names.
  const plainHtml = views.filmMarkup(crawlers, "");
  assert.deepEqual(times(venues(plainHtml)["Shaw Theatres Jem"]), Array(8).fill("19:30"));
  assert.equal(more(venues(plainHtml)["Shaw Theatres Jem"]), null);
  assert.deepEqual(more(venues(plainHtml)["Shaw Theatres Lot One"]), ["https://shaw.sg/", 1]);
  // Without a mode, or with allDates off, the default is the single-day view.
  assert.equal(plainHtml, views.filmMarkup(crawlers, "", null));
  assert.equal(plainHtml, views.filmMarkup(crawlers, "", { allDates: false, today: listings.from }));
  assert.doesNotMatch(plainHtml, /Tomorrow/);
});

test("source list, note, day pills and summary escape every provider value", () => {
  const listings = model.decodeListings(hostile);
  assert.equal(listings.sources[0].url, "");
  const sources = views.sourcesMarkup(listings);
  assertInert(sources);
  assert.ok(sources.includes("Evil &lt;img src=x onerror=&quot;alert(1)&quot;&gt;"));
  assert.ok(sources.includes("&lt;script&gt;alert(&quot;m&quot;)&lt;/script&gt;"));
  assert.ok(sources.includes('<small class="screenings-source-coverage">Next 3 days</small>'));
  assert.ok(sources.includes('<li class="is-error is-stale">'));
  assert.ok(sources.includes('<small class="screenings-source-stale">Showing the listings read earlier. Read 16 Oct, 08:00.</small>'));
  // A source read for the whole range needs no coverage note.
  assert.match(sources, /<li class="is-ok"><a href="https:\/\/filmhouse\.sg\/"[^>]*>Full<\/a><span>0 screenings<\/span><\/li>/);
  const plainStale = { ...listings.sources[0], message: null, fetchedAt: null };
  assert.equal(views.staleLabel(plainStale), "Showing the listings read earlier.");
  assert.equal(views.staleLabel({ ...plainStale, state: "ok", message: "the venue is slow to answer" }), "The venue is slow to answer.");
  assert.equal(views.staleLabel({ ...listings.sources[0], state: "ok" }), '<script>alert("m")</script>. Read 16 Oct, 08:00.');
  // Unlisted sources keep their own state and message; coverage is not claimed for them.
  assert.match(sources, /<li class="is-unlisted"><a href="https:\/\/www\.gv\.com\.sg\/"[^>]*>GV &quot;quoted&#039; &lt;img[^<]*<\/a><span>&lt;b&gt;blocked&lt;\/b&gt;<\/span><\/li>/);
  // The note and summary are written with textContent, so they are plain strings.
  assert.equal(views.unlistedNote(listings), `Not included: GV "quoted' ${MARKUP} (<b>blocked</b>).`);
  const pills = views.dayPillsMarkup(["2026-10-16", "2026-10-17"], listings.from, "2026-10-16", new Map([["2026-10-16", 2]]), 3);
  assert.equal(pills, '<button type="button" data-screenings-day="all" aria-pressed="false" aria-label="All dates, 3 films">All dates<span aria-hidden="true">3</span></button>'
    + '<button type="button" data-screenings-day="2026-10-16" aria-pressed="true" aria-label="Today, 2 films">Today<span aria-hidden="true">2</span></button>'
    + '<button type="button" data-screenings-day="2026-10-17" aria-pressed="false" aria-label="Tomorrow, 0 films" class="is-quiet">Tomorrow<span aria-hidden="true">0</span></button>');
  assertInert(pills);
  // With no day chosen, All dates leads pressed and every day pill is not.
  const every = views.dayPillsMarkup(["2026-10-16", "2026-10-17"], listings.from, null, new Map([["2026-10-17", 1]]), 1);
  assert.ok(every.startsWith('<button type="button" data-screenings-day="all" aria-pressed="true" aria-label="All dates, 1 film">All dates<span aria-hidden="true">1</span></button>'));
  assert.deepEqual(Array.from(every.matchAll(/data-screenings-day="([^"]+)" aria-pressed="(true|false)"/g), (match) => `${match[1]}=${match[2]}`),
    ["all=true", "2026-10-16=false", "2026-10-17=false"]);
  assert.ok(views.dayPillsMarkup([], listings.from, null, new Map(), 0)
    === '<button type="button" data-screenings-day="all" aria-pressed="true" aria-label="All dates, 0 films" class="is-quiet">All dates<span aria-hidden="true">0</span></button>');
  for (const args of [[MARKUP], [MARKUP, true], [MARKUP, true, false], [MARKUP, false, false]]) {
    assertInert(views.emptyMarkup(...args));
    assert.ok(views.emptyMarkup(...args).includes("“&lt;img src=x onerror=&quot;alert(1)&quot;&gt;”"), String(args.slice(1)));
  }
  const empty = (message) => `<p class="screenings-empty">${message}</p>`;
  // Every date, every venue and no title: nothing is listed at all.
  assert.equal(views.emptyMarkup("", true, false), empty("No screenings are listed right now."));
  // Every date otherwise: a title or a venue narrowed it.
  assert.equal(views.emptyMarkup("kiss", true, false), empty("No screenings match “kiss” with this filter."));
  assert.equal(views.emptyMarkup("kiss", true, true), empty("No screenings match “kiss” with this filter."));
  assert.equal(views.emptyMarkup("", true, true), empty("No screenings match with this filter."));
  // A single day always names the day, filtered or not.
  assert.equal(views.emptyMarkup("", false, false), empty("Nothing is listed for this day."));
  assert.equal(views.emptyMarkup("", false, true), empty("No screenings match on this day and with this filter."));
  assert.equal(views.emptyMarkup("kiss", false, false), empty("No screenings match “kiss” on this day and with this filter."));
  // The defaults are a filtered single day.
  assert.equal(views.emptyMarkup(""), views.emptyMarkup("", false, true));
  assert.equal(views.emptyMarkup("kiss"), empty("No screenings match “kiss” on this day and with this filter."));
  assert.equal(views.emptyMarkup("", true), empty("No screenings match with this filter."));
  assert.ok(views.failureMarkup(true).includes("data-screenings-retry"));
  assert.ok(views.failureMarkup(false).includes("data-screenings-retry"));
  const films = model.groupFilms(listings, { day: "2026-10-17", venue: "all", query: "" });
  assert.equal(views.summaryText(listings, films, "2026-10-17", "all"), "0 films at 0 venues · 1 source unavailable · 1 source showing earlier listings");
  assert.match(views.summaryText(listings, [], "2026-10-19", "all"), /Evil <img[^·]*: times read for the next 3 days$/);
  assert.doesNotMatch(views.summaryText(listings, [], "2026-10-18", "all"), /times read for/);
  // Only the chosen venue's coverage is mentioned.
  assert.match(views.summaryText(listings, [], "2026-10-19", "evil"), /: times read for the next 3 days$/);
  assert.doesNotMatch(views.summaryText(listings, [], "2026-10-19", "full"), /times read for/);
  // Across every date (the 16th to the 20th), a three-day source stops short; a five-day one does not.
  const everyDay = model.groupFilms(listings, { day: null, venue: "all", query: "" });
  assert.equal(views.summaryText(listings, everyDay, null, "all"),
    `2 films at 2 venues · 1 source unavailable · 1 source showing earlier listings · Evil ${MARKUP}: times read for the next 3 days`);
  assert.doesNotMatch(views.summaryText(listings, [], null, "all"), /Full: times read/);
  assert.doesNotMatch(views.summaryText(listings, [], null, "full"), /times read for/);
});

test("the summary names a source's coverage only while that source is serving listings", () => {
  const shaw = (extra) => ({ id: "shaw", name: "Shaw Theatres", kind: "multiplex", url: "https://shaw.sg/", count: 0,
    coverage_days: 7, ...extra });
  const summary = (source, day = null, venue = "all") => {
    const listings = model.decodeListings({ ...payload, sources: [payload.sources[0], source], screenings: [] });
    return views.summaryText(listings, [], day, venue);
  };
  const note = "Shaw Theatres: times read for the next 7 days";
  // Serving fresh or earlier listings, Shaw's seven days fall short of the fourteen shown.
  assert.equal(summary(shaw({ state: "ok" })), `0 films at 0 venues · ${note}`);
  assert.equal(summary(shaw({ state: "ok", stale: true })), `0 films at 0 venues · 1 source showing earlier listings · ${note}`);
  assert.equal(summary(shaw({ state: "error", stale: true })),
    `0 films at 0 venues · 1 source unavailable · 1 source showing earlier listings · ${note}`);
  assert.equal(summary(shaw({ state: "ok" }), "2026-10-24", "shaw"), `0 films at 0 venues · ${note}`);
  // A failed read with nothing to show, an empty read and an unread source claim no coverage.
  assert.equal(summary(shaw({ state: "error", message: "Shaw Theatres returned HTTP 503." })), "0 films at 0 venues · 1 source unavailable");
  assert.equal(summary(shaw({ state: "error" }), "2026-10-24"), "0 films at 0 venues · 1 source unavailable");
  assert.equal(summary(shaw({ state: "error" }), "2026-10-24", "shaw"), "0 films at 0 venues · 1 source unavailable");
  assert.equal(summary(shaw({ state: "empty" })), "0 films at 0 venues");
  assert.equal(summary(shaw({ state: "unlisted" })), "0 films at 0 venues");
});

test("venue pills follow All venues, escape every label and press only the chosen one", () => {
  const listings = model.decodeListings(hostile);
  const pills = views.venuePillsMarkup(model.venueOptions(listings), "all");
  assertInert(pills);
  // Only the source with listings is offered; the empty and unlisted ones are not.
  assert.equal(pills, '<button type="button" data-screenings-venue="all" aria-pressed="true">All venues</button>'
    + '<button type="button" data-screenings-venue="evil" aria-pressed="false">Evil &lt;img src=x onerror=&quot;alert(1)&quot;&gt;</button>');
  const options = [{ id: "shaw", label: "Shaw" }, { id: 'x" onclick="y', label: `<b>${MARKUP}</b>` }];
  const chosen = views.venuePillsMarkup(options, 'x" onclick="y');
  assertInert(chosen);
  assert.ok(chosen.includes('data-screenings-venue="x&quot; onclick=&quot;y" aria-pressed="true">&lt;b&gt;&lt;img'));
  const pressed = (html) => Array.from(html.matchAll(/aria-pressed="(true|false)"/g), (match) => match[1]);
  assert.deepEqual(pressed(chosen), ["false", "false", "true"]);
  assert.deepEqual(pressed(views.venuePillsMarkup(options, "shaw")), ["false", "true", "false"]);
  assert.deepEqual(pressed(views.venuePillsMarkup(options, "invented")), ["false", "false", "false"]);
  assert.equal(views.venuePillsMarkup([], "all"), '<button type="button" data-screenings-venue="all" aria-pressed="true">All venues</button>');
});

test("unread multiplexes follow the venue pills as escaped links out, never as filter pills", () => {
  const listings = model.decodeListings(hostile);
  const unread = model.unreadMultiplexes(listings);
  assert.deepEqual(plain(unread.map((source) => source.id)), ["gv"]);
  const html = views.venuePillsMarkup(model.venueOptions(listings), "all", unread);
  assertInert(html);
  // The short label comes from venueLabel; the hostile API name is spoken, escaped, in the label.
  assert.equal(html, '<button type="button" data-screenings-venue="all" aria-pressed="true">All venues</button>'
    + '<button type="button" data-screenings-venue="evil" aria-pressed="false">Evil &lt;img src=x onerror=&quot;alert(1)&quot;&gt;</button>'
    + '<a class="screenings-venue-link" href="https://www.gv.com.sg/" target="_blank" rel="noopener noreferrer" '
    + 'aria-label="GV &quot;quoted&#039; &lt;img src=x onerror=&quot;alert(1)&quot;&gt; times on gv.com.sg '
    + '(opens in a new tab; not read by FirstRoll)">GV ↗</a>');
  // The link carries no filter id or pressed state, so the venue click handler cannot read it as a pill.
  const link = html.match(/<a [^>]+>/)[0];
  assert.doesNotMatch(link, /data-screenings-venue|aria-pressed/);
  assert.deepEqual(Array.from(html.matchAll(/data-screenings-venue="([^"]*)"/g), (match) => match[1]), ["all", "evil"]);
  // Another unread multiplex is labelled by its API name; every value is escaped, including the address.
  const other = { id: "cathay", name: 'Cathay <b>"x"</b>', kind: "multiplex", url: 'https://cathay.example/"onmouseover="y', state: "unlisted" };
  const otherHtml = views.venuePillsMarkup([], "all", [other]);
  assertInert(otherHtml);
  assert.ok(otherHtml.endsWith('<a class="screenings-venue-link" href="https://cathay.example/&quot;onmouseover=&quot;y" target="_blank" '
    + 'rel="noopener noreferrer" aria-label="Cathay &lt;b&gt;&quot;x&quot;&lt;/b&gt; times on cathay.example '
    + '(opens in a new tab; not read by FirstRoll)">Cathay &lt;b&gt;&quot;x&quot;&lt;/b&gt; ↗</a>'));
  // A source without a readable address has nowhere to link to, so it is left out.
  assert.equal(views.venuePillsMarkup([], "all", [{ ...other, url: "" }]),
    '<button type="button" data-screenings-venue="all" aria-pressed="true">All venues</button>');
  // Links follow every pill, in the order given.
  const both = views.venuePillsMarkup([{ id: "shaw", label: "Shaw" }], "shaw", [unread[0], other]);
  assert.deepEqual(Array.from(both.matchAll(/<(button|a) /g), (match) => match[1]), ["button", "button", "a", "a"]);
  assert.deepEqual(Array.from(both.matchAll(/aria-pressed="(true|false)"/g), (match) => match[1]), ["false", "true"]);
});
