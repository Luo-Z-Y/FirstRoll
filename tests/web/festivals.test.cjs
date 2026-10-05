const assert = require("node:assert/strict");
const { test } = require("node:test");
const vm = require("node:vm");
const { buildSync } = require("esbuild");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
function bundle(entry, format = "cjs") {
  return buildSync({ absWorkingDir: root, entryPoints: [entry], bundle: true, format, write: false }).outputFiles[0].text;
}
function moduleExports(entry) {
  const context = { module: { exports: {} } };
  vm.runInNewContext(bundle(entry), context);
  return context.module.exports;
}
const model = moduleExports("app/web/src/festivals/model.ts");
const { FESTIVALS } = moduleExports("app/web/src/festivals/data.ts");

test("atlas data has unique identities, bounded coordinates, valid windows and HTTPS links", () => {
  assert.equal(FESTIVALS.length, 33);
  assert.equal(new Set(FESTIVALS.map(f => f.id)).size, 33);
  for (const f of FESTIVALS) {
    assert.match(f.id, /^[a-z]+$/);
    assert.ok(Math.abs(f.lat) <= 90 && Math.abs(f.lon) <= 180);
    for (const [month, day] of [f.start, f.end]) {
      assert.ok(month >= 1 && month <= 12);
      assert.ok(day >= 1 && day <= model.CUMULATIVE[month] - model.CUMULATIVE[month - 1]);
    }
    assert.ok(model.dayOfYear(f.start) <= model.dayOfYear(f.end));
    if (f.url) assert.equal(new URL(f.url).protocol, "https:");
  }
  assert.equal(FESTIVALS.filter(f => f.kind === "awards").length, 1);
  assert.ok(FESTIVALS.find(f => f.id === "sgiff"));
});

test("typical windows overlap months inclusively without claiming confirmed events", () => {
  const sgiff = FESTIVALS.find(f => f.id === "sgiff");
  assert.equal(model.inMonth(sgiff, 11), true);
  assert.equal(model.inMonth(sgiff, 12), true);
  assert.equal(model.inMonth(sgiff, 10), false);
  assert.equal(model.inMonth(sgiff, 0), true);
  assert.equal(model.formatWindow(sgiff), "26 Nov – 7 Dec");
  for (const day of [model.dayOfYear(sgiff.start), model.dayOfYear(sgiff.end)]) {
    assert.equal(model.status(sgiff, day).label, "Within typical window");
  }
  assert.equal(model.status(sgiff, 365).key, "later");
  assert.equal(model.status(FESTIVALS[0], 365).key, "soon");
});

test("projection and leap day use the documented fixed-year plane", () => {
  assert.equal(model.project(0, 0).x, 500);
  assert.equal(model.project(0, 0).y, 250);
  assert.equal(model.todayOfYear(new Date(2024, 1, 29)), 59);
  assert.equal(model.todayOfYear(new Date(2024, 2, 1)), 60);
});

class Element {
  constructor(dataset = {}) {
    this.dataset = dataset; this.innerHTML = ""; this.textContent = "";
    this.listeners = {}; this.attributes = {}; this.children = {};
    this.classList = { toggle() {}, add() {}, remove() {} };
  }
  addEventListener(name, listener) { this.listeners[name] = listener; }
  querySelector(selector) { return this.children[selector] || null; }
  querySelectorAll(selector) { return this.children[selector] || []; }
  getBoundingClientRect() { return this.rect || { width: 1000, height: 396 }; }
  contains(target) { return !!target.dataset.calendarRow; }
  setAttribute(name, value) { this.attributes[name] = value; }
  closest(selector) {
    const key = { "[data-festival-month]": "festivalMonth", "[data-festival-id]": "festivalId", "[data-festival-zoom]": "festivalZoom" }[selector];
    return key in this.dataset ? this : null;
  }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolled = true; }
}
function harness(mobile = false) {
  const section = new Element();
  const refs = Object.fromEntries(["months", "map", "detail", "calendar", "summary"].map(name => [name, new Element()]));
  for (const [name, ref] of Object.entries(refs)) section.children[`[data-festival-${name}]`] = ref;
  const svg = new Element();
  const pin = new Element({ x: "500", y: "250" });
  svg.children[".festival-pin"] = [pin];
  refs.map.children.svg = svg;
  for (const action of ["in", "out", "reset"]) refs.map.children[`[data-festival-zoom="${action}"]`] = new Element();
  const document = { getElementById: () => section, addEventListener() {} };
  const source = process.env.FIRSTROLL_TEST_APP
    ? readFileSync(path.join(path.dirname(path.resolve(root, process.env.FIRSTROLL_TEST_APP)), "festivals.js"), "utf8")
    : bundle("app/web/festivals.ts", "iife");
  let resize;
  class ResizeObserver {
    constructor(callback) { resize = callback; }
    observe(target) { assert.equal(target, refs.map); }
  }
  vm.runInNewContext(source, { document, Element, ResizeObserver,
    window: { setTimeout() {}, matchMedia: () => ({ matches: mobile }) }, Date });
  const click = dataset => section.listeners.click({ target: new Element(dataset) });
  return { refs, svg, pin, click, resize: () => resize() };
}

