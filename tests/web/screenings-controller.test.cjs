const assert = require("node:assert/strict");
const { test } = require("node:test");
const vm = require("node:vm");
const { buildSync } = require("esbuild");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");

function bundle(entry, format) {
  return buildSync({ absWorkingDir: root, entryPoints: [entry], bundle: true, format, write: false }).outputFiles[0].text;
}
// CI runs these against the minified release adapter beside the release application.
const entrySource = process.env.FIRSTROLL_TEST_APP
  ? readFileSync(path.join(path.dirname(path.resolve(root, process.env.FIRSTROLL_TEST_APP)), "screenings.js"), "utf8")
  : bundle("app/web/screenings.ts", "iife");
const POSTER = "/api/screenings/posters/0123456789abcdef0123456789abcdef";
const SELECTOR_KEYS = {
  "[data-screenings-day]": "screeningsDay",
  "[data-screenings-venue]": "screeningsVenue",
  "[data-screenings-retry]": "screeningsRetry",
  "[data-screenings-study]": "screeningsStudy",
};

class Element {
  constructor({ dataset = {}, tagName = "DIV", parentElement = null } = {}) {
    this.dataset = dataset; this.tagName = tagName; this.parentElement = parentElement;
    this.innerHTML = ""; this.textContent = ""; this.value = ""; this.hidden = false;
    this.listeners = new Map(); this.attributes = new Map(); this.children = {};
    this.classes = new Set(); this.clicks = 0; this.focused = 0; this.dispatched = [];
    this.classList = { contains: name => this.classes.has(name), add: name => this.classes.add(name),
      remove: name => this.classes.delete(name), toggle() {} };
  }
  addEventListener(name, handler, capture = false) {
    this.listeners.set(name, [...(this.listeners.get(name) || []), { handler, capture }]);
  }
  fire(name, event = {}) {
    for (const { handler } of this.listeners.get(name) || []) handler(event);
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) { this.attributes.delete(name); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  querySelector(selector) { return this.children[selector] || null; }
  querySelectorAll(selector) { return this.children[selector] || []; }
  contains(target) {
    for (let node = target; node; node = node.parentElement) if (node === this) return true;
    return false;
  }
  closest(selector) {
    const key = SELECTOR_KEYS[selector];
    for (let node = this; node; node = node.parentElement) if (key && key in node.dataset) return node;
    return null;
  }
  click() { this.clicks += 1; }
  focus() { this.focused += 1; }
  dispatchEvent(event) { this.dispatched.push(event); return true; }
}

// The summary is the polite live region, so count every write a screen reader would hear.
class LiveRegion extends Element {
  constructor() { super(); this.writes = []; this.text = ""; }
  get textContent() { return this.text; }
  set textContent(value) { this.text = value; if (this.writes) this.writes.push(value); }
}

const unescapeHtml = value => value.replaceAll("&quot;", '"').replaceAll("&#039;", "'").replaceAll("&lt;", "<")
  .replaceAll("&gt;", ">").replaceAll("&amp;", "&");

// The venue group is written once per load and afterwards only re-pressed, so its markup is
// parsed into button and link elements the controller can query, and every rebuild is counted.
class VenueGroup extends Element {
  constructor() { super(); this.markup = ""; this.builds = 0; this.buttons = []; this.links = []; }
  get innerHTML() { return this.markup; }
  set innerHTML(value) {
    this.markup = value;
    if (!this.buttons) return; // Element's constructor writes "" before this class is ready.
    this.builds += 1;
    this.buttons = Array.from(value.matchAll(/<button type="button" data-screenings-venue="([^"]*)" aria-pressed="(true|false)">/g),
      ([, id, pressed]) => {
        const button = new Element({ dataset: { screeningsVenue: unescapeHtml(id) }, tagName: "BUTTON", parentElement: this });
        button.setAttribute("aria-pressed", pressed);
        return button;
      });
    this.links = Array.from(value.matchAll(/<a class="screenings-venue-link" href="([^"]*)"/g),
      ([, href]) => Object.assign(new Element({ tagName: "A", parentElement: this }), { href: unescapeHtml(href) }));
    this.children["[data-screenings-venue]"] = this.buttons;
  }
  button(id) { return this.buttons.find(button => button.dataset.screeningsVenue === id) || null; }
  // What a visitor would hear: each pill's id and whether it is pressed now.
  get pressed() { return this.buttons.filter(button => button.getAttribute("aria-pressed") === "true").map(button => button.dataset.screeningsVenue); }
  get ids() { return this.buttons.map(button => button.dataset.screeningsVenue); }
}

