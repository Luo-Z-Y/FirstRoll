const assert = require("node:assert/strict");
const test = require("node:test");
const path = require("node:path");
const Module = require("node:module");
const { buildSync } = require("esbuild");

// Exercise the real TypeScript sources, not duplicate implementations in fixtures.
function loadModule(relativePath) {
  const filename = path.resolve(__dirname, "../../app/web/src", relativePath);
  const result = buildSync({ entryPoints: [filename], bundle: true, platform: "node", format: "cjs", write: false });
  const module = new Module(filename);
  module._compile(result.outputFiles[0].text, filename);
  return module.exports;
}

const html = loadModule("shared/html.ts");
const format = loadModule("shared/format.ts");
const progress = loadModule("study/progress.ts");
const errors = loadModule("api/errors.ts");
const math = loadModule("analysis/math.ts");
const analysis = loadModule("analysis/heuristics.ts");
const { createAnalysisController } = loadModule("analysis/controller.js");

test("provider text is escaped and unsafe links are rejected", () => {
  assert.equal(html.escapeHtml('<img src="x" onerror=\'x\'>&'), "&lt;img src=&quot;x&quot; onerror=&#039;x&#039;&gt;&amp;");
  assert.equal(html.escapeHtml(null), "");
  for (const url of ["javascript:alert(1)", "data:text/html,x", "/relative", "invalid"]) {
    assert.equal(html.safeHttpUrl(url), null);
  }
  assert.equal(html.safeHttpUrl("https://example.com/film"), "https://example.com/film");
});

test("only recognised video embed hosts and identifiers are accepted", () => {
  const youtube = "https://www.youtube-nocookie.com/embed/abcdefghijk";
  assert.equal(html.safeVideoEmbedUrl(youtube), youtube);
  assert.equal(html.safeVideoEmbedUrl("https://player.bilibili.com/player.html?bvid=BV1234567890"), "https://player.bilibili.com/player.html?bvid=BV1234567890");
  for (const url of [youtube.replace("https:", "http:"), youtube.replace(".com/", ".com.evil.test/"), youtube + "l", "https://example.com/embed/abcdefghijk"]) {
    assert.equal(html.safeVideoEmbedUrl(url), null);
  }
});

test("time, file-size and film-year labels retain their existing behaviour", () => {
  assert.equal(format.formatTime(3661), "01:01:01");
  assert.equal(format.formatTime(NaN), "00:00");
  assert.equal(format.formatTime(-20), "00:00");
  assert.equal(format.formatBytes(1024), "1.0 KB");
  assert.equal(format.formatFilmDuration(98), "1h 38m");
  assert.equal(format.formatFilmDuration(null), "");
  assert.equal(format.filmYearLabel({ year: 2026, release_years: [2025, "2026", null] }), "2025");
  assert.equal(format.filmYearLabel(null), "Year unknown");
  assert.equal(format.normaliseFilmYear(1870), null);
});

test("API errors retain safe HTTP-status fallback for malformed responses", async () => {
  assert.equal(await errors.readApiError(Response.json({ detail: "Try again" }, { status: 429 })), "Try again");
  assert.equal(await errors.readApiError(Response.json({ detail: { message: "Unavailable" } }, { status: 503 })), "Unavailable");
  for (const body of ["not json", "null", "{}", '{"detail":[]}']) {
    assert.equal(await errors.readApiError(new Response(body, { status: 503 })), "HTTP 503");
  }
});

function event(overrides = {}) {
  return { run_id: "run-1", sequence: 1, kind: "existing_evidence_loading", message: "Reading…", elapsed_ms: 0, counts: {}, ...overrides };
}
function packet(value) { return `event: progress\ndata: ${JSON.stringify(value)}\n\n`; }
function response(text) {
  const bytes = new TextEncoder().encode(text);
  // Byte-by-byte chunks also split the multibyte ellipsis and SSE delimiters.
  return new Response(new ReadableStream({ start(controller) {
    for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
    controller.close();
  } }));
}

