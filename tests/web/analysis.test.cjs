const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const Module = require("node:module");
const { buildSync } = require("esbuild");
const { bundleApplication } = require("../../tools/frontend/build.cjs");

const root = path.resolve(__dirname, "../..");
const source = process.env.FIRSTROLL_TEST_APP
  ? readFileSync(path.resolve(root, process.env.FIRSTROLL_TEST_APP), "utf8")
  : bundleApplication({ write: false }).outputFiles[0].text;
const parserFile = path.join(root, "app/web/src/analysis/response.ts");
const parserModule = new Module(parserFile);
parserModule._compile(buildSync({
  entryPoints: [parserFile], bundle: true, platform: "node", format: "cjs", write: false,
}).outputFiles[0].text, parserFile);
const { parseAnalysisResponse } = parserModule.exports;

// Matches analysis_pipeline.py, including Unknown scales when no detector supplies a label.
function fixture() {
  const shot = { shotId: 1, startSec: 0, endSec: 10, durationSec: 10,
    shotScale: "Unknown", avgRgb: [10, 20, 30], frameId: 1, focus: 0, texture: 0 };
  return {
    meta: { id: "clip", filename: "clip.mp4", durationSec: 10, width: 640,
      height: 480, frameCountEstimated: 240, fpsEstimated: 24 },
    global: { shotCount: 1, sceneCount: 1, averageShotLengthSec: 10,
      averageSceneLengthSec: 10, averageShotsPerScene: 1 },
    scenes: [{ sceneId: 1, startSec: 0, endSec: 10, durationSec: 10, shotCount: 1,
      averageShotLengthSec: 10, shotScaleComposition: { longPct: 0, mediumPct: 0, closePct: 0 },
      dominantRgb: [10, 20, 30], dominantHue: 210,
      props: [{ label: "chair", score: 0.75, count: 1 }], shots: [shot], motionProxy: 0 }],
    shots: [shot], outputs: { shotlenCsv: "/private/output/shotlen.csv" },
  };
}

test("analysis parser accepts the actual backend contract and optional older fields", () => {
  const input = fixture(), before = structuredClone(input);
  const result = parseAnalysisResponse(input, 1, 6);
  assert.equal(result.scenes[0].shots[0].shotScale, "Unknown");
  assert.equal(result.scenes[0].props[0].count, 1);
  assert.deepEqual(result.config, { interval: 1, sensitivity: 6, source: "backend" });
  assert.deepEqual(input, before);
  delete input.shots;
  delete input.outputs;
  assert.deepEqual(parseAnalysisResponse(input, 1, 6).shots, []);
  assert.deepEqual(parseAnalysisResponse(input, 1, 6).outputs, {});
});

test("analysis parser rejects malformed nested values before rendering/export", () => {
  const mutations = [
    data => { data.meta = null; },
    data => { data.meta.filename = {}; },
    data => { data.meta.durationSec = "10"; },
    data => { data.global.averageShotLengthSec = Infinity; },
    data => { data.scenes[0].shots = null; },
    data => { data.scenes[0].shots[0].shotScale = "<script>"; },
    data => { data.scenes[0].shots[0].endSec = -1; },
    data => { data.scenes[0].dominantRgb = [1, 2]; },
    data => { data.scenes[0].dominantRgb[0] = NaN; },
    data => { data.scenes[0].dominantRgb[0] = 256; },
    data => { data.scenes[0].shotScaleComposition.longPct = 101; },
    data => { data.scenes[0].props[0].score = 2; },
    data => { data.scenes[0].props[0].count = -1; },
    data => { data.global.shotCount = 0.5; },
    data => { data.outputs = { unexpected: {} }; },
  ];
  for (const mutate of mutations) {
    const data = fixture();
    mutate(data);
    assert.throws(() => parseAnalysisResponse(data, 1, 6), /Invalid backend response/);
  }
  for (const value of [null, [], {}, "text"]) {
    assert.throws(() => parseAnalysisResponse(value, 1, 6), /Invalid backend response/);
  }
  for (const interval of [0, -1, NaN, Infinity]) {
    assert.throws(() => parseAnalysisResponse(fixture(), interval, 6), /Invalid backend response/);
  }
});