const payload = {
  generated_at: "2026-10-16T12:00:00+08:00",
  range: { from: "2026-10-16", to: "2026-10-29" },
  sources: [
    { id: "afa", name: "Asian Film Archive", kind: "cinematheque", url: "https://asianfilmarchive.org/", state: "ok", count: 1 },
    { id: "shaw", name: "Shaw Theatres", kind: "multiplex", url: "https://shaw.sg/", state: "ok", count: 3, coverage_days: 7,
      stale: true, fetched_at: "2026-10-16T09:05:00+08:00", message: "Shaw Theatres returned HTTP 503. Showing the listings read earlier." },
    { id: "filmhouse", name: "Filmhouse", kind: "independent", url: "https://filmhouse.sg/", state: "empty", coverage_days: 14 },
    { id: "gv", name: "Golden Village", kind: "multiplex", url: "https://www.gv.com.sg/", state: "unlisted",
      message: "its website blocks automated reading, so check gv.com.sg" },
    { id: "artscience", name: "ArtScience Cinema", kind: "museum", url: "https://www.marinabaysands.com/", state: "unlisted",
      message: "closed from 1 September 2026, according to the venue" },
  ],
  screenings: [
    { title: "The Kiss (くちづけ, 1957)", venue: "Asian Film Archive · Oldham Theatre", source: "afa",
      starts_at: "2026-10-16T20:00+08:00", date: "2026-10-16", url: "https://asianfilmarchive.org/e/", poster: POSTER },
    { title: "Crawlers (NC16)", venue: "Shaw Theatres Lot One", source: "shaw", starts_at: "2026-10-16T18:00+08:00",
      date: "2026-10-16", url: "https://shaw.sg/movie-details/1811", poster: "https://cdn.shaw.sg/p.jpg" },
    { title: "Crawlers", venue: "Shaw Theatres Jem", source: "shaw", starts_at: "2026-10-17T19:00+08:00", date: "2026-10-17" },
  ],
};

function harness({ active = false, note = true, venues = true, apiBase = "https://api.firstroll.example/" } = {}) {
  const section = new Element();
  if (active) section.classes.add("active");
  const names = ["query", "days", "day-title", "list", "source-list", ...(note ? ["note"] : [])];
  const refs = Object.fromEntries(names.map(name => [name, new Element()]));
  if (venues) refs.venues = new VenueGroup();
  refs.summary = new LiveRegion();
  for (const [name, ref] of Object.entries(refs)) section.children[`[data-screenings-${name}]`] = ref;
  // Day pills are re-rendered as markup, so record which replacement each re-render asks to focus.
  // Venue pills are never re-rendered, so their log must stay empty.
  const focusLog = container => {
    const log = [];
    container.querySelector = selector => {
      const target = new Element({ parentElement: container });
      log.push({ selector, target });
      return target;
    };
    return log;
  };
  const focusTargets = focusLog(refs.days);
  const venueFocusTargets = refs.venues ? focusLog(refs.venues) : [];
  const form = new Element({ tagName: "FORM" });
  form.submissions = 0;
  form.requestSubmit = () => { form.submissions += 1; };
  const fields = { filmTitle: new Element(), filmYear: new Element(), filmDirector: new Element() };
  fields.filmYear.value = "1999";
  fields.filmDirector.value = "Someone";
  const nav = new Element();
  const documentListeners = [];
  const document = {
    body: { dataset: { apiBase: "" } }, activeElement: null,
    getElementById: id => ({ "product-screenings": section, discoveryForm: form, ...fields })[id] || null,
    querySelector: selector => (selector === '.nav-link[data-product-view="discovery"]' ? nav : null),
    addEventListener: (name, handler) => documentListeners.push({ name, handler }),
  };
  const requests = [];
  const timers = new Map();
  let nextTimer = 1;
  const window = {
    FIRSTROLL_CONFIG: { apiBase },
    setTimeout: (callback, delay) => { const id = nextTimer++; timers.set(id, { callback, delay }); return id; },
    clearTimeout: id => { timers.delete(id); },
    fetch(url, options = {}) {
      return new Promise((resolve, reject) => {
        requests.push({ url, options, resolve, reject });
        options.signal?.addEventListener("abort", () => reject(new Error("aborted")));
      });
    },
  };
  vm.runInNewContext(entrySource, { document, window, AbortController, Event, URL, Date, console });
  const viewChanged = view => {
    for (const { name, handler } of documentListeners) if (name === "firstroll:view-changed") handler({ detail: { view } });
  };
  const runTimers = delay => {
    for (const [id, timer] of Array.from(timers)) {
      if (delay === undefined || timer.delay === delay) { timers.delete(id); timer.callback(); }
    }
  };
  const target = (dataset, parentElement = null) => new Element({ dataset, parentElement });
  const retryButton = new Element({ dataset: { screeningsRetry: "" } });
  refs.list.children["[data-screenings-retry]"] = retryButton;
  const dayPill = day => target({ screeningsDay: day }, refs.days);
  // Once the pills are built, press the rendered button itself; before then, a stand-in.
  const venuePill = venue => refs.venues.button(venue) || target({ screeningsVenue: venue }, refs.venues);
  // Activates a pill as a keyboard user would: focus stays on it while the click is handled.
  const press = (container, pill, { keyboard = false } = {}) => {
    if (keyboard) document.activeElement = pill;
    container.fire("click", { target: pill });
    if (keyboard) document.activeElement = null;
  };
  const chooseDay = (day, options) => press(refs.days, dayPill(day), options);
  const chooseVenue = (venue, options) => press(refs.venues, venuePill(venue), options);
  return { section, refs, focusTargets, venueFocusTargets, retryButton, form, fields, nav, document, documentListeners, requests,
    timers, viewChanged, runTimers, target, chooseDay, chooseVenue };
}

