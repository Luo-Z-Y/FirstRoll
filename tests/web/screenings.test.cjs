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
  assert.equal(model.stampLabel(shaw.fetchedAt), "16 Oct, 09:05");
  assert.equal(model.stampLabel(null), "");
});

test("films group across venues, and programmed venues lead the day", () => {
  const listings = model.decodeListings(payload);
  const today = model.groupFilms(listings, { day: "2026-10-16", kind: "all", query: "" });
  assert.deepEqual(plain(today.map((film) => film.title)), ["The Kiss (くちづけ, 1957)", "Crawlers"]);
  assert.equal(today[0].programmed, true);
  assert.equal(today[0].poster, POSTER);
  assert.deepEqual(plain(today[1].venues.map((v) => v.venue)), ["Shaw Theatres Jem", "Shaw Theatres Lot One"]);
  assert.equal(model.groupFilms(listings, { day: "2026-10-16", kind: "multiplex", query: "" }).length, 1);
  assert.equal(model.groupFilms(listings, { day: "2026-10-16", kind: "programmed", query: "" })[0].title, "The Kiss (くちづけ, 1957)");
  assert.equal(model.groupFilms(listings, { day: null, kind: "all", query: "crawl" })[0].venues[0].showings.length, 2);
  assert.equal(model.groupFilms(listings, { day: null, kind: "all", query: "くちづけ" }).length, 1);
  assert.equal(model.availableDays(listings).get("2026-10-16"), 2);
  assert.equal(model.initialDay(listings), "2026-10-16");
});

test("day counts respect the venue kind and title query that the list applies", () => {
  const listings = model.decodeListings(payload);
  const count = (kind, query) => plain(Object.fromEntries(model.availableDays(listings, { kind, query })));
  assert.deepEqual(count("all", ""), { "2026-10-16": 2, "2026-10-17": 1 });
  assert.deepEqual(count("programmed", ""), { "2026-10-16": 1 });
  assert.deepEqual(count("multiplex", ""), { "2026-10-16": 1, "2026-10-17": 1 });
  assert.deepEqual(count("all", "kiss"), { "2026-10-16": 1 });
  assert.deepEqual(count("programmed", "crawlers"), {});
  // Each day's count equals the number of films that day's list shows.
  for (const kind of ["all", "multiplex", "programmed"]) {
    for (const query of ["", "crawl", "kiss", "zzz"]) {
      const counts = model.availableDays(listings, { kind, query });
      for (const day of model.dayRange(listings.from, listings.to)) {
        assert.equal(counts.get(day) || 0, model.groupFilms(listings, { day, kind, query }).length, `${kind} ${query} ${day}`);
      }
    }
  }
});

test("a day with nothing showing today opens on the first day that has films", () => {
  const listings = model.decodeListings({ ...payload, screenings: [payload.screenings[3]] });
  assert.equal(model.initialDay(listings), "2026-10-17");
  assert.equal(model.initialDay(model.decodeListings({ ...payload, screenings: [] })), "2026-10-16");
  assert.equal(model.initialDay(model.decodeListings({ ...payload, range: {} })), null);
});

test("multiplex films link out to unread multiplexes; programmed-only films do not", () => {
  const listings = model.decodeListings(payload);
  const today = model.groupFilms(listings, { day: "2026-10-16", kind: "all", query: "" });
  const kiss = today.find((film) => film.title.startsWith("The Kiss"));
  const crawlers = today.find((film) => film.title === "Crawlers");
  assert.deepEqual(plain(kiss.elsewhere), []);
  assert.deepEqual(plain(crawlers.elsewhere.map((source) => [source.id, source.url])), [["gv", "https://www.gv.com.sg/"]]);
  // The link is not a venue with times, so it never counts as a showing.
  assert.equal(crawlers.venues.length, 2);
  const noGv = model.decodeListings({ ...payload, sources: payload.sources.filter((source) => source.id !== "gv") });
  assert.deepEqual(plain(model.groupFilms(noGv, { day: "2026-10-16", kind: "all", query: "" })[1].elsewhere), []);
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
  assert.deepEqual(plain(model.groupFilms(listings, { day: null, kind: "all", query: "" }).map((film) => film.title)),
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
  const films = model.groupFilms(listings, { day: "2026-10-16", kind: "all", query: "" });
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
  const pills = views.dayPillsMarkup(["2026-10-16", "2026-10-17"], listings.from, "2026-10-16", new Map([["2026-10-16", 2]]));
  assert.equal(pills, '<button type="button" data-screenings-day="2026-10-16" aria-pressed="true" aria-label="Today, 2 films">Today<span aria-hidden="true">2</span></button>'
    + '<button type="button" data-screenings-day="2026-10-17" aria-pressed="false" aria-label="Tomorrow, 0 films" class="is-quiet">Tomorrow<span aria-hidden="true">0</span></button>');
  assertInert(views.emptyMarkup(MARKUP));
  assert.ok(views.failureMarkup(true).includes("data-screenings-retry"));
  assert.ok(views.failureMarkup(false).includes("data-screenings-retry"));
  const films = model.groupFilms(listings, { day: "2026-10-17", kind: "all", query: "" });
  assert.equal(views.summaryText(listings, films, "2026-10-17", "all"), "0 films at 0 venues · 1 source unavailable · 1 source showing earlier listings");
  assert.match(views.summaryText(listings, [], "2026-10-19", "all"), /Evil <img[^·]* lists only the next 3 days$/);
  assert.doesNotMatch(views.summaryText(listings, [], "2026-10-18", "all"), /lists only/);
  assert.doesNotMatch(views.summaryText(listings, [], "2026-10-19", "programmed"), /lists only/);
});