class Element {
  constructor() {
    this.innerHTML = ""; this.textContent = ""; this.value = ""; this.disabled = false;
    this.dataset = {}; this.style = {}; this.files = []; this.attributes = {};
    this.classes = new Set(); this.focused = false;
    this.classList = {
      add: name => this.classes.add(name), remove: name => this.classes.delete(name),
      toggle: (name, yes) => yes ? this.classes.add(name) : this.classes.delete(name),
    };
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  focus() { this.focused = true; }
  addEventListener() {}
  querySelector() { return null; }
}
class Canvas extends Element { getContext() { return null; } }

function harness(response) {
  const nodes = new Map(), requests = [], downloads = [], blobs = new Map(), errors = [];
  const tabs = ["overview", "shotdata", "color", "objects"].map(view => {
    const el = new Element(); el.dataset.view = view; return el;
  });
  const document = {
    readyState: "loading", body: new Element(), documentElement: new Element(),
    addEventListener() {},
    querySelectorAll: selector => selector === ".tab" ? tabs : [],
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, id.startsWith("wheel-") ? new Canvas() : new Element());
      return nodes.get(id);
    },
    createElement() {
      return { click() { downloads.push({ filename: this.download, blob: blobs.get(this.href) }); }, remove() {} };
    },
  };
  document.body.appendChild = () => {};
  class TestURL extends URL {
    static createObjectURL(value) { const id = `blob:${blobs.size}`; blobs.set(id, value); return id; }
    static revokeObjectURL() {}
  }
  const context = vm.createContext({
    document, HTMLCanvasElement: Canvas, Blob, FormData, URL: TestURL, AbortController,
    console: { error: error => errors.push(error), warn() {}, debug() {} },
    window: { FIRSTROLL_CONFIG: {}, matchMedia: () => ({ matches: false }) },
    fetch: async (url, options) => { requests.push({ url, options }); return response(); },
  });
  vm.runInContext(source, context);
  const app = vm.runInContext("createApplication()", context);
  app.refs.sampleInterval.value = "1";
  app.refs.sceneSensitivity.value = "6";
  app.refs.backendUrl.value = "/api/analyze";
  app.refs.analysisVideo.duration = 10;
  app.refs.analysisVideo.videoWidth = 640;
  app.refs.analysisVideo.videoHeight = 480;
  function select(filename = "clip.mp4") {
    app.refs.videoFile.files = [new File(["video fixture"], filename, { type: "video/mp4" })];
    app.onFileSelected({ target: app.refs.videoFile });
    app.refs.analysisVideo.onloadedmetadata();
  }
  return { app, select, nodes, tabs, requests, downloads, errors };
}

test("typed analysis flow uploads, renders without canvas, and exports JSON/CSV", async () => {
  const h = harness(() => Response.json(fixture()));
  h.select();
  await h.app.onAnalyze();
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].options.body.get("video").name, "clip.mp4");
  assert.equal(h.requests[0].options.body.get("scene_sensitivity"), "6");
  assert.ok(h.app.refs.contents.shotdata.innerHTML.includes("Scene 1"));
  assert.equal(h.app.refs.exportJsonBtn.disabled, false);
  assert.equal(h.errors.length, 0); // Null canvas context is a supported browser condition.
  h.app.exportAnalysisJson();
  h.app.exportScenesCsv();
  h.app.exportShotsCsv();
  const exported = JSON.parse(await h.downloads[0].blob.text());
  assert.equal(exported.videoMeta.filename, "clip.mp4");
  assert.equal(exported.shots[0].shotScale, "Unknown");
  assert.equal(exported.scenes[0].props[0].count, 1);
  assert.ok((await h.downloads[1].blob.text()).startsWith("scene_id,start_sec"));
  assert.ok((await h.downloads[2].blob.text()).includes("Unknown"));
  h.app.generateLlmDraft();
  assert.ok(h.app.refs.llmDraftText.value.includes("Film Clip: clip.mp4"));
});

test("analysis rejects malformed responses safely without enabling export", async () => {
  const h = harness(() => Response.json({ meta: {}, global: {}, scenes: [{}] }));
  h.select();
  await h.app.onAnalyze();
  assert.equal(h.app.refs.exportJsonBtn.disabled, true);
  assert.equal(h.app.refs.analyzeBtn.disabled, false);
  assert.ok(h.app.refs.statusText.textContent.includes("could not complete"));
  h.app.exportAnalysisJson();
  assert.equal(h.downloads.length, 0);
});

test("filenames and detected-object labels remain text, not executable HTML", async () => {
  const data = fixture();
  data.meta.filename = '<img src=x onerror="bad">.mp4';
  data.scenes[0].props[0].label = "<script>bad</script>";
  const h = harness(() => Response.json(data));
  h.select(data.meta.filename);
  assert.ok(h.app.refs.contents.overview.innerHTML.includes("&lt;img"));
  await h.app.onAnalyze();
  assert.ok(!h.app.refs.contents.overview.innerHTML.includes("<img"));
  assert.ok(h.app.refs.contents.objects.innerHTML.includes("&lt;script&gt;"));
  assert.ok(!h.app.refs.contents.objects.innerHTML.includes("<script>"));
});

test("typed keyboard navigation accepts only known analysis view keys", () => {
  const h = harness(() => Response.json(fixture()));
  let prevented = false;
  h.app.onAnalysisTabKeydown({
    key: "ArrowRight", currentTarget: h.tabs[0], preventDefault() { prevented = true; },
  });
  assert.ok(prevented);
  assert.ok(h.tabs[1].focused);
  assert.equal(h.tabs[1].attributes["aria-selected"], "true");
  h.tabs[2].dataset.view = "invented";
  h.app.onAnalysisTabKeydown({ key: "ArrowRight", currentTarget: h.tabs[1], preventDefault() {} });
  assert.equal(h.tabs[1].attributes["aria-selected"], "true");
  h.app.onFileSelected({ target: null }); // Unrelated events cannot supply a file.
  assert.equal(h.requests.length, 0);
});