const settle = () => new Promise(resolve => setImmediate(resolve));
// Read the rendered state back out of the markup, as a visitor would see it.
const pressed = (html, name) =>
  Array.from(html.matchAll(new RegExp(`data-screenings-${name}="([^"]*)" aria-pressed="true"`, "g")), match => match[1]);
const pills = (html, name) => Array.from(html.matchAll(new RegExp(`data-screenings-${name}="([^"]*)"`, "g")), match => match[1]);
const titles = h => Array.from(h.refs.list.innerHTML.matchAll(/<h3>([^<]*)<\/h3>/g), match => match[1]);
// True only for the very same element objects, in order, not merely equal-looking ones.
const sameElements = (actual, expected) => actual.length === expected.length && actual.every((item, index) => item === expected[index]);
async function respond(h, body = payload, { ok = true, status = 200 } = {}) {
  h.requests.at(-1).resolve({ ok, status, json: async () => body });
  await settle();
}
async function loaded(options) {
  const h = harness(options);
  h.viewChanged("screenings");
  await respond(h);
  return h;
}

test("the entry does nothing without the listing note and its other hooks", () => {
  const h = harness({ note: false });
  assert.equal(h.documentListeners.length, 0);
  h.viewChanged("screenings");
  assert.equal(h.requests.length, 0);
  const { mountScreenings } = (() => {
    const context = { module: { exports: {} }, URL, Date };
    vm.runInNewContext(bundle("app/web/src/screenings/controller.ts", "cjs"), context);
    return context.module.exports;
  })();
  assert.equal(mountScreenings(h.section, { apiBase: "" }), null);
  // The venue group is a required hook too.
  const noVenues = harness({ venues: false });
  assert.equal(noVenues.documentListeners.length, 0);
  assert.equal(mountScreenings(noVenues.section, { apiBase: "" }), null);
});

test("listings load once, on the first switch to the screenings view, from FirstRoll only", async () => {
  const h = harness();
  assert.equal(h.requests.length, 0);
  h.viewChanged("festivals");
  assert.equal(h.requests.length, 0);
  h.viewChanged("screenings");
  h.viewChanged("screenings");
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].url, "https://api.firstroll.example/api/screenings/singapore");
  assert.equal(h.requests[0].options.headers.Accept, "application/json");
  assert.ok(h.requests[0].options.signal);
  assert.equal(h.refs.list.getAttribute("aria-busy"), "true");
  assert.match(h.refs.list.innerHTML, /Gathering listings/);
  await respond(h);
  assert.equal(h.refs.list.getAttribute("aria-busy"), null);
  h.viewChanged("discovery");
  h.viewChanged("screenings");
  assert.equal(h.requests.length, 1);
  assert.equal(h.timers.size, 0); // The request timeout is cleared once the response arrives.
});

test("a view already active at mount loads immediately", () => {
  const h = harness({ active: true, apiBase: "" });
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].url, "/api/screenings/singapore");
});

test("failed and timed-out requests offer a retry that loads again", async () => {
  const h = harness();
  h.viewChanged("screenings");
  await respond(h, {}, { ok: false, status: 503 });
  assert.match(h.refs.list.innerHTML, /could not be loaded[\s\S]*data-screenings-retry/);
  assert.equal(h.refs.summary.textContent, "Listings unavailable");
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  assert.equal(h.requests.length, 2);
  // A second retry while the first is in flight is ignored.
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  assert.equal(h.requests.length, 2);
  const timeout = Array.from(h.timers.values()).find(timer => timer.delay === 30000);
  assert.ok(timeout, "requests carry a 30 second timeout");
  h.runTimers(30000);
  assert.equal(h.requests[1].options.signal.aborted, true);
  await settle();
  assert.match(h.refs.list.innerHTML, /took too long[\s\S]*data-screenings-retry/);
  assert.equal(h.retryButton.focused, 1);
  assert.equal(h.refs["day-title"].focused, 0);
  // Removing the focused button drops focus to the page; a success lands it on the day heading.
  h.document.activeElement = h.document.body;
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  assert.equal(h.requests.length, 3);
  await respond(h);
  assert.match(h.refs.list.innerHTML, /screenings-film/);
  assert.equal(h.refs["day-title"].textContent, "All dates");
  assert.equal(h.refs.summary.textContent,
    "2 films at 3 venues · 1 source showing earlier listings · Shaw Theatres: times read for the next 7 days");
  assert.equal(h.refs["day-title"].focused, 1);
  assert.equal(h.retryButton.focused, 1);
});