test("atlas entry mounts map and calendar without a network service", () => {
  const { refs } = harness();
  assert.match(refs.map.innerHTML, /World map of film festivals/);
  assert.match(refs.summary.textContent, /32 festivals and the Oscars/);
  assert.match(refs.calendar.innerHTML, /Singapore International Film Festival/);
});

test("month filter toggles off and excludes out-of-month selections", () => {
  const { refs, click } = harness();
  click({ festivalId: "sgiff" });
  assert.match(refs.detail.innerHTML, /Singapore International Film Festival/);
  click({ festivalMonth: "5" });
  assert.match(refs.calendar.innerHTML, /Festival de Cannes/);
  assert.doesNotMatch(refs.calendar.innerHTML, /Singapore International Film Festival/);
  assert.doesNotMatch(refs.detail.innerHTML, /<h2>Singapore/);
  click({ festivalMonth: "5" });
  assert.match(refs.calendar.innerHTML, /Singapore International Film Festival/);
});

test("zoom stays bounded and reset restores the world view", () => {
  const { svg, click } = harness();
  for (let i = 0; i < 15; i++) click({ festivalZoom: "in" });
  const view = svg.attributes.viewBox.split(" ").map(Number);
  assert.equal(view[2], 125);
  assert.ok(view[0] >= 0 && view[0] + view[2] <= 1000);
  click({ festivalZoom: "reset" });
  assert.equal(svg.attributes.viewBox, "0.00 16.00 1000.00 396.00");
});

test("pins retain CSS-pixel size on phones, resize, zoom and initially hidden views", () => {
  const { svg, pin, click, resize } = harness();
  svg.rect = { width: 320, height: 126.72 };
  resize();
  assert.match(pin.attributes.transform, /scale\(3\.1250\)/);
  click({ festivalZoom: "in" });
  const width = Number(svg.attributes.viewBox.split(" ")[2]);
  const scale = Number(pin.attributes.transform.match(/scale\(([^)]+)\)/)[1]);
  assert.ok(Math.abs(scale * 320 / width - 1) < 0.001);
  svg.rect = { width: 0, height: 0 };
  resize();
  assert.doesNotMatch(pin.attributes.transform, /Infinity|NaN/);
  svg.rect = { width: 1000, height: 396 };
  click({ festivalZoom: "reset" });
  assert.match(pin.attributes.transform, /scale\(1\.0000\)/);
});

test("mobile calendar selection reveals details without scrolling map taps or desktop", () => {
  const { refs, click } = harness(true);
  click({ festivalId: "sgiff" });
  assert.equal(refs.detail.scrolled, undefined);
  click({ festivalId: "cannes", calendarRow: "true" });
  assert.equal(refs.detail.focused, true);
  assert.equal(refs.detail.scrolled, true);
  assert.match(refs.detail.innerHTML, /Festival de Cannes/);
  const desktop = harness();
  desktop.click({ festivalId: "cannes", calendarRow: "true" });
  assert.equal(desktop.refs.detail.scrolled, undefined);
});
