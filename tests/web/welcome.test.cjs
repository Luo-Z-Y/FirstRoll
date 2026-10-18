const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");
const path = require("node:path");
const { buildSync } = require("esbuild");

const source = buildSync({
  entryPoints: [path.resolve(__dirname, "../../app/web/src/discovery/welcome.ts")],
  bundle: true, format: "cjs", platform: "node", write: false,
}).outputFiles[0].text;

// Per-tab storage double. `mode` "throws" makes every access raise, as blocked storage does.
function tabStorage(mode = "memory", items = new Map()) {
  const fail = () => { throw Object.assign(Error("The operation is insecure."), { name: "SecurityError" }); };
  if (mode === "throws") return { items, getItem: fail, setItem: fail };
  return { items, getItem: key => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => { items.set(key, String(value)); } };
}

function harness({ supported = true, fails = false, reduced = false, storage = tabStorage(),
  blockedStorage = false, restoredView = "analysis" } = {}) {
  const events = () => ({ listeners: new Map(),
    addEventListener(name, callback) { this.listeners.set(name, callback); },
    removeEventListener(name) { this.listeners.delete(name); },
    fire(name, value) { this.listeners.get(name)?.(value); },
  });
  let opened = 0, focused = "", modals = 0;
  const welcomeClasses = new Set();
  const welcome = { ...events(), open: false,
    classList: { add: name => welcomeClasses.add(name), remove: name => welcomeClasses.delete(name) },
    showModal: supported ? function () { modals++; if (fails) throw Error("unsupported"); this.open = true; } : undefined,
    close() { this.open = false; this.fire("close"); },
  };
  const enter = { ...events(), focus() { focused = "enter"; } };
  const title = { focus() { focused = "filmTitle"; } };
  const classes = new Set();
  const document = {
    body: { classList: { add: name => classes.add(name), remove: name => classes.delete(name) } },
    getElementById: id => ({ welcomeScreen: welcome, welcomeEnter: enter, filmTitle: title })[id],
  };
  const motion = { ...events(), matches: reduced };
  const timers = new Map();
  const frames = new Map();
  const window = { ...events(), matchMedia: () => motion,
    requestAnimationFrame(fn) { frames.set(1, fn); return 1; }, cancelAnimationFrame(id) { frames.delete(id); },
    setTimeout(fn) { timers.set(1, fn); return 1; }, clearTimeout(id) { timers.delete(id); } };
  // Some browsers throw on the `sessionStorage` getter itself when site data is blocked.
  Object.defineProperty(window, "sessionStorage", { get() {
    if (blockedStorage) throw Object.assign(Error("Access is denied."), { name: "SecurityError" });
    return storage;
  } });
  const context = vm.createContext({ module: { exports: {} }, document, window });
  vm.runInContext(source, context);
  // Stands in for setProductView("discovery") after restoreProductSession() chose a view.
  let view = restoredView;
  const dispose = context.module.exports.mountWelcomeScreen(() => { opened++; view = "discovery"; });
  return { welcome, enter, window, motion, timers, frames, classes, welcomeClasses, dispose, storage,
    key: context.module.exports.WELCOME_SEEN_KEY,
    frame() { const fn = frames.get(1); frames.delete(1); fn(); },
    endTransition: () => welcome.fire("transitionend", { target: welcome, propertyName: "opacity" }),
    opened: () => opened, focused: () => focused, view: () => view, modals: () => modals };
}

test("entry opens a modal and entering reveals Discover once with search focus", () => {
  const h = harness();
  assert.equal(h.welcome.open, true);
  assert.equal(h.focused(), "enter");
  assert.equal(h.classes.has("welcome-open"), true);
  h.enter.fire("click");
  h.frame();
  assert.equal(h.welcome.open, true); // Discover is prepared but remains behind the modal.
  assert.equal(h.welcomeClasses.has("is-leaving"), true);
  assert.equal(h.opened(), 1);
  assert.equal(h.focused(), "enter");
  h.endTransition();
  assert.equal(h.welcome.open, false);
  assert.equal(h.opened(), 1);
  assert.equal(h.focused(), "filmTitle");
  assert.equal(h.classes.size, 0);
  assert.equal(h.timers.size, 0);
  assert.equal(h.frames.size, 0);
  h.enter.fire("click"); h.welcome.fire("close"); h.dispose();
  assert.equal(h.opened(), 1);
});