test("a retry leaves focus alone when the visitor moved it during the load", async () => {
  const h = harness();
  h.viewChanged("screenings");
  await respond(h, {}, { ok: false, status: 503 });
  h.document.activeElement = h.refs.query;
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  await respond(h, {}, { ok: false, status: 503 });
  assert.match(h.refs.list.innerHTML, /could not be loaded[\s\S]*data-screenings-retry/);
  assert.equal(h.retryButton.focused, 0);
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  await respond(h);
  assert.match(h.refs.list.innerHTML, /screenings-film/);
  assert.equal(h.refs["day-title"].focused, 0);
  assert.equal(h.refs.query.focused, 0);
});

test("loaded listings open on All dates, listing every film once with its days, sources, note and posters", async () => {
  const h = await loaded();
  assert.equal(h.refs["day-title"].textContent, "All dates");
  assert.ok(h.refs.days.innerHTML.startsWith('<button type="button" data-screenings-day="all" aria-pressed="true" '
    + 'aria-label="All dates, 2 films">All dates<span aria-hidden="true">2</span></button>'));
  assert.match(h.refs.days.innerHTML, /data-screenings-day="2026-10-16" aria-pressed="false" aria-label="Today, 2 films"/);
  assert.match(h.refs.days.innerHTML, /data-screenings-day="2026-10-17" aria-pressed="false" aria-label="Tomorrow, 1 film"/);
  assert.deepEqual(pressed(h.refs.days.innerHTML, "day"), ["all"]);
  assert.equal((h.refs.days.innerHTML.match(/<button/g) || []).length, 15);
  // One pill per source with listings, in the API's order; the empty and unlisted sources have none.
  // Golden Village, an unread multiplex, follows as a link out; the closed museum is only in the note.
  assert.equal(h.refs.venues.innerHTML, '<button type="button" data-screenings-venue="all" aria-pressed="true">All venues</button>'
    + '<button type="button" data-screenings-venue="afa" aria-pressed="false">Film Archive</button>'
    + '<button type="button" data-screenings-venue="shaw" aria-pressed="false">Shaw</button>'
    + '<a class="screenings-venue-link" href="https://www.gv.com.sg/" target="_blank" rel="noopener noreferrer" '
    + 'aria-label="Golden Village times on gv.com.sg (opens in a new tab; not read by FirstRoll)">GV ↗</a>');
  assert.equal(h.refs.venues.builds, 1);
  assert.deepEqual(h.refs.venues.ids, ["all", "afa", "shaw"]);
  assert.deepEqual(h.refs.venues.pressed, ["all"]);
  assert.deepEqual(h.refs.venues.links.map(link => link.href), ["https://www.gv.com.sg/"]);
  assert.doesNotMatch(h.refs.venues.innerHTML, /marinabaysands|ArtScience/);
  // Each film appears once, programmed films first, and every time names its day.
  assert.deepEqual(titles(h), ["The Kiss (くちづけ, 1957)", "Crawlers"]);
  assert.match(h.refs.list.innerHTML, /aria-label="Today · 18:00 at Shaw Theatres Lot One, book with the venue \(opens in a new tab\)">Today · 18:00<\/a>/);
  assert.match(h.refs.list.innerHTML, /<span>Tomorrow · 19:00<\/span>/);
  assert.match(h.refs.list.innerHTML, />Today · 20:00<\/a>/);
  assert.equal(h.refs.summary.textContent,
    "2 films at 3 venues · 1 source showing earlier listings · Shaw Theatres: times read for the next 7 days");
  assert.equal(h.refs.note.hidden, false);
  assert.equal(h.refs.note.textContent, "Not included: Golden Village (its website blocks automated reading, so check gv.com.sg); "
    + "ArtScience Cinema (closed from 1 September 2026, according to the venue).");
  assert.match(h.refs["source-list"].innerHTML, /<li class="is-ok is-stale">[^]*<span>3 screenings<\/span><small class="screenings-source-coverage">Next 7 days<\/small><small class="screenings-source-stale">Shaw Theatres returned HTTP 503\. Showing the listings read earlier\. Read 16 Oct, 09:05\.<\/small><\/li>/);
  assert.match(h.refs["source-list"].innerHTML, /<li class="is-empty">[^]*>Filmhouse<\/a><span>No listings in range<\/span><\/li>/);
  assert.match(h.refs["source-list"].innerHTML, /<li class="is-unlisted">[^]*Closed from 1 September 2026/);
  const images = h.refs.list.innerHTML.match(/<img [^>]+>/g);
  assert.equal(images.length, 1);
  assert.match(images[0], /src="https:\/\/api\.firstroll\.example\/api\/screenings\/posters\/0123456789abcdef0123456789abcdef"/);
  assert.match(images[0], /alt="" loading="lazy" decoding="async"/);
  assert.doesNotMatch(h.refs.list.innerHTML, /cdn\.shaw\.sg/);
});

