const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");
const path = require("node:path");
const { buildSync } = require("esbuild");
const code = buildSync({ entryPoints: [path.resolve(__dirname, "../../app/web/src/discovery/welcome-heading.ts")],
  bundle: true, format: "cjs", platform: "node", write: false }).outputFiles[0].text;

function harness({ supported = true, fails = false, width = 240 } = {}) {
  const animation = { onfinish: null, cancel() { this.cancelled = true; } };
  const label = { style: {}, setAttribute(name, value) { this[name] = value; }, remove() { this.removed = true; },
    animate(frames, options) { if (fails) throw Error("unavailable"); this.frames = frames; this.options = options; return animation; } };
  const source = { textContent: "Find a film", animate: supported ? () => {} : undefined,
    getBoundingClientRect: () => ({ left: 400, top: 300, width, height: 44 }),
    style: { fontSize: "36px", lineHeight: "44px", letterSpacing: "-1px", color: "white", textShadow: "shadow" } };
  const target = { getBoundingClientRect: () => ({ left: 64, top: 160, width: 1000, height: 80 }),
    style: { fontSize: "72px", lineHeight: "80px", letterSpacing: "-4px", color: "black", fontFamily: "DM Sans", fontWeight: "500" } };
  const host = { append(node) { this.child = node; } };
  const context = vm.createContext({ module: { exports: {} }, document: { createElement: () => label },
    window: { getComputedStyle: element => element.style } });
  vm.runInContext(code, context);
  let finished = 0;
  const dispose = context.module.exports.animateWelcomeHeading(host, source, target, 1500, () => finished++);
  return { dispose, host, label, animation, finished: () => finished };
}

test("heading moves between measured positions and interpolates to Discover typography", () => {
  const h = harness();
  assert.equal(h.host.child, h.label);
  assert.equal(h.label["aria-hidden"], "true");
  assert.equal(h.label.frames[0].left, "400px");
  assert.equal(h.label.frames[1].left, "64px");
  assert.equal(h.label.frames[1].top, "160px");
  assert.equal(h.label.frames[1].fontSize, "72px");
  assert.equal(h.label.frames[1].color, "black");
  assert.equal(h.label.options.duration, 1500);
  h.animation.onfinish(); assert.equal(h.finished(), 1);
  h.dispose();
  assert.equal(h.animation.onfinish, null);
  assert.equal(h.animation.cancelled, true);
  assert.equal(h.label.removed, true);
});

test("missing animation support, hidden destination or animation failure permits plain fade", () => {
  for (const options of [{ supported: false }, { width: 0 }, { fails: true }]) {
    const h = harness(options);
    assert.equal(h.dispose, null);
    assert.equal(h.finished(), 0);
    if (options.fails) assert.equal(h.label.removed, true);
  }
});