test("Escape fades into Discover even without WebGL", () => {
  const h = harness(); let prevented = false;
  h.welcome.fire("cancel", { preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(h.welcome.open, true);
  h.endTransition();
  assert.equal(h.opened(), 1);
  assert.equal(h.focused(), "filmTitle");
});

test("duplicate clicks and unrelated transitions do not finish the fade early", () => {
  const h = harness(); h.enter.fire("click"); h.enter.fire("click");
  h.welcome.fire("transitionend", { target: h.enter, propertyName: "opacity" });
  h.welcome.fire("transitionend", { target: h.welcome, propertyName: "transform" });
  assert.equal(h.welcome.open, true);
  assert.equal(h.opened(), 1);
  assert.equal(h.timers.size, 1);
  h.endTransition(); h.endTransition();
  assert.equal(h.opened(), 1);
});

test("timeout fallback completes entry when transition events are missing", () => {
  const h = harness(); h.enter.fire("click");
  h.timers.get(1)();
  assert.equal(h.welcome.open, false);
  assert.equal(h.focused(), "filmTitle");
  assert.equal(h.timers.size, 0);
});

test("reduced motion skips the fade, including a change during transition", () => {
  for (const reduced of [true, false]) {
    const h = harness({ reduced }); h.enter.fire("click");
    if (!reduced) { h.motion.matches = true; h.motion.fire("change"); }
    assert.equal(h.welcome.open, false);
    assert.equal(h.timers.size, 0);
    assert.equal(h.focused(), "filmTitle");
    assert.equal(h.motion.listeners.size, 0);
  }
});

test("disposal during a fade cancels delayed callbacks", () => {
  const h = harness(); h.enter.fire("click"); h.dispose();
  assert.equal(h.timers.size, 0);
  assert.equal(h.frames.size, 0);
  assert.equal(h.welcome.open, false);
  assert.equal(h.classes.size, 0);
  assert.equal(h.welcomeClasses.size, 0);
  assert.equal(h.motion.listeners.size, 0);
  assert.equal(h.focused(), "enter");
});

test("viewport changes during entry finish safely instead of using stale heading coordinates", () => {
  const h = harness(); h.enter.fire("click"); h.frame();
  h.window.fire("resize");
  assert.equal(h.welcome.open, false);
  assert.equal(h.focused(), "filmTitle");
  assert.equal(h.classes.size, 0);
});

test("unsupported or failed modal leaves the ordinary application accessible", () => {
  for (const options of [{ supported: false }, { fails: true }]) {
    const h = harness(options);
    assert.equal(h.welcome.open, false);
    assert.equal(h.classes.size, 0);
    assert.equal(h.opened(), 0);
    h.dispose();
  }
});

test("bfcache retains welcome but final page exit cleans up without navigation", () => {
  const h = harness();
  h.window.fire("pagehide", { persisted: true });
  assert.equal(h.welcome.open, true);
  h.window.fire("pagehide", { persisted: false });
  assert.equal(h.welcome.open, false);
  assert.equal(h.classes.size, 0);
  assert.equal(h.opened(), 0);
  assert.equal(h.enter.listeners.size, 0);
  assert.equal(h.welcome.listeners.size, 0);
});

test("an opening already entered in this tab is skipped and the restored view is untouched", () => {
  const h = harness({ storage: tabStorage("memory", new Map([["firstroll.welcome-seen", "1"]])) });
  assert.equal(h.key, "firstroll.welcome-seen");
  assert.equal(h.modals(), 0);
  assert.equal(h.welcome.open, false);
  assert.equal(h.classes.size, 0);
  assert.equal(h.focused(), "");
  assert.equal(h.opened(), 0);
  assert.equal(h.view(), "analysis");
  // Nothing is listening, so stray events cannot navigate away from the restored view.
  assert.equal(h.enter.listeners.size, 0);
  assert.equal(h.welcome.listeners.size, 0);
  assert.equal(h.window.listeners.size, 0);
  assert.equal(h.motion.listeners.size, 0);
  h.enter.fire("click"); h.welcome.fire("close"); h.dispose();
  assert.equal(h.view(), "analysis");
});

test("entering records the per-tab marker, so the next load in the tab skips the opening", () => {
  for (const enter of [h => h.enter.fire("click"), h => h.welcome.fire("cancel", { preventDefault() {} })]) {
    const items = new Map();
    const h = harness({ storage: tabStorage("memory", items) });
    assert.equal(h.modals(), 1);
    assert.equal(items.has(h.key), false); // Showing alone does not count as seen.
    enter(h);
    assert.equal(items.get(h.key), "1");
    assert.equal(h.view(), "discovery");
    h.endTransition();
    const next = harness({ storage: tabStorage("memory", items) });
    assert.equal(next.modals(), 0);
    assert.equal(next.opened(), 0);
    assert.equal(next.view(), "analysis");
  }
});

test("a browser-initiated close also counts as entry", () => {
  const h = harness();
  h.welcome.close();
  assert.equal(h.storage.items.get(h.key), "1");
  assert.equal(h.opened(), 1);
  assert.equal(h.focused(), "filmTitle");
});

test("leaving the page without entering does not mark the opening as seen", () => {
  for (const options of [{}, { fails: true }]) {
    const h = harness(options);
    h.window.fire("pagehide", { persisted: false });
    assert.equal(h.storage.items.size, 0);
    assert.equal(h.opened(), 0);
    assert.equal(h.view(), "analysis");
  }
});

test("blocked or throwing storage still shows the opening and lets the visitor enter", () => {
  for (const options of [{ storage: tabStorage("throws") }, { blockedStorage: true }, { storage: null }]) {
    const h = harness(options);
    assert.equal(h.welcome.open, true);
    assert.equal(h.focused(), "enter");
    h.enter.fire("click"); h.frame(); h.endTransition();
    assert.equal(h.welcome.open, false);
    assert.equal(h.opened(), 1);
    assert.equal(h.view(), "discovery");
    assert.equal(h.focused(), "filmTitle");
    assert.equal(h.classes.size, 0);
  }
});