test("multiplex films alone carry the link out to unread multiplexes", async () => {
  const h = await loaded();
  const articles = h.refs.list.innerHTML.split("<article").slice(1);
  assert.equal(articles.length, 2);
  const [kiss, crawlers] = articles;
  assert.match(kiss, /The Kiss/);
  assert.doesNotMatch(kiss, /screenings-elsewhere/);
  assert.match(crawlers, /Crawlers/);
  assert.equal((crawlers.match(/class="screenings-elsewhere" href="https:\/\/www\.gv\.com\.sg\/"/g) || []).length, 1);
  // A closed museum is named in the note, never offered as somewhere to see a multiplex film.
  assert.doesNotMatch(h.refs.list.innerHTML, /marinabaysands/);
  h.chooseVenue("afa");
  assert.deepEqual(titles(h), ["The Kiss (くちづけ, 1957)"]);
  assert.doesNotMatch(h.refs.list.innerHTML, /screenings-elsewhere/);
  h.chooseVenue("shaw");
  assert.equal((h.refs.list.innerHTML.match(/class="screenings-elsewhere"/g) || []).length, 1);
});

test("a day pill narrows the list to that day and All dates returns to every film", async () => {
  const h = await loaded();
  // Keyboard activation leaves focus on the pill being pressed.
  h.chooseDay("2026-10-17", { keyboard: true });
  assert.deepEqual(pressed(h.refs.days.innerHTML, "day"), ["2026-10-17"]);
  assert.match(h.refs.days.innerHTML, /data-screenings-day="all" aria-pressed="false" aria-label="All dates, 2 films"/);
  assert.equal(h.refs["day-title"].textContent, "Tomorrow");
  assert.equal(h.refs.summary.textContent, "1 film at 1 venue · 1 source showing earlier listings");
  assert.deepEqual(titles(h), ["Crawlers"]);
  // A single day shows plain clock times.
  assert.match(h.refs.list.innerHTML, /<span>19:00<\/span>/);
  assert.doesNotMatch(h.refs.list.innerHTML, /Tomorrow ·/);
  // Re-rendering replaces that pill, so focus moves to its replacement.
  assert.equal(h.focusTargets.length, 1);
  assert.equal(h.focusTargets.at(-1).selector, '[data-screenings-day="2026-10-17"]');
  assert.equal(h.focusTargets.at(-1).target.focused, 1);
  assert.equal(h.venueFocusTargets.length, 0);
  const writes = h.refs.summary.writes.length;
  for (const invalid of ["2026-11-30", "2026-10-15", "tomorrow", "ALL", "", undefined]) {
    h.refs.days.fire("click", { target: h.target(invalid === undefined ? {} : { screeningsDay: invalid }) });
  }
  h.refs.days.fire("click", { target: null });
  assert.equal(h.refs["day-title"].textContent, "Tomorrow");
  assert.equal(h.refs.summary.writes.length, writes);
  // All dates returns to every film, and keyboard focus follows its replacement too.
  h.chooseDay("all", { keyboard: true });
  assert.equal(h.refs["day-title"].textContent, "All dates");
  assert.deepEqual(pressed(h.refs.days.innerHTML, "day"), ["all"]);
  assert.deepEqual(titles(h), ["The Kiss (くちづけ, 1957)", "Crawlers"]);
  assert.match(h.refs.list.innerHTML, /<span>Tomorrow · 19:00<\/span>/);
  assert.equal(h.focusTargets.length, 2);
  assert.equal(h.focusTargets.at(-1).selector, '[data-screenings-day="all"]');
  assert.equal(h.focusTargets.at(-1).target.focused, 1);
  // A pointer click moves no focus.
  h.chooseDay("2026-10-16");
  assert.equal(h.refs["day-title"].textContent, "Today");
  // Within a day programmed films lead, and Crawlers carries the only title shown that day.
  assert.deepEqual(titles(h), ["The Kiss (くちづけ, 1957)", "Crawlers (NC16)"]);
  assert.equal(h.focusTargets.length, 2);
  // Day choices leave the venue pills as they were built.
  assert.equal(h.refs.venues.builds, 1);
  assert.deepEqual(h.refs.venues.pressed, ["all"]);
});

