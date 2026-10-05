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
const { createAnalysisController } = loadModule("analysis/controller.ts");
const films = loadModule("discovery/films.ts");
const views = loadModule("discovery/views.ts");
const crew = loadModule("shared/crew.ts");

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

test("film duration rounds before splitting hours and minutes", () => {
  assert.equal(format.formatFilmDuration(119.6), "2h");
  assert.equal(format.formatFilmDuration(59.6), "1h");
  assert.equal(format.formatFilmDuration(119.4), "1h 59m");
  assert.equal(format.formatFilmDuration(0.4), "0 min");
  assert.equal(format.formatFilmDuration("98"), "1h 38m");
  assert.equal(format.formatFilmDuration(-1), "");
  assert.equal(format.formatFilmDuration(0), "");
  assert.equal(format.formatFilmDuration(NaN), "");
  assert.equal(format.formatFilmDuration(Infinity), "");
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
  return new Response(new ReadableStream({
    start(controller) {
      for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
      controller.close();
    }
  }));
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
    await assert.rejects(progress.consumeResearchProgress(response(text), "run-1", () => { }), expected);
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

test("film selection uses stable IDs, keeps the first record and never mutates input", () => {
  const original = Object.freeze({ id: "f1", title: "Original" });
  const input = Object.freeze([original, null, undefined, { id: "", title: "Missing ID" }, { id: "f1", title: "Duplicate" }, { id: "f2", title: "Other" }]);
  assert.deepEqual(films.uniqueFilms(input), [original, input[5]]);
  assert.equal(films.uniqueFilms(input)[0], original);
  assert.deepEqual(films.uniqueFilms(input, [original]), [input[5]]);
  assert.equal(input.length, 6);
});

test("displayable films use original/alternative titles and omit raw catalogue IDs", () => {
  const input = [
    { id: "1", title: "Q123", original_title: " 花樣年華 " },
    { id: "2", title: "", alternative_titles: ["Q456", "  Alternate title  "] },
    { id: "3", title: "Q789", original_title: "Q000" },
    { id: "4", title: "Actual film" },
  ];
  assert.deepEqual(films.displayableFilms(input).map(film => film.title), ["花樣年華", "Alternate title", "Actual film"]);
  assert.equal(input[0].title, "Q123");
});

test("director shelf is capped at twelve distinct films with the selected film first", () => {
  const primary = Object.freeze({ id: "selected", title: "Selected film" });
  const others = Array.from({ length: 20 }, (_, index) => ({ id: String(index), title: `Film ${index}` }));
  const shelf = films.directorShelfFilms(primary, [primary, ...others, others[0]]);
  assert.equal(shelf.length, 12);
  assert.equal(shelf[0].id, primary.id);
  assert.equal(new Set(shelf.map(film => film.id)).size, 12);
});

test("crew formatting filters scraped markup, raw IDs and duplicates", () => {
  assert.deepEqual(crew.displayCrewNames([" Wong Kar-wai ", "Wong Kar-wai", "Q123", "<script>", "font-size: 12px", "1234", null, "王家衛"]), ["Wong Kar-wai", "王家衛"]);
  assert.equal(crew.displayCrew({ name: "Not an array" }), "Not supplied");
  assert.equal(crew.firstCrewName([], "Unknown director"), "Unknown director");
});

test("identity choices preserve indexed controls, accessible labels and original titles", () => {
  const markup = views.filmIdentityChoicesMarkup([
    { id: "1", title: 'Film <one> "quoted"', original_title: "花樣年華", year: 2000, directors: ["Wong Kar-wai"] },
    { id: "2", original_title: "Other film", release_years: [2026, 2025] },
  ]);
  assert.ok(markup.includes('data-confirm-film-index="0"'));
  assert.ok(markup.includes('data-confirm-film-index="1"'));
  assert.ok(markup.includes('aria-label="Choose Film &lt;one&gt; &quot;quoted&quot;, 2000, Wong Kar-wai"'));
  assert.ok(markup.includes("<em>花樣年華</em>"));
  assert.ok(markup.includes("2025 · Director not supplied"));
  assert.ok(!markup.includes("Film <one>"));
});

test("shelf separates selected articles from selectable buttons and rejects unsafe posters", () => {
  const primary = { id: "1", title: "First", year: 2000 };
  const markup = views.directorShelfFilmsMarkup(primary, [primary, { id: '2"', title: "<Other>", poster_url: "javascript:alert(1)" }], false);
  assert.equal((markup.match(/aria-current="true"/g) || []).length, 1);
  assert.ok(!markup.includes('data-select-film-id="1"'));
  assert.ok(markup.includes('data-select-film-id="2&quot;"'));
  assert.ok(markup.includes("&lt;Other&gt;"));
  assert.ok(markup.includes("director-film-fallback"));
  assert.ok(!markup.includes("javascript:"));
  assert.ok(!markup.includes("is-skeleton"));
});

test("loading shelf retains selected film, five placeholders and retry/status hooks", () => {
  const primary = { id: "1", title: "First", poster_url: "https://example.com/poster.jpg" };
  const markup = views.directorShelfMarkup(primary, [], "Director", true);
  assert.equal((markup.match(/is-skeleton/g) || []).length, 5);
  assert.ok(markup.includes('data-primary-film-id="1"'));
  assert.ok(markup.includes('data-film-shelf-count>1 film'));
  assert.ok(markup.includes('role="status" aria-live="polite"'));
  assert.ok(markup.includes("data-retry-director-shelf"));
  assert.ok(markup.includes('loading="eager"'));
});

test("archive view preserves case, dossier control and escaped summary without side effects", () => {
  const primary = Object.freeze({ id: "1", title: "Selected <film>", original_title: "Original", year: 2000, runtime_minutes: 98, directors: Object.freeze(["Director"]) });
  const markup = views.filmArchiveMarkup(primary, [], false);
  assert.ok(markup.includes('class="archive-pullout-shell"'));
  assert.ok(markup.includes('class="criterion-object"'));
  assert.ok(markup.includes('data-film-id="1"'));
  assert.ok(markup.includes("2000 · 1h 38m"));
  assert.ok(markup.includes("Selected &lt;film&gt;"));
  assert.ok(markup.includes("Only the selected film") === false);
  assert.ok(markup.includes("1 verified film."));
  assert.equal(primary.title, "Selected <film>");
});
