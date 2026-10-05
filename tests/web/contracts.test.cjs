const assert = require("node:assert/strict");
const { test } = require("node:test");
const { buildSync } = require("esbuild");
const vm = require("node:vm");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");

function load(entry, globals = {}) {
  const source = buildSync({ absWorkingDir: root, entryPoints: [entry], bundle: true, format: "cjs", write: false, external: ["@supabase/supabase-js"] }).outputFiles[0].text;
  const module = { exports: {} };
  vm.runInNewContext(source, { module, exports: module.exports, ...globals });
  return module.exports;
}
const models = load("app/web/src/api/models.ts");
const accounts = load("app/web/src/accounts/decode.ts");

test("film decoder preserves consumed dossier fields and tolerates genuinely optional metadata", () => {
  const film = models.film({
    id: "wikidata:film", title: "Example", original_title: null, year: 2000, directors: ["Director"],
    source: { name: "Wikidata", url: "https://example.org/film", licence: "CC0", ignored: true },
    credits: { cinematographers: ["Cinematographer"] }, awards: [{ name: "Award", description: "Film prize" }],
    critical_research: { bundles: { douban: { provider: "Douban", reviews: [{ source_id: "R1", summary: "Text", rating_label: null }], claims: [] } } },
    video_sources: { bundle: { videos: [{ title: "Interview", duration_seconds: null }] } }, unconsumed: "discard",
  });
  assert.equal(film.id, "wikidata:film");
  assert.equal(film.original_title, undefined);
  assert.equal(film.credits.cinematographers[0], "Cinematographer");
  assert.equal(film.critical_research.bundles.douban.reviews[0].summary, "Text");
  assert.equal(film.unconsumed, undefined);
  assert.equal(film.source.ignored, undefined);
});

test("malformed film, review, provider and video fields cannot enter typed application state", () => {
  for (const value of [null, [], {}, { id: " " }, { id: 12 }, { id: "A", year: "2000" },
    { id: "A", directors: [{}] }, { id: "A", critical_research: { bundles: { x: { reviews: [{ summary: {} }] } } } },
    { id: "A", video_sources: { providers: { youtube: { state: 1 } } } },
    { id: "A", video_sources: { bundle: { videos: [{ duration_seconds: Infinity }] } } }]) {
    assert.throws(() => models.film(value));
  }
});

test("study decoder keeps citations, quota, packet accounting and timings", () => {
  const data = models.studyResult({ study: {
    title: "A study", sections: [{ source_ids: ["T1"], hypothesis: "A hypothesis" }],
    sources: [{ id: "T1", page: 12, excerpt: "Evidence" }],
    evidence_packet: { retrieval: { theory_selection: { omission_reasons: { duplicate: 2 } } } },
    observability: { stages: [{ name: "end_to_end", duration_ms: 123, status: "ok" }] },
  }, quota: { user: { remaining: 2, limit: 3 }, global: { remaining: 29 } } });
  assert.equal(data.study.sections[0].source_ids[0], "T1");
  assert.equal(data.study.sources[0].page, 12);
  assert.equal(data.study.evidence_packet.retrieval.theory_selection.omission_reasons.duplicate, 2);
  assert.equal(data.quota.user.remaining, 2);
  assert.throws(() => models.studyResult({ study: { sections: [{ source_ids: [42] }] } }));
  assert.throws(() => models.studyResult({ quota: { user: { remaining: "unlimited" } } }));
});

test("account decoders reject invalid preferences and saved-film identities", () => {
  assert.equal(accounts.authMode("invented"), "sign-in");
  assert.equal(accounts.displayName({ id: "u", user_metadata: { display_name: {} } }), "");
  assert.equal(accounts.preferences({ theme: "dark", shelf_motion: true }).theme, "dark");
  assert.throws(() => accounts.preferences({ theme: "blue", shelf_motion: true }));
  assert.throws(() => accounts.preferences({ theme: "system", shelf_motion: "yes" }));
  assert.throws(() => accounts.savedFilms([{ film_id: "", title: "Example" }]));
  assert.throws(() => accounts.savedFilms([{ film_id: "A", title: 12 }]));
  assert.equal(accounts.savedFilms([{ film_id: "A", title: "Example", poster_url: null }])[0].title, "Example");
});

test("invalid or unavailable local storage falls back without trusting parsed JSON", () => {
  const decoder = load("app/web/src/accounts/decode.ts", { window: { localStorage: { getItem: () => '{"theme":"blue"}' } } });
  const fallback = { theme: "system", shelf_motion: true };
  assert.equal(decoder.readStorage("key", fallback, decoder.preferences), fallback);
  const unavailable = load("app/web/src/accounts/decode.ts", { window: { localStorage: { getItem() { throw new Error("disabled"); } } } });
  assert.equal(unavailable.readStorage("key", fallback, unavailable.preferences), fallback);
});

