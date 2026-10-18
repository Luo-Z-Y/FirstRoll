const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");
const path = require("node:path");
const { buildSync } = require("esbuild");

const source = buildSync({
  entryPoints: [path.resolve(__dirname, "../../app/web/src/discovery/atmosphere.ts")],
  bundle: true, format: "cjs", platform: "node", write: false,
}).outputFiles[0].text;

function harness({ reduced = false, available = true, compile = true, link = true, observersAvailable = true,
  markup = "static" } = {}) {
  const events = () => ({ listeners: new Map(),
    addEventListener(name, cb) { this.listeners.set(name, cb); },
    removeEventListener(name) { this.listeners.delete(name); },
    fire(name, event = {}) { this.listeners.get(name)?.(event); },
  });
  const calls = { contexts: 0, draws: 0, deletes: 0, time: null, sources: [], uniforms: [] };
  const gl = {
    createProgram: () => ({}), createShader: () => ({}), createBuffer: () => ({}),
    shaderSource(_, source) { calls.sources.push(source); }, compileShader() {}, attachShader() {}, linkProgram() {}, useProgram() {},
    getShaderParameter: () => compile, getProgramParameter: () => link,
    bindBuffer() {}, bufferData() {}, getAttribLocation: () => 0,
    enableVertexAttribArray() {}, vertexAttribPointer() {}, getUniformLocation: (_, name) => name,
    viewport() {}, uniform2f() {}, uniform1f(name, value) { calls.uniforms.push(name); if (name === "time") calls.time = value; },
    drawArrays() { calls.draws++; },
    deleteShader() { calls.deletes++; }, deleteProgram() { calls.deletes++; }, deleteBuffer() { calls.deletes++; },
  };
  const host = { open: true, dataset: { shaderState: markup }, getBoundingClientRect: () => ({ width: 1500, height: 600 }) };
  const canvas = { ...events(), parentElement: host, dataset: { shaderState: markup }, width: 0, height: 0,
    getContext() { calls.contexts++; return available ? gl : null; } };
  const toggle = { ...events(), hidden: true, setAttribute(name, value) { this[name] = value; } };
  const motion = { ...events(), matches: reduced };
  const observers = [];
  class Observer {
    constructor(cb) { this.cb = cb; observers.push(this); }
    observe(target, options) { this.target = target; this.options = options; } disconnect() { this.disconnected = true; }
  }
  const Observed = observersAvailable ? Observer : undefined;
  const frames = new Map(); let id = 0;
  const window = { ...events(), matchMedia: () => motion, devicePixelRatio: 3,
    requestAnimationFrame(cb) { frames.set(++id, cb); return id; },
    cancelAnimationFrame(id) { frames.delete(id); } };
  const document = { ...events(), hidden: false, documentElement: { dataset: { theme: "dark" } },
    getElementById: id => ({ discoveryShader: canvas, shaderToggle: toggle })[id] };
  const context = vm.createContext({ module: { exports: {} }, window, document,
    IntersectionObserver: Observed, ResizeObserver: Observer, MutationObserver: Observer });
  vm.runInContext(source, context);
  const dispose = context.module.exports.mountDiscoveryShader();
  return { canvas, toggle, host, motion, document, window, frames, calls, observers, dispose,
    // The dialog must always carry the same state as its canvas, for :has()-free CSS.
    state() { assert.equal(host.dataset.shaderState, canvas.dataset.shaderState); return host.dataset.shaderState; },
    size: context.module.exports.shaderSize,
    visible(value = true) { observers[0].cb([{ isIntersecting: value }]); },
    frame(time) { const [key, cb] = frames.entries().next().value; frames.delete(key); cb(time); } };
}

test("shader waits until visible and caps resolution and draw frequency", () => {
  const h = harness();
  assert.equal(h.calls.contexts, 0);
  assert.equal(h.state(), "static"); // Nothing drawn before the dialog is visible.
  h.visible();
  assert.equal(h.state(), "running");
  assert.equal(h.calls.time, 0);
  assert.ok(h.canvas.width <= 960 && h.canvas.height <= 540);
  h.frame(100);
  const count = h.calls.draws;
  h.frame(116); assert.equal(h.calls.draws, count);
  h.frame(140); assert.equal(h.calls.draws, count + 1);
  h.visible(false); assert.equal(h.frames.size, 0);
  h.dispose();
});