test("a venue pill filters every date, updates counts and summary, and ignores unknown ids", async () => {
  const h = await loaded();
  const { venues } = h.refs;
  const [all, afa, shaw] = venues.buttons;
  h.chooseVenue("afa", { keyboard: true });
  assert.deepEqual(venues.pressed, ["afa"]);
  assert.deepEqual(venues.ids, ["all", "afa", "shaw"]);
  assert.equal(h.refs["day-title"].textContent, "All dates");
  assert.deepEqual(titles(h), ["The Kiss (くちづけ, 1957)"]);
  assert.match(h.refs.days.innerHTML, /aria-label="All dates, 1 film"/);
  assert.match(h.refs.days.innerHTML, /aria-label="Today, 1 film"/);
  assert.match(h.refs.days.innerHTML, /aria-label="Tomorrow, 0 films" class="is-quiet"/);
  // The archive reads the whole range, so Shaw's seven-day window is not mentioned for it.
  assert.equal(h.refs.summary.textContent, "1 film at 1 venue · 1 source showing earlier listings");
  // The pills are not rebuilt: the very same buttons are re-pressed, so focus never has to move.
  assert.equal(venues.builds, 1);
  assert.ok(sameElements(venues.buttons, [all, afa, shaw]));
  assert.deepEqual([all, afa, shaw].map(button => button.getAttribute("aria-pressed")), ["false", "true", "false"]);
  assert.equal(h.venueFocusTargets.length, 0);
  assert.equal(afa.focused, 0);
  assert.equal(h.focusTargets.length, 0);
  // Ids that are not offered as pills change nothing and announce nothing.
  const list = h.refs.list.innerHTML;
  const days = h.refs.days.innerHTML;
  const writes = h.refs.summary.writes.length;
  for (const invalid of ["invented", "gv", "filmhouse", "artscience", "Shaw", "", "__proto__", "constructor", undefined]) {
    h.refs.venues.fire("click", { target: h.target(invalid === undefined ? {} : { screeningsVenue: invalid }, h.refs.venues) });
  }
  h.refs.venues.fire("click", { target: null });
  // Following the Golden Village link is navigation, not a filter.
  h.refs.venues.fire("click", { target: venues.links[0] });
  assert.deepEqual(venues.pressed, ["afa"]);
  assert.equal(h.refs.list.innerHTML, list);
  assert.equal(h.refs.days.innerHTML, days);
  assert.equal(h.refs.summary.writes.length, writes);
  // A venue and a day combine; an empty day says so.
  h.chooseDay("2026-10-17");
  assert.equal(h.refs.list.innerHTML, '<p class="screenings-empty">No screenings match on this day and with this filter.</p>');
  assert.equal(h.refs.summary.textContent, "0 films at 0 venues · 1 source showing earlier listings");
  h.chooseVenue("shaw");
  assert.deepEqual(venues.pressed, ["shaw"]);
  assert.deepEqual([all, afa, shaw].map(button => button.getAttribute("aria-pressed")), ["false", "false", "true"]);
  assert.deepEqual(titles(h), ["Crawlers"]);
  assert.match(h.refs.days.innerHTML, /aria-label="All dates, 1 film"/);
  assert.match(h.refs.days.innerHTML, /aria-label="Today, 1 film"/);
  assert.match(h.refs.days.innerHTML, /aria-label="Tomorrow, 1 film"/);
  // Past the seven days FirstRoll reads from Shaw, the summary says why its listings stop.
  h.chooseDay("2026-10-24");
  assert.equal(h.refs["day-title"].textContent, "Sat 24 Oct");
  assert.equal(h.refs.summary.textContent, "0 films at 0 venues · 1 source showing earlier listings · Shaw Theatres: times read for the next 7 days");
  h.chooseDay("all");
  assert.equal(h.refs.summary.textContent,
    "1 film at 2 venues · 1 source showing earlier listings · Shaw Theatres: times read for the next 7 days");
  // All venues returns to every film; the keyboard user's button is still the focused one.
  h.chooseVenue("all", { keyboard: true });
  assert.deepEqual(venues.pressed, ["all"]);
  assert.deepEqual(titles(h), ["The Kiss (くちづけ, 1957)", "Crawlers"]);
  assert.equal(venues.builds, 1);
  assert.ok(sameElements(venues.buttons, [all, afa, shaw]));
  assert.equal(h.venueFocusTargets.length, 0);
  assert.equal(all.focused, 0);
  // The markup is still what was built at load, so nothing was re-rendered behind the buttons.
  assert.deepEqual(pressed(venues.innerHTML, "venue"), ["all"]);
  assert.deepEqual(pills(venues.innerHTML, "venue"), ["all", "afa", "shaw"]);
});