class Element {
  constructor() {
    this.value = ""; this.textContent = ""; this.dataset = {}; this.listeners = new Map();
    this.classList = { toggle() {}, add() {}, remove() {}, contains: () => false };
  }
  addEventListener(name, handler) { this.listeners.set(name, handler); }
  setAttribute() {}
  querySelector() { return null; }
  showModal() {}
  close() {}
  focus() {}
  reset() {}
}
function browser(storage = new Map()) {
  const nodes = new Map(), listeners = new Map();
  const document = {
    body: new Element(), activeElement: null,
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); },
    querySelectorAll: () => [],
    addEventListener: (name, handler) => listeners.set(name, handler),
    dispatchEvent(event) { listeners.get(event.type)?.(event); },
  };
  const window = {
    FIRSTROLL_CONFIG: { localTestAccountEmail: "tester@example.org" },
    localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
  };
  const globals = { window, document, HTMLInputElement: Element, console, CustomEvent: class {
    constructor(type, options = {}) { this.type = type; this.detail = options.detail; }
  } };
  return { window, nodes, storage, globals };
}

test("local TypeScript adapter signs in, persists profile/preferences/films and never stores a password", async () => {
  const h = browser();
  load("app/web/local-auth.ts", h.globals);
  const auth = h.window.FirstRollAuth;
  await auth.ready;
  assert.equal(auth.currentUser(), null);
  h.nodes.get("authEmail").value = "tester@example.org";
  h.nodes.get("authPassword").value = "test-password-never-store";
  await h.nodes.get("authForm").listeners.get("submit")({ preventDefault() {} });
  assert.equal(auth.currentUser().email, "tester@example.org");
  assert.match((await auth.authorisationHeaders()).Authorization, /^Bearer /);
  await auth.updateDisplayName("Test viewer");
  await auth.updatePreferences({ theme: "dark" });
  await auth.saveFilm({ id: "film:A", title: "Film A", year: 2000 });
  assert.equal(auth.isFilmSaved("film:A"), true);
  const next = browser(h.storage);
  load("app/web/local-auth.ts", next.globals);
  await next.window.FirstRollAuth.ready;
  assert.equal(next.window.FirstRollAuth.currentProfile().display_name, "Test viewer");
  assert.equal(next.window.FirstRollAuth.currentPreferences().theme, "dark");
  assert.equal(next.window.FirstRollAuth.savedFilms()[0].film_id, "film:A");
  assert.ok(!JSON.stringify([...h.storage]).includes("test-password-never-store"));
  await auth.removeSavedFilm("film:A");
  assert.equal(auth.savedFilms().length, 0);
  await auth.signOut();
  assert.equal(auth.currentUser(), null);
  assert.deepEqual(Object.keys(await auth.authorisationHeaders()), []);
});

test("settings keys stay in memory, are provider-specific, and clear at sign-out", async () => {
  const h = browser();
  load("app/web/integrations.ts", h.globals);
  const key = "example-test-key-not-a-secret-12345";
  h.nodes.get("deepseekSessionKey").value = key;
  h.nodes.get("deepseekSessionForm").listeners.get("submit")({ preventDefault() {} });
  assert.equal(h.window.FirstRollIntegrations.configured("deepseek"), true);
  assert.equal(h.window.FirstRollIntegrations.requestHeaders("deepseek")["X-FirstRoll-DeepSeek-Key"], key);
  assert.deepEqual(Object.keys(h.window.FirstRollIntegrations.requestHeaders("youtube")), []);
  assert.equal(h.storage.size, 0);
  h.globals.document.dispatchEvent(new h.globals.CustomEvent("firstroll:auth-changed", { detail: { user: null } }));
  assert.equal(h.window.FirstRollIntegrations.configured("deepseek"), false);
  h.nodes.get("accountDisplayName").value = "New name";
  await h.nodes.get("accountProfileForm").listeners.get("submit")({ preventDefault() {} });
  assert.match(h.nodes.get("accountProfileStatus").textContent, /managed by your account provider/);
});