test("pause, hidden tab, closed welcome and bfcache resume safely", () => {
  const h = harness(); h.visible();
  h.toggle.fire("click");
  assert.equal(h.frames.size, 0);
  assert.equal(h.state(), "paused");
  assert.equal(h.toggle["aria-label"], "Play background animation");
  h.document.documentElement.dataset.theme = "light"; h.observers[2].cb();
  assert.equal(h.calls.uniforms.includes("dark"), false); assert.equal(h.frames.size, 0);
  h.toggle.fire("click"); assert.equal(h.frames.size, 1); assert.equal(h.state(), "running");
  h.document.hidden = true; h.document.fire("visibilitychange"); assert.equal(h.frames.size, 0);
  h.document.hidden = false; h.document.fire("visibilitychange"); assert.equal(h.frames.size, 1);
  h.host.open = false; h.observers[2].cb(); assert.equal(h.frames.size, 0);
  h.host.open = true; h.observers[2].cb(); assert.equal(h.frames.size, 1);
  h.window.fire("pagehide", { persisted: true }); assert.equal(h.frames.size, 0);
  h.window.fire("pageshow"); assert.equal(h.frames.size, 1);
  h.window.fire("pagehide", { persisted: false });
  assert.equal(h.frames.size, 0); assert.ok(h.observers.every(o => o.disconnected));
  assert.equal(h.state(), "static");
  assert.equal(h.calls.deletes, 4);
  assert.equal(h.motion.listeners.size, 0); assert.equal(h.toggle.listeners.size, 0);
});

test("original fractal layers, colour and speed are retained without theme recolouring", () => {
  const h = harness(); h.visible();
  const fragment = h.calls.sources[1];
  assert.match(fragment, /#define NUM_LAYERS 16\./);
  assert.match(fragment, /#define ITER 23/);
  assert.match(fragment, /o\.xzyw = abs\(o \/ dot\(o, o\) - dec\)/);
  assert.match(fragment, /col \*= vec3\(2\., 1\., 2\.\)/);
  assert.match(fragment, /float t = time \* \.3/);
  assert.doesNotMatch(fragment, /uniform float dark|vec3\(shade\)/);
  h.frame(100); h.frame(140);
  assert.equal(h.calls.time, 0.04);
  h.dispose();
});

test("reduced motion never allocates a GPU context and can change live", () => {
  const h = harness({ reduced: true }); h.visible();
  assert.equal(h.calls.contexts, 0); assert.equal(h.toggle.hidden, true);
  h.motion.matches = false; h.motion.fire("change"); assert.equal(h.frames.size, 1);
  h.motion.matches = true; h.motion.fire("change");
  assert.equal(h.frames.size, 0); assert.equal(h.state(), "static");
  h.dispose();
});

for (const options of [{ available: false }, { compile: false }, { link: false }]) {
  test(`GPU failure leaves the static fallback: ${JSON.stringify(options)}`, () => {
    const h = harness(options); h.visible();
    assert.equal(h.frames.size, 0); assert.equal(h.state(), "static");
    assert.equal(h.toggle.hidden, true);
    h.visible(); assert.equal(h.calls.contexts, 1); // No retry loop.
    h.dispose();
  });
}

test("lost context cancels animation and cleans up resources", () => {
  const h = harness(); h.visible(); h.canvas.fire("webglcontextlost");
  assert.equal(h.frames.size, 0); assert.equal(h.state(), "static");
  assert.equal(h.calls.deletes, 4);
  h.dispose(); h.dispose(); assert.equal(h.calls.deletes, 4);
});

test("the dialog mirrors the renderer state and its observer ignores that mirrored attribute", () => {
  // Stale or missing markup state is corrected before anything is drawn.
  for (const markup of ["running", undefined]) {
    const h = harness({ markup });
    assert.equal(h.state(), "static");
    const mutation = h.observers[2];
    assert.equal(mutation.target, h.host);
    assert.deepEqual([...mutation.options.attributeFilter], ["open"]);
    h.visible(); assert.equal(h.state(), "running");
    h.dispose(); assert.equal(h.state(), "static");
  }
});

test("missing observer support leaves both canvas and dialog static without a GPU context", () => {
  const h = harness({ observersAvailable: false, markup: undefined });
  assert.equal(h.state(), "static");
  assert.equal(h.calls.contexts, 0);
  assert.equal(h.toggle.hidden, true);
  assert.equal(h.frames.size, 0);
  h.dispose();
});

test("the shader's licence notice survives minified release bundling", () => {
  // Same bundling defaults as tools/frontend/build.cjs: legal comments move to the end of file.
  const minified = buildSync({
    entryPoints: [path.resolve(__dirname, "../../app/web/src/discovery/atmosphere.ts")],
    bundle: true, format: "esm", write: false, minifyWhitespace: true, minifySyntax: true,
  }).outputFiles[0].text;
  const notice = minified.slice(minified.indexOf("/*!"));
  assert.ok(minified.includes("/*!"));
  for (const part of ["Path to the colorful infinity", "Benoit Marini", "https://www.shadertoy.com/view/WtjyzR",
    "CC BY-NC-SA 3.0", "https://creativecommons.org/licenses/by-nc-sa/3.0/"]) assert.ok(notice.includes(part), part);
});