test("progress parser ignores unrelated events and rejects untrusted fields/counts", () => {
  assert.equal(progress.parseProgressEvent("event: heartbeat\ndata: {}"), null);
  assert.deepEqual(progress.parseProgressEvent(packet(event())), event());
  for (const changes of [{ secret: "not allowed" }, { kind: "invented" }, { message: "x".repeat(181) }, { counts: { tokens: 1 } }, { counts: { sections: -1 } }, { counts: { sections: "2" } }]) {
    assert.throws(() => progress.parseProgressEvent(packet(event(changes))), /invalid/);
  }
});

test("chunked UTF-8 progress completes in order and escapes provider text in the view", async () => {
  const events = [];
  await progress.consumeResearchProgress(response(packet(event()) + packet(event({ sequence: 2, kind: "run_completed", message: "<script>" }))), "run-1", value => events.push(value));
  assert.equal(events[0].message, "Reading…");
  assert.equal(events.length, 2);
  const markup = progress.researchProgressMarkup(events, { completed: true });
  assert.ok(markup.includes("Run complete"));
  assert.ok(markup.includes("&lt;script&gt;"));
  assert.ok(!markup.includes("<script>"));
});

test("progress fails safely on cross-run, sequence-gap, early EOF and failed-run streams", async () => {
  for (const [text, expected] of [
    [packet(event({ run_id: "other" })), /invalid/],
    [packet(event({ sequence: 2 })), /invalid/],
    [packet(event()), /before completion/],
    [packet(event({ kind: "run_failed", message: "Research unavailable" })), /Research unavailable/],
  ]) {
    await assert.rejects(progress.consumeResearchProgress(response(text), "run-1", () => {}), expected);
  }
});

test("analysis maths preserves RGB, distance and empty-input conventions", () => {
  assert.deepEqual(math.averageRgb([[0, 10, 20], [20, 30, 40]]), [10, 20, 30]);
  assert.deepEqual(math.averageRgb([]), [0, 0, 0]);
  assert.equal(math.rgbDistance([0, 0, 0], [3, 4, 0]), 5);
  assert.equal(math.rgbToHue([0, 255, 0]), 120);
  assert.equal(math.rgbToCss([-2, 256, 12.5]), "rgb(0, 255, 13)");
  assert.equal(math.pct(5, 0), 0);
});

test("local analysis keeps existing frame, shot and scene heuristics", () => {
  const features = analysis.extractFrameFeatures(new Uint8ClampedArray([255, 0, 0, 255]), 1, 1);
  assert.deepEqual(features.avgRgb, [255, 0, 0]);
  assert.equal(features.hist.reduce((a, b) => a + b, 0), 1);
  assert.equal(features.texture, 0);
  assert.deepEqual(analysis.detectShots([], 10, 5), []);
  const shots = analysis.detectShots([{ ...features, timeSec: 0 }], 10, 5);
  assert.equal(shots.length, 1);
  assert.equal(shots[0].durationSec, 10);
  assert.equal(analysis.classifyShotScale(0.62), "Close-Up");
  assert.equal(analysis.classifyShotScale(0.49), "Medium");
  const scenes = analysis.detectScenes(shots, 10, 5);
  assert.deepEqual(scenes[0].shotIds, [1]);
  assert.equal(analysis.summarizeScenes(scenes, shots)[0].shotCount, 1);
});

test("analysis controllers own independent UI references and do not expose clip state", async () => {
  const names = ["openShotDataBtn", "openColorBtn", "openObjectsBtn", "exportJsonBtn", "exportScenesCsvBtn", "exportShotsCsvBtn", "generateLlmDraftBtn"];
  const refs = () => Object.fromEntries(names.map(name => [name, { disabled: true }]));
  const left = refs(), right = refs();
  const controller = createAnalysisController(left);
  createAnalysisController(right);
  controller.setFeatureButtonsEnabled(true);
  assert.ok(names.every(name => !left[name].disabled && right[name].disabled));
  assert.equal(controller.state, undefined);
  // No clip: no DOM or network work should be attempted.
  await controller.onAnalyze();
});