test("the Golden Village link sits beside the venue pills and is never treated as a filter", async () => {
  const h = await loaded();
  const { venues } = h.refs;
  const [link] = venues.links;
  assert.ok(link);
  assert.equal(link.href, "https://www.gv.com.sg/");
  assert.equal(venues.button("gv"), null);
  const list = h.refs.list.innerHTML;
  const days = h.refs.days.innerHTML;
  const writes = h.refs.summary.writes.length;
  // A keyboard or pointer activation of the link, or of something inside it, changes no filter.
  h.document.activeElement = link;
  venues.fire("click", { target: link });
  venues.fire("click", { target: new Element({ tagName: "SPAN", parentElement: link }) });
  h.document.activeElement = null;
  assert.deepEqual(venues.pressed, ["all"]);
  assert.equal(h.refs.list.innerHTML, list);
  assert.equal(h.refs.days.innerHTML, days);
  assert.equal(h.refs.summary.writes.length, writes);
  assert.equal(h.focusTargets.length, 0);
  assert.equal(link.focused, 0);
  assert.equal(venues.builds, 1);
  // With a venue chosen, the link still leaves it pressed.
  h.chooseVenue("shaw");
  venues.fire("click", { target: link });
  assert.deepEqual(venues.pressed, ["shaw"]);
  assert.deepEqual(titles(h), ["Crawlers"]);
  // Without an unread multiplex there is no link at all.
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  await respond(h, { ...payload, sources: payload.sources.filter(source => source.id !== "gv") });
  assert.deepEqual(venues.links, []);
  assert.doesNotMatch(venues.innerHTML, /screenings-venue-link/);
  assert.equal(venues.builds, 2);
});

test("venue choices made before the listings arrive are ignored", async () => {
  const h = harness();
  h.viewChanged("screenings");
  h.chooseVenue("shaw");
  h.chooseDay("2026-10-17");
  h.chooseDay("all");
  assert.match(h.refs.list.innerHTML, /Gathering listings/);
  // Before the listings there are no pills to press, and nothing was built for the stray clicks.
  assert.equal(h.refs.venues.builds, 0);
  await respond(h);
  assert.equal(h.refs.venues.builds, 1);
  assert.deepEqual(h.refs.venues.pressed, ["all"]);
  assert.deepEqual(pressed(h.refs.venues.innerHTML, "venue"), ["all"]);
  assert.equal(h.refs["day-title"].textContent, "All dates");
});

test("a reload opens on All dates again and keeps a venue only while it still has listings", async () => {
  const h = await loaded();
  const first = h.refs.venues.buttons;
  h.chooseVenue("shaw");
  h.chooseDay("2026-10-17");
  assert.equal(h.refs["day-title"].textContent, "Tomorrow");
  assert.equal(h.refs.venues.builds, 1);
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  await respond(h);
  assert.equal(h.refs["day-title"].textContent, "All dates");
  assert.deepEqual(pressed(h.refs.days.innerHTML, "day"), ["all"]);
  // Each load builds the pills once more, from the new listings, with the kept venue pressed.
  assert.equal(h.refs.venues.builds, 2);
  assert.ok(!sameElements(h.refs.venues.buttons, first));
  assert.deepEqual(pressed(h.refs.venues.innerHTML, "venue"), ["shaw"]);
  assert.deepEqual(h.refs.venues.pressed, ["shaw"]);
  assert.deepEqual(titles(h), ["Crawlers"]);
  assert.match(h.refs.list.innerHTML, /<span>Tomorrow · 19:00<\/span>/);
  // Shaw lists nothing this time, so its pill goes and the filter returns to every venue.
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  await respond(h, { ...payload, screenings: payload.screenings.filter(screening => screening.source !== "shaw") });
  assert.equal(h.refs.venues.builds, 3);
  assert.deepEqual(pills(h.refs.venues.innerHTML, "venue"), ["all", "afa"]);
  assert.deepEqual(pressed(h.refs.venues.innerHTML, "venue"), ["all"]);
  assert.deepEqual(h.refs.venues.ids, ["all", "afa"]);
  assert.deepEqual(h.refs.venues.pressed, ["all"]);
  assert.deepEqual(h.refs.venues.links.map(link => link.href), ["https://www.gv.com.sg/"]);
  assert.deepEqual(titles(h), ["The Kiss (くちづけ, 1957)"]);
  assert.equal(h.refs.summary.textContent,
    "1 film at 1 venue · 1 source showing earlier listings · Shaw Theatres: times read for the next 7 days");
});

