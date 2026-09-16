const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../..");
const appPath = path.resolve(root, process.env.FIRSTROLL_TEST_APP || "app/web/app.js");
const source = readFileSync(appPath, "utf8");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

class Element {
  constructor() {
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.disabled = false;
    this.dataset = {};
    this.attributes = new Map();
    this.children = new Map();
    const classes = new Set();
    this.classList = {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
      toggle: (name, active) => active ? classes.add(name) : classes.delete(name),
    };
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name); }
  removeAttribute(name) { this.attributes.delete(name); }
  querySelector(selector) { return this.children.get(selector) || null; }
  querySelectorAll() { return []; }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolled = true; }
  insertAdjacentHTML(_where, markup) { this.innerHTML += markup; }
}

function harness({ publicMode = false } = {}) {
  const nodes = new Map();
  const pending = [];
  const frames = [];
  const context = vm.createContext({
    AbortController, URLSearchParams, TextDecoder, Uint8Array, CSS: { escape: String },
    console: { warn() {}, debug() {} },
    document: {
      body: new Element(),
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, new Element());
        return nodes.get(id);
      },
      querySelectorAll: () => [],
    },
    window: {
      FIRSTROLL_CONFIG: { publicMode },
      queueMicrotask,
      matchMedia: () => ({ matches: false }),
      requestAnimationFrame: (callback) => frames.push(callback),
      localStorage: { setItem() {}, removeItem() {} },
      sessionStorage: { setItem() {}, removeItem() {} },
    },
    fetch(url, options = {}) {
      const request = { url, options, ...deferred() };
      pending.push(request);
      // Deliberately ignore abort: already-received responses must also be harmless.
      return request.promise;
    },
  });
  // Unit-test the production request handlers without unrelated DOM startup/rendering.
  // Hoisted overrides also work against the minified classic-script production build.
  vm.runInContext(`${source}\n
    function setup() {}
    function persistDiscoverySession() {}
    function clearDiscoverySession() {}
    function renderFilmDetail(film) { refs.filmDetail.innerHTML = film.title; }
    function renderDiscoveryResults(data) { state.discovery.results = data.results; }
    function renderRecentSearches() {}
    function deepStudyMarkup(study) { return study.title || 'Completed study'; }
  `, context, { filename: appPath });
  const api = vm.runInContext(`({ state, refs, loadFilmDetail, onFilmDetailClick,
    cancelFilmDetailRequests, onDiscoverySearch, loadFilmVideos, loadFilmReception,
    loadProviderCriticism, structureProviderCriticism, selectCriticismSource,
    generateDeepStudy, cancelDeepStudyRequest, updateDeepStudyAuthState })`, context);
  api.refs.discoverySubmit.children.set("span", new Element());

  function film(id) {
    api.cancelFilmDetailRequests();
    const selected = { id, title: `Film ${id}`, critical_research: { bundles: {} } };
    api.state.discovery.selectedFilm = selected;
    api.state.discovery.detailFilmId = id;
    api.state.discovery.detailController = new AbortController();
    api.state.discovery.activeCriticismProvider = "douban";
    const selectors = {
      videos: "[data-film-videos-output]", critical: "[data-critical-output]",
      study: "[data-study-output]", generate: "[data-generate-study]",
      cancel: "[data-cancel-study]", question: "[data-study-question]",
    };
    const elements = {};
    for (const [name, selector] of Object.entries(selectors)) {
      elements[name] = new Element();
      api.refs.filmDetail.children.set(selector, elements[name]);
    }
    elements.generate.textContent = "Generate study";
    elements.cancel.classList.add("hidden");
    return { selected, ...elements };
  }
  return { ...api, context, pending, frames, film };
}

function reply(request, data, status = 200) {
  request.resolve({ ok: status < 400, status, json: async () => data });
}

