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
  "[data-screenings-kind]": "screeningsKind",
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

function harness({ active = false, note = true, apiBase = "https://api.firstroll.example/" } = {}) {
  const section = new Element();
  if (active) section.classes.add("active");
  const names = ["kinds", "query", "days", "day-title", "list", "source-list", ...(note ? ["note"] : [])];
  const refs = Object.fromEntries(names.map(name => [name, new Element()]));
  refs.summary = new LiveRegion();
  for (const [name, ref] of Object.entries(refs)) section.children[`[data-screenings-${name}]`] = ref;
  const kindButtons = ["all", "programmed", "multiplex"].map(kind =>
    new Element({ dataset: { screeningsKind: kind }, parentElement: refs.kinds }));
  refs.kinds.children["[data-screenings-kind]"] = kindButtons;
  const focusTargets = [];
  refs.days.querySelector = selector => {
    const target = new Element({ parentElement: refs.days });
    focusTargets.push({ selector, target });
    return target;
  };
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
  return { section, refs, kindButtons, focusTargets, retryButton, form, fields, nav, document, documentListeners, requests, timers,
    viewChanged, runTimers, target };
}

const settle = () => new Promise(resolve => setImmediate(resolve));
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
  h.refs.list.fire("click", { target: h.target({ screeningsRetry: "" }) });
  assert.equal(h.requests.length, 3);
  await respond(h);
  assert.match(h.refs.list.innerHTML, /screenings-film/);
  assert.equal(h.refs.summary.textContent, "2 films at 2 venues · 1 source showing earlier listings");
});

test("loaded listings render days, sources, the unlisted note and proxied posters", async () => {
  const h = await loaded();
  assert.equal(h.refs["day-title"].textContent, "Today");
  assert.match(h.refs.days.innerHTML, /data-screenings-day="2026-10-16" aria-pressed="true" aria-label="Today, 2 films"/);
  assert.match(h.refs.days.innerHTML, /data-screenings-day="2026-10-17" aria-pressed="false" aria-label="Tomorrow, 1 film"/);
  assert.equal((h.refs.days.innerHTML.match(/<button/g) || []).length, 14);
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
  h.kindButtons[0].parentElement.fire("click", { target: h.kindButtons[1] });
  assert.doesNotMatch(h.refs.list.innerHTML, /screenings-elsewhere/);
});

test("day and kind choices update pressed states, counts, heading and summary", async () => {
  const h = await loaded();
  // Keyboard activation leaves focus on the pill being pressed.
  const pill = h.target({ screeningsDay: "2026-10-17" }, h.refs.days);
  h.document.activeElement = pill;
  h.refs.days.fire("click", { target: pill });
  assert.match(h.refs.days.innerHTML, /data-screenings-day="2026-10-17" aria-pressed="true"/);
  assert.match(h.refs.days.innerHTML, /data-screenings-day="2026-10-16" aria-pressed="false"/);
  assert.equal(h.refs["day-title"].textContent, "Tomorrow");
  assert.equal(h.refs.summary.textContent, "1 film at 1 venue · 1 source showing earlier listings");
  // Re-rendering replaces that pill, so focus moves to its replacement.
  assert.equal(h.focusTargets.length, 1);
  assert.equal(h.focusTargets.at(-1).selector, '[data-screenings-day="2026-10-17"]');
  assert.equal(h.focusTargets.at(-1).target.focused, 1);
  h.document.activeElement = null;
  for (const invalid of ["2026-11-30", "tomorrow", undefined]) {
    h.refs.days.fire("click", { target: h.target(invalid === undefined ? {} : { screeningsDay: invalid }) });
  }
  assert.equal(h.refs["day-title"].textContent, "Tomorrow");
  h.kindButtons[0].parentElement.fire("click", { target: h.kindButtons[1] });
  assert.deepEqual(h.kindButtons.map(button => button.getAttribute("aria-pressed")), ["false", "true", "false"]);
  assert.match(h.refs.days.innerHTML, /aria-label="Today, 1 film"/);
  assert.match(h.refs.days.innerHTML, /aria-label="Tomorrow, 0 films" class="is-quiet"/);
  assert.match(h.refs.list.innerHTML, /No screenings match this day and filter/);
  h.kindButtons[0].parentElement.fire("click", { target: h.target({ screeningsKind: "invented" }) });
  assert.deepEqual(h.kindButtons.map(button => button.getAttribute("aria-pressed")), ["false", "true", "false"]);
  h.kindButtons[0].parentElement.fire("click", { target: h.kindButtons[2] });
  assert.match(h.refs.days.innerHTML, /aria-label="Today, 1 film"/);
  assert.match(h.refs.days.innerHTML, /aria-label="Tomorrow, 1 film"/);
  // Past Shaw's seven published days, the summary says why multiplex listings stop.
  h.refs.days.fire("click", { target: h.target({ screeningsDay: "2026-10-24" }) });
  assert.equal(h.refs.summary.textContent, "0 films at 0 venues · 1 source showing earlier listings · Shaw Theatres lists only the next 7 days");
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
  assert.equal(h.refs.summary.textContent, "1 film at 1 venue · 1 source showing earlier listings");
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
  assert.match(h.refs.list.innerHTML, /No screenings match “zzz”/);
});

test("Study this film hands the title to Discover, with or without requestSubmit", async () => {
  const h = await loaded();
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