test("Supabase adapter preserves password auth, bearer headers and user-scoped saved data", async () => {
  const h = browser(), calls = [];
  h.window.FIRSTROLL_CONFIG = { supabaseUrl: "https://test.supabase.co", supabasePublishableKey: "sb_publishable_test" };
  h.window.location = { origin: "https://example.org", pathname: "/" };
  h.window.setTimeout = handler => { void handler(); return 1; };
  let session = { access_token: "mock-access-token", user: { id: "viewer-1", email: "viewer@example.org", user_metadata: {} } };
  let onChange;
  const rows = {
    firstroll_profiles: { display_name: "Test viewer" },
    firstroll_preferences: { theme: "dark", shelf_motion: true },
    firstroll_saved_films: [{ film_id: "A", title: "Film A" }],
  };
  const client = {
    auth: {
      getSession: async () => ({ data: { session }, error: null }),
      onAuthStateChange: callback => { onChange = callback; },
      signInWithPassword: async payload => { calls.push(["password", payload]); return { data: { session }, error: null }; },
      updateUser: async payload => { calls.push(["updateUser", payload]); return { error: null }; },
      signOut: async () => { session = null; onChange("SIGNED_OUT", null); return { error: null }; },
    },
    from(table) {
      const query = {
        select() { return this; },
        eq(key, value) { calls.push(["eq", table, key, value]); return this; },
        upsert(payload, options) { calls.push(["upsert", table, payload, options]); if (table !== "firstroll_saved_films") rows[table] = { ...rows[table], ...payload }; return this; },
        delete() { return this; },
        maybeSingle: async () => ({ data: rows[table], error: null }),
        single: async () => ({ data: rows[table], error: null }),
        order: async () => ({ data: rows[table], error: null }),
        then(resolve) { return Promise.resolve({ error: null }).then(resolve); },
      };
      return query;
    },
  };
  load("app/web/auth.ts", { ...h.globals, require(name) { assert.equal(name, "@supabase/supabase-js"); return { createClient: () => client }; } });
  const auth = h.window.FirstRollAuth;
  await auth.ready;
  assert.equal(auth.currentProfile().display_name, "Test viewer");
  assert.equal(auth.currentPreferences().theme, "dark");
  assert.equal(auth.savedFilms()[0].film_id, "A");
  assert.equal((await auth.authorisationHeaders()).Authorization, "Bearer mock-access-token");
  h.nodes.get("authEmail").value = "viewer@example.org";
  h.nodes.get("authPassword").value = "test-password";
  await h.nodes.get("authForm").listeners.get("submit")({ preventDefault() {} });
  assert.equal(calls.find(call => call[0] === "password")[1].email, "viewer@example.org");
  await auth.updateDisplayName("New name");
  await auth.updatePreferences({ theme: "light" });
  await auth.updatePassword("new-test-password");
  await auth.saveFilm({ id: "B", title: "Film B" });
  await auth.removeSavedFilm("A");
  const save = calls.find(call => call[0] === "upsert" && call[1] === "firstroll_saved_films");
  assert.equal(save[2].user_id, "viewer-1");
  assert.equal(save[3].onConflict, "user_id,film_id");
  assert.ok(calls.some(call => call[0] === "eq" && call[1] === "firstroll_saved_films" && call[2] === "user_id" && call[3] === "viewer-1"));
  await auth.signOut();
  assert.equal(auth.currentUser(), null);
  assert.deepEqual(Object.keys(await auth.authorisationHeaders()), []);
  assert.equal(h.storage.size, 0);
});

test("typed auth loader selects only Supabase or the loopback-only local adapter", () => {
  for (const [hostname, config, expected] of [
    ["localhost", { localTestAccountEmail: "test@example.org" }, "local-auth.js"],
    ["firstroll.app", { localTestAccountEmail: "test@example.org" }, null],
    ["firstroll.app", { publicMode: true, supabaseUrl: "https://test.supabase.co", supabasePublishableKey: "sb_publishable_test" }, "auth.js"],
    ["firstroll.app", { publicMode: true, authProvider: "entra", entraAuthority: "https://test.ciamlogin.com/tenant", entraSpaClientId: "test", entraApiScope: "scope" }, null],
    ["firstroll.app", { publicMode: true, authProvider: "entra" }, null],
  ]) {
    const h = browser(), scripts = [];
    h.window.location = { hostname };
    h.window.FIRSTROLL_CONFIG = config;
    h.globals.document.createElement = () => ({});
    h.globals.document.body.append = script => scripts.push(script);
    load("app/web/auth-loader.ts", h.globals);
    assert.equal(scripts.length, expected ? 1 : 0);
    if (expected) assert.equal(scripts[0].src.split("?")[0], `/assets/${expected}`);
  }
});

test("early typed theme script survives disabled storage and honours a saved preference", () => {
  for (const stored of ["dark", "light", "invalid", null]) {
    const root = { dataset: {} };
    load("app/web/theme-init.ts", {
      document: { documentElement: root },
      window: { localStorage: { getItem: () => stored }, matchMedia: () => ({ matches: true }) },
    });
    assert.equal(root.dataset.theme, stored === "light" ? "light" : "dark");
  }
  const root = { dataset: {} };
  load("app/web/theme-init.ts", {
    document: { documentElement: root },
    window: { localStorage: { getItem() { throw new Error("disabled"); } }, matchMedia: () => ({ matches: false }) },
  });
  assert.equal(root.dataset.theme, "light");
});