test("title filtering waits for a pause in typing before updating the list and live summary", async () => {
  const h = await loaded();
  const writes = h.refs.summary.writes.length;
  const before = h.refs.list.innerHTML;
  for (const value of ["k", "ki", "kis", "kiss"]) {
    h.refs.query.value = value;
    h.refs.query.fire("input");
  }
  assert.equal(h.timers.size, 1);
  assert.equal(Array.from(h.timers.values())[0].delay, 200);
  assert.equal(h.refs.list.innerHTML, before);
  assert.equal(h.refs.summary.writes.length, writes);
  h.runTimers(200);
  assert.equal(h.refs.summary.writes.length, writes + 1);
  assert.equal(h.refs.summary.textContent,
    "1 film at 1 venue · 1 source showing earlier listings · Shaw Theatres: times read for the next 7 days");
  assert.deepEqual(titles(h), ["The Kiss (くちづけ, 1957)"]);
  assert.match(h.refs.days.innerHTML, /aria-label="All dates, 1 film"/);
  assert.match(h.refs.days.innerHTML, /aria-label="Today, 1 film"/);
  assert.match(h.refs.days.innerHTML, /aria-label="Tomorrow, 0 films"/);
  // Typing back to the same query, or a change that leaves the summary as it was, says nothing new.
  h.refs.query.value = "kiss ";
  h.refs.query.fire("input");
  h.runTimers(200);
  assert.equal(h.refs.summary.writes.length, writes + 1);
  h.refs.query.value = "zzz";
  h.refs.query.fire("input");
  h.runTimers(200);
  assert.equal(h.refs.list.innerHTML, '<p class="screenings-empty">No screenings match “zzz” with this filter.</p>');
  assert.match(h.refs.days.innerHTML, /aria-label="All dates, 0 films" class="is-quiet"/);
  h.chooseDay("2026-10-16");
  assert.equal(h.refs.list.innerHTML, '<p class="screenings-empty">No screenings match “zzz” on this day and with this filter.</p>');
  // A venue filter with a title keeps the all-dates wording.
  h.chooseDay("all");
  h.chooseVenue("afa");
  assert.equal(h.refs.list.innerHTML, '<p class="screenings-empty">No screenings match “zzz” with this filter.</p>');
});

test("with nothing listed at all, every date and each day say so plainly and a title filter is named", async () => {
  const h = harness();
  h.viewChanged("screenings");
  await respond(h, { ...payload, screenings: [] });
  assert.equal(h.refs["day-title"].textContent, "All dates");
  assert.equal(h.refs.list.innerHTML, '<p class="screenings-empty">No screenings are listed right now.</p>');
  // No source has listings, so All venues is the only pill; the unread multiplex is still linked.
  assert.deepEqual(h.refs.venues.ids, ["all"]);
  assert.deepEqual(h.refs.venues.pressed, ["all"]);
  assert.equal(h.refs.venues.links.length, 1);
  assert.match(h.refs.days.innerHTML, /aria-label="All dates, 0 films" class="is-quiet"/);
  h.chooseDay("2026-10-16");
  assert.equal(h.refs.list.innerHTML, '<p class="screenings-empty">Nothing is listed for this day.</p>');
  h.chooseDay("all");
  assert.equal(h.refs.list.innerHTML, '<p class="screenings-empty">No screenings are listed right now.</p>');
  h.refs.query.value = "kiss";
  h.refs.query.fire("input");
  h.runTimers(200);
  assert.equal(h.refs.list.innerHTML, '<p class="screenings-empty">No screenings match “kiss” with this filter.</p>');
});

test("Study this film hands the title to Discover, with or without requestSubmit", async () => {
  const h = await loaded();
  // Across every date each film's button carries the group's title once.
  assert.deepEqual(Array.from(h.refs.list.innerHTML.matchAll(/data-screenings-study="([^"]*)"/g), match => match[1]),
    ["The Kiss (くちづけ, 1957)", "Crawlers"]);
  h.refs.list.fire("click", { target: h.target({ screeningsStudy: "Crawlers (NC16)" }) });
  assert.equal(h.fields.filmTitle.value, "Crawlers (NC16)");
  assert.equal(h.fields.filmYear.value, "");
  assert.equal(h.fields.filmDirector.value, "");
  assert.equal(h.nav.clicks, 1);
  assert.equal(h.form.submissions, 1);
  assert.equal(h.form.dispatched.length, 0);
  h.form.requestSubmit = undefined;
  h.refs.list.fire("click", { target: h.target({ screeningsStudy: "The Kiss" }) });
  assert.equal(h.fields.filmTitle.value, "The Kiss");
  assert.equal(h.nav.clicks, 2);
  assert.equal(h.form.dispatched.length, 1);
  assert.equal(h.form.dispatched[0].type, "submit");
  assert.equal(h.form.dispatched[0].cancelable, true);
  // Clicks elsewhere in the list do nothing.
  h.refs.list.fire("click", { target: h.target({}) });
  h.refs.list.fire("click", { target: null });
  assert.equal(h.nav.clicks, 2);
});

test("a poster FirstRoll cannot serve falls back to the title initial", async () => {
  const h = await loaded();
  const listener = h.refs.list.listeners.get("error")[0];
  assert.equal(listener.capture, true);
  const holder = new Element();
  holder.innerHTML = "<img>";
  listener.handler({ target: new Element({ tagName: "IMG", dataset: { screeningsPoster: "", screeningsInitial: "<K>" }, parentElement: holder }) });
  assert.equal(holder.innerHTML, '<span aria-hidden="true">&lt;K&gt;</span>');
  const other = new Element();
  other.innerHTML = "unchanged";
  listener.handler({ target: new Element({ tagName: "IMG", dataset: {}, parentElement: other }) });
  listener.handler({ target: new Element({ tagName: "SPAN", dataset: { screeningsPoster: "" }, parentElement: other }) });
  assert.equal(other.innerHTML, "unchanged");
});