function close(h) {
  return h.onFilmDetailClick({ target: {
    closest: (selector) => selector === "[data-detail-close]" ? {} : null,
  } });
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

for (const staleFailure of [false, true]) {
  for (const oldFirst of [false, true]) {
    test(`latest dossier wins: stale failure=${staleFailure}, old first=${oldFirst}`, async () => {
      const h = harness();
      const old = h.loadFilmDetail("A");
      const current = h.loadFilmDetail("B");
      assert.equal(h.pending[0].options.signal.aborted, true);
      const finishOld = async () => {
        if (staleFailure) h.pending[0].reject(new Error("Delayed provider failure"));
        else reply(h.pending[0], { film: { id: "A", title: "Old film" } });
        await old;
      };
      if (oldFirst) {
        await finishOld();
        assert.equal(h.refs.filmDetail.getAttribute("aria-busy"), "true");
        assert.equal(h.state.discovery.selectedFilm, null);
      }
      reply(h.pending[1], { film: { id: "B", title: "Current film" } });
      await current;
      if (!oldFirst) await finishOld();
      assert.equal(h.state.discovery.selectedFilm.id, "B");
      assert.equal(h.state.discovery.detailFilmId, "B");
      assert.equal(h.refs.filmDetail.innerHTML, "Current film");
      assert.equal(h.refs.filmDetail.getAttribute("aria-busy"), "false");
    });
  }
}

test("closing a loading dossier cancels it and blocks late rendering/focus", async () => {
  const h = harness();
  const request = h.loadFilmDetail("A");
  assert.match(h.refs.filmDetail.innerHTML, /data-detail-close/);
  await close(h);
  assert.equal(h.pending[0].options.signal.aborted, true);
  reply(h.pending[0], { film: { id: "A", title: "Old film" } });
  await request;
  assert.equal(h.state.discovery.selectedFilm, null);
  assert.equal(h.state.discovery.detailFilmId, null);
  assert.equal(h.refs.filmDetail.innerHTML, "");
  assert.equal(h.frames.length, 0);
});

test("a queued dossier scroll cannot steal focus after closing", async () => {
  const h = harness();
  const request = h.loadFilmDetail("A", { scroll: true });
  reply(h.pending[0], { film: { id: "A", title: "Old film" } });
  await request;
  await close(h);
  h.refs.filmDetail.scrolled = false;
  h.frames.forEach((callback) => callback());
  assert.equal(h.refs.filmDetail.scrolled, false);
});

test("a new search aborts dossier work without a late state or busy reset", async () => {
  const h = harness();
  const dossier = h.loadFilmDetail("A");
  h.refs.filmTitle.value = "New film";
  const search = h.onDiscoverySearch({ preventDefault() {} });
  assert.equal(h.pending[0].options.signal.aborted, true);
  reply(h.pending[0], { film: { id: "A", title: "Old film" } });
  await dossier;
  assert.equal(h.state.discovery.selectedFilm, null);
  assert.equal(h.state.discovery.detailFilmId, null);
  assert.equal(h.refs.discoverySubmit.getAttribute("aria-busy"), "true");
  reply(h.pending[1], { results: [], mode: "test" });
  await search;
});

test("closing the dossier aborts its background reception request", async () => {
  const h = harness();
  const { selected } = h.film("A");
  const section = new Element();
  const scores = new Element();
  scores.innerHTML = "Loading ratings";
  h.refs.filmDetail.children.set("[data-film-reception]", section);
  h.refs.filmDetail.children.set("[data-reception-scores]", scores);
  const request = h.loadFilmReception(selected);
  await close(h);
  assert.equal(h.pending[0].options.signal.aborted, true);
  reply(h.pending[0], { scores: [] });
  await request;
  assert.equal(scores.innerHTML, "Loading ratings");
});

for (const operation of ["fetch", "structure"]) {
  for (const staleFailure of [false, true]) {
    test(`stale criticism ${operation}, failure=${staleFailure}, never enters another film`, async () => {
      const h = harness();
      const a = h.film("A");
      const button = new Element();
      button.dataset.criticismSource = "douban";
      const request = operation === "fetch"
        ? h.loadProviderCriticism(button, "douban")
        : h.structureProviderCriticism("douban", button);
      const before = a.critical.innerHTML;
      const b = h.film("B");
      assert.equal(h.pending[0].options.signal.aborted, true);
      b.critical.setAttribute("aria-busy", "true");
      if (staleFailure) h.pending[0].reject(new Error("Old source failed"));
      else reply(h.pending[0], { critical_research: { provider: "Douban", reviews: [] } });
      await request;
      assert.equal(Object.keys(a.selected.critical_research.bundles).length, 0);
      assert.equal(Object.keys(b.selected.critical_research.bundles).length, 0);
      assert.equal(a.critical.innerHTML, before);
      assert.equal(b.critical.getAttribute("aria-busy"), "true");
      // In particular, no automatic local structuring call for film B.
      assert.equal(h.pending.length, 1);
    });
  }
}

test("a background criticism completion cannot clear the active provider's busy state", async () => {
  const h = harness({ publicMode: true });
  const a = h.film("A");
  const button = new Element();
  button.dataset.criticismSource = "douban";
  const request = h.loadProviderCriticism(button, "douban");
  h.state.discovery.activeCriticismProvider = "guardian-web";
  a.critical.innerHTML = "Fetching Guardian";
  reply(h.pending[0], { critical_research: { provider: "Douban", reviews: [] } });
  await request;
  assert.equal(a.selected.critical_research.bundles.douban.provider, "Douban");
  assert.equal(a.critical.innerHTML, "Fetching Guardian");
  assert.equal(a.critical.getAttribute("aria-busy"), "true");
});

for (const operation of ["fetch", "structure"]) {
  test(`selecting cached criticism clears a previous provider's ${operation} busy state`, async () => {
    const h = harness({ publicMode: operation === "fetch" });
    const a = h.film("A");
    const cached = { provider: "The Guardian public web", reviews: [] };
    a.selected.critical_research.bundles.guardian = cached;
    const request = operation === "fetch"
      ? h.loadProviderCriticism(new Element(), "douban")
      : h.structureProviderCriticism("douban");
    assert.equal(a.critical.getAttribute("aria-busy"), "true");
    const tab = new Element();
    tab.dataset.criticismSource = "guardian-web";
    await h.selectCriticismSource(tab);
    assert.equal(a.critical.getAttribute("aria-busy"), "false");
    assert.match(a.critical.innerHTML, /The Guardian public web/);
    const cachedMarkup = a.critical.innerHTML;
    reply(h.pending[0], { critical_research: { provider: "Douban", reviews: [] } });
    await request;
    assert.equal(a.critical.getAttribute("aria-busy"), "false");
    assert.equal(a.critical.innerHTML, cachedMarkup);
  });
}

test("current local criticism still fetches then structures the same film", async () => {
  const h = harness();
  const a = h.film("A");
  const button = new Element();
  button.dataset.criticismSource = "douban";
  const request = h.loadProviderCriticism(button, "douban");
  reply(h.pending[0], { critical_research: { provider: "Douban", reviews: [] } });
  await tick();
  assert.equal(h.pending.length, 2);
  assert.match(h.pending[1].url, /\/films\/A\/criticism\/douban\/structure$/);
  reply(h.pending[1], { critical_research: { provider: "Douban", reviews: [], claim_status: "structured" } });
  await request;
  assert.equal(a.selected.critical_research.bundles.douban.claim_status, "structured");
  assert.equal(a.critical.getAttribute("aria-busy"), "false");
  assert.equal(button.disabled, false);
});

test("video authorisation resolving after navigation sends no obsolete search", async () => {
  const h = harness();
  h.film("A");
  const auth = deferred();
  h.context.window.FirstRollAuth = { authorisationHeaders: () => auth.promise };
  const request = h.loadFilmVideos(new Element());
  h.film("B");
  auth.resolve({ Authorization: "Bearer synthetic" });
  await request;
  assert.equal(h.pending.length, 0);
});

test("a late video response does not mutate a closed dossier", async () => {
  const h = harness();
  const a = h.film("A");
  const request = h.loadFilmVideos(new Element());
  await tick();
  await close(h);
  assert.equal(h.pending[0].options.signal.aborted, true);
  reply(h.pending[0], { video_sources: { videos: [] } });
  await request;
  assert.equal(a.selected.video_sources, undefined);
});

for (const stop of ["cancel", "close", "replace"]) {
  test(`study responds immediately and ${stop} during auth prevents a paid request`, async () => {
    const h = harness({ publicMode: true });
    const a = h.film("A");
    const auth = deferred();
    h.context.window.FirstRollAuth = { authorisationHeaders: () => auth.promise };
    const request = h.generateDeepStudy(a.generate);
    assert.equal(a.generate.disabled, true);
    assert.equal(a.generate.textContent, "Studying…");
    assert.equal(a.study.getAttribute("aria-busy"), "true");
    assert.equal(a.cancel.classList.contains("hidden"), false);
    if (stop === "cancel") h.cancelDeepStudyRequest({ announce: true });
    else if (stop === "close") await close(h);
    else h.film("B");
    auth.resolve({ Authorization: "Bearer synthetic" });
    await request;
    assert.equal(h.pending.length, 0);
    assert.equal(h.state.discovery.studyController, null);
    if (stop === "cancel") {
      assert.match(a.study.innerHTML, /You stopped waiting/);
      assert.equal(a.study.getAttribute("aria-busy"), "false");
      assert.equal(a.generate.disabled, false);
    }
  });
}

test("repeated study clicks during auth start only one request", async () => {
  const h = harness();
  const a = h.film("A");
  const auth = deferred();
  let authCalls = 0;
  h.context.window.FirstRollAuth = { authorisationHeaders() { authCalls += 1; return auth.promise; } };
  const request = h.generateDeepStudy(a.generate);
  await h.generateDeepStudy(a.generate);
  assert.equal(authCalls, 1);
  auth.resolve({});
  await tick();
  assert.equal(h.pending.length, 1);
  reply(h.pending[0], { study: { title: "A completed study" } });
  await request;
  assert.match(a.study.innerHTML, /A completed study/);
  assert.equal(a.generate.disabled, false);
  assert.equal(h.state.discovery.studyController, null);
});

for (const rejection of [false, true]) {
  test(`auth failure is actionable and clears study busy state: rejection=${rejection}`, async () => {
    const h = harness({ publicMode: true });
    const a = h.film("A");
    let opened = false;
    h.context.window.FirstRollAuth = {
      authorisationHeaders: async () => { if (rejection) throw new Error("Session unavailable"); return {}; },
      open() { opened = true; },
    };
    await h.generateDeepStudy(a.generate);
    assert.equal(h.pending.length, 0);
    assert.match(a.study.innerHTML, /role="alert"/);
    assert.equal(opened, !rejection);
    assert.equal(a.generate.disabled, false);
    assert.equal(a.cancel.classList.contains("hidden"), true);
    assert.equal(a.study.getAttribute("aria-busy"), "false");
    assert.equal(h.state.discovery.studyController, null);
  });
}

test("an auth notification does not replace the running study label", async () => {
  const h = harness({ publicMode: true });
  const a = h.film("A");
  const auth = deferred();
  h.context.window.FirstRollAuth = {
    authorisationHeaders: () => auth.promise, currentUser: () => ({ id: "synthetic" }),
  };
  const request = h.generateDeepStudy(a.generate);
  h.updateDeepStudyAuthState();
  assert.equal(a.generate.textContent, "Studying…");
  h.cancelDeepStudyRequest();
  auth.resolve({});
  await request;
});

test("closing and reopening the same film ignores its old study completion", async () => {
  const h = harness();
  const a = h.film("A");
  const old = h.generateDeepStudy(a.generate);
  await tick();
  const b = h.film("A");
  const current = h.generateDeepStudy(b.generate);
  await tick();
  assert.equal(h.pending[0].options.signal.aborted, true);
  reply(h.pending[0], { study: { title: "Obsolete study" } });
  await old;
  assert.equal(b.generate.disabled, true);
  assert.equal(b.study.getAttribute("aria-busy"), "true");
  reply(h.pending[1], { study: { title: "Current study" } });
  await current;
  assert.match(b.study.innerHTML, /Current study/);
  assert.doesNotMatch(b.study.innerHTML, /Obsolete/);
});

test("hosted completion keeps the authenticated two-request result contract", async () => {
  const h = harness({ publicMode: true });
  const a = h.film("A");
  const authorisation = { Authorization: "Bearer synthetic" };
  h.context.window.FirstRollAuth = { authorisationHeaders: async () => authorisation };
  const request = h.generateDeepStudy(a.generate);
  await tick();
  assert.match(h.pending[0].url, /\/study\/stream$/);
  const progress = { run_id: "run-1", kind: "run_completed", sequence: 1, message: "Ready", elapsed_ms: 1 };
  h.pending[0].resolve(new Response(`event: progress\ndata: ${JSON.stringify(progress)}\n\n`, {
    headers: { "X-FirstRoll-Run-ID": "run-1" },
  }));
  await tick();
  assert.equal(h.pending.length, 2);
  assert.match(h.pending[1].url, /\/research\/runs\/run-1$/);
  assert.equal(h.pending[1].options.headers, authorisation);
  assert.equal(h.pending[1].options.signal, h.pending[0].options.signal);
  reply(h.pending[1], { study: { title: "Hosted study" } });
  await request;
  assert.match(a.study.innerHTML, /Hosted study/);
  assert.equal(a.generate.disabled, false);
});
