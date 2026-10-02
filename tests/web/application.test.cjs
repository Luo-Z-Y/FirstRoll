const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { bundleApplication } = require("../../tools/frontend-build.cjs");

const root = path.resolve(__dirname, "../..");
const compiled = bundleApplication({ write: false, metafile: true });
const source = process.env.FIRSTROLL_TEST_APP
  ? readFileSync(path.resolve(root, process.env.FIRSTROLL_TEST_APP), "utf8")
  : compiled.outputFiles[0].text;

class Element {
  constructor() {
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.dataset = {};
    this.listeners = new Map();
    this.attributes = new Map();
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  addEventListener(name, handler) {
    this.listeners.set(name, [...(this.listeners.get(name) || []), handler]);
  }
  setAttribute(name, value) { this.attributes.set(name, value); }
  querySelector() { return null; }
  focus() {}
}

function harness() {
  const nodes = new Map();
  const events = [];
  const pending = [];
  const storage = new Map();
  const localStorage = new Map();
  const store = entries => ({
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
    removeItem: key => entries.delete(key),
  });
  const document = {
    readyState: "loading", body: new Element(), documentElement: new Element(),
    querySelectorAll: () => [],
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, new Element());
      return nodes.get(id);
    },
    addEventListener: (name, handler) => events.push({ name, handler }),
    dispatchEvent() {},
  };
  const window = {
    FIRSTROLL_CONFIG: {}, scrollY: 0,
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    sessionStorage: store(storage), localStorage: store(localStorage),
    addEventListener: (name, handler) => events.push({ name, handler }),
    requestAnimationFrame() {}, scrollTo() {},
    setTimeout: () => 1, clearTimeout() {},
  };
  const context = vm.createContext({
    document, window, AbortController, URL, URLSearchParams, TextEncoder, TextDecoder,
    Uint8Array, console: { warn() {}, debug() {} },
    CustomEvent: class { constructor(name, options) { this.type = name; this.detail = options.detail; } },
    fetch(url, options = {}) {
      return new Promise((resolve, reject) => pending.push({ url, options, resolve, reject }));
    },
  });
  vm.runInContext(source, context);
  return { context, window, document, nodes, events, pending, storage, localStorage,
    create: () => vm.runInContext("createApplication()", context) };
}

test("construction is inert and each application owns independent request/session state", () => {
  const h = harness();
  const first = h.create(), second = h.create();
  assert.notEqual(first.state, second.state);
  first.state.discovery.results.push({ id: "1" });
  first.state.discovery.relatedFilmCache.set("1", {});
  assert.equal(second.state.discovery.results.length, 0);
  assert.equal(second.state.discovery.relatedFilmCache.size, 0);
  assert.equal(h.pending.length, 0);
  assert.equal(h.storage.size, 0);
  assert.equal(h.events.length, 1); // Only the entry's DOM-ready hook.
});

test("start wires the real modules once and preserves the account-facing theme API", () => {
  const h = harness(), app = h.create();
  app.start();
  app.start();
  assert.equal(h.nodes.get("discoveryForm").listeners.get("submit").length, 1);
  assert.equal(h.events.filter(event => event.name === "pagehide").length, 1);
  assert.equal(h.pending.length, 1);
  assert.equal(h.pending[0].url, "/api/discovery/status");
  assert.equal(h.window.FirstRollUI.setThemePreference, app.setThemePreference);
  h.window.FirstRollUI.setThemePreference("dark");
  assert.equal(h.document.documentElement.dataset.theme, "dark");
  assert.equal(h.localStorage.get("firstroll.theme"), "dark");
});

test("DOM-ready entry starts the application without a test-specific boot flag", () => {
  const h = harness();
  h.events.find(event => event.name === "DOMContentLoaded").handler();
  assert.equal(h.pending.length, 1);
  assert.equal(h.nodes.get("filmDetail").listeners.get("click").length, 1);
});

test("dossier rendering connects criticism, video and account modules without fetching", () => {
  const h = harness(), app = h.create();
  app.renderFilmDetail({ id: "1", title: "Film <one>", year: 2000, directors: ["Director"] });
  const html = app.refs.filmDetail.innerHTML;
  for (const expected of ["Film &lt;one&gt;", "data-load-film-videos", "data-criticism-source", "data-generate-study", "data-dossier-heading"]) {
    assert.ok(html.includes(expected), expected);
  }
  assert.equal(h.pending.length, 0);
});

test("archive persistence uses the bounded film projection, not the complete dossier", () => {
  const h = harness(), app = h.create();
  app.state.discovery.lastQuery = { title: "Film", year: "", director: "" };
  app.renderFilmArchive({ id: "1", title: "Film", critical_research: { private: true }, reviews: ["Do not persist"] }, [], [], false);
  const saved = h.storage.get("firstroll.discovery-session");
  assert.ok(saved);
  assert.ok(!saved.includes("critical_research"));
  assert.ok(!saved.includes("Do not persist"));
  assert.equal(app.state.discovery.archiveSelectionId, "1");
});

test("shelf requests crossing film selection cannot replace the newer archive", async () => {
  const h = harness(), app = h.create();
  const first = { id: "A", title: "First" }, second = { id: "B", title: "Second" };
  app.renderFilmArchive(first, [], [], true);
  const old = app.loadRelatedFilms(first, []);
  app.renderFilmArchive(second, [], [], true);
  const current = app.loadRelatedFilms(second, []);
  h.pending[1].resolve({ ok: true, json: async () => ({ same_director: [{ id: "B2", title: "Second related" }] }) });
  await current;
  h.pending[0].resolve({ ok: true, json: async () => ({ same_director: [{ id: "A2", title: "Old related" }] }) });
  await old;
  assert.equal(app.state.discovery.archive.primary.id, "B");
  assert.equal(app.state.discovery.archive.directorWorks[0].id, "B2");
});

test("module graph stays acyclic and the application entry stays small", () => {
  const graph = compiled.metafile.inputs;
  const visited = new Set(), active = new Set();
  function visit(name) {
    assert.ok(!active.has(name), `Circular import at ${name}`);
    if (visited.has(name)) return;
    active.add(name);
    for (const dependency of graph[name]?.imports || []) {
      if (!dependency.external) visit(dependency.path);
    }
    active.delete(name);
    visited.add(name);
  }
  for (const name of Object.keys(graph)) visit(name);
  assert.ok(readFileSync(path.join(root, "app/web/app.js"), "utf8").split("\n").length <= 100);
  for (const name of Object.keys(graph).filter(name => name.startsWith("app/web/src/"))) {
    assert.ok(readFileSync(path.join(root, name), "utf8").split("\n").length <= 500, `${name} needs a smaller boundary`);
  }
});
