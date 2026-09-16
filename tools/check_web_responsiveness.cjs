#!/usr/bin/env node
// Optional, synthetic browser diagnostic. Requires Playwright 1.58.2 and installed Chrome.
// No backend is started; page HTTP requests are fulfilled locally or blocked.
// Speculative connection hints are removed; this is not an OS-level network sandbox.
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const { createHash } = require("node:crypto");
const { mkdtempSync, readFileSync, writeFileSync } = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const revision = process.argv[2];
if (!revision || !/^[0-9a-f]{40}$/.test(revision)) {
  throw new Error("Supply the full baseline Git commit SHA as the only argument.");
}
const output = mkdtempSync(path.join(os.tmpdir(), "firstroll-web-evidence-"));
const assets = ["index.html", "app.js", "styles.css", "integrations.js", "favicon.svg"];
const baseline = Object.fromEntries(assets.map((name) => [name, execFileSync(
  "git", ["show", `${revision}:app/web/${name}`], { cwd: root },
)]));
const candidate = Object.fromEntries(assets.map((name) => [name, readFileSync(
  path.join(root, "dist", name === "index.html" ? name : `assets/${name}`),
)]));
const film = {
  id: "Q1", title: "Synthetic Study Film", year: 2026, directors: ["Test Filmmaker"],
  overview: "A synthetic fixture for offline interface checks, not evidence about a real film.",
  critical_research: { providers: {}, bundles: {} },
};
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return Number(sorted[Math.max(0, Math.ceil(sorted.length * fraction) - 1)].toFixed(2));
}

async function measure(browser, variant, width) {
  const context = await browser.newContext({
    viewport: { width, height: 1000 }, locale: "en-GB", serviceWorkers: "block",
    reducedMotion: "reduce",
  });
  const errors = [];
  const unexpected = [];
  let mockStudyRequests = 0;
  try {
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== "https://firstroll.test") return route.abort();
      const json = (data) => route.fulfill({ json: data });
      if (url.pathname === "/assets/config.js") {
        return route.fulfill({ contentType: "application/javascript", body:
          'window.FIRSTROLL_CONFIG = { publicMode: true, videoAnalysisEnabled: false };',
        });
      }
      if (url.pathname === "/api/discovery/status") return json({ mode: "synthetic" });
      if (url.pathname === "/api/discovery/search") {
        return json({ query: { title: film.title }, results: [film], mode: "synthetic" });
      }
      if (url.pathname.endsWith("/related")) return json({ same_director: [] });
      if (url.pathname.endsWith("/reception")) return json({ scores: [] });
      if (url.pathname === "/api/discovery/films/Q1") return json({ film });
      if (url.pathname.endsWith("/study/stream")) {
        mockStudyRequests += 1;
        // Keep the entirely mocked run pending until the test cancels it.
        await delay(1000);
        return route.abort().catch(() => {});
      }
      const name = url.pathname === "/" ? "index.html" : url.pathname.replace(/^\/assets\//, "");
      const body = (variant === "baseline" ? baseline : candidate)[name];
      if (body) {
        const extension = path.extname(name);
        // Preconnect/DNS hints bypass Playwright's HTTP interception; omit them in this fixture.
        const served = name === "index.html"
          ? body.toString("utf8").replace(/<link\b[^>]*\brel=["'](?:preconnect|dns-prefetch)["'][^>]*>/gi, "")
          : body;
        return route.fulfill({ body: served, contentType: {
          ".html": "text/html", ".js": "application/javascript", ".css": "text/css",
          ".svg": "image/svg+xml",
        }[extension] });
      }
      unexpected.push(url.pathname);
      return route.abort();
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    const cdp = await context.newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.goto("https://firstroll.test");
    await page.evaluate(() => {
      window.FirstRollAuth = {
        currentUser: () => ({ id: "synthetic", email: "test@example.invalid" }),
        isFilmSaved: () => false,
        authorisationHeaders: () => new Promise((resolve) => window.setTimeout(
          () => resolve({ Authorization: "Bearer synthetic" }), 500,
        )),
      };
    });
    await page.locator("#filmTitle").fill(film.title);
    await page.locator("#discoverySubmit").click();
    await page.locator('[data-film-id="Q1"]').click();
    await page.locator("[data-dossier-heading]").waitFor();

    const samples = [];
    for (let iteration = 0; iteration < 20; iteration += 1) {
      await page.evaluate(() => {
        const button = document.querySelector("[data-generate-study]");
        window.busyEvidence = new Promise((resolve, reject) => {
          const timeout = window.setTimeout(() => {
            observer.disconnect();
            reject(new Error("No responsive busy state within five seconds."));
          }, 5000);
          let started;
          button.addEventListener("click", () => { started = performance.now(); }, {
            once: true, capture: true,
          });
          const observer = new MutationObserver(() => {
            if (!button.disabled || started === undefined) return;
            observer.disconnect();
            window.clearTimeout(timeout);
            const busyMs = performance.now() - started;
            window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve({
              busyMs,
              nextFrameMs: performance.now() - started,
              busy: document.querySelector("[data-study-output]").getAttribute("aria-busy"),
              canCancel: !document.querySelector("[data-cancel-study]").classList.contains("hidden"),
            })));
          });
          observer.observe(button, { attributes: true, attributeFilter: ["disabled"] });
        });
      });
      await page.locator("[data-generate-study]").click();
      const sample = await page.evaluate(() => window.busyEvidence);
      assert.equal(sample.busy, "true");
      assert.equal(sample.canCancel, true);
      samples.push(sample);
      if (iteration === 0 && variant === "candidate") {
        await page.screenshot({ path: path.join(output, `study-busy-${width}.png`), fullPage: true });
      }
      await page.locator("[data-cancel-study]").click();
      await page.getByText("You stopped waiting for this study.").waitFor();
    }
    // Let delayed authentication settle: cancelled candidate runs must send no study POST.
    await page.waitForTimeout(600);
    if (variant === "candidate") assert.equal(mockStudyRequests, 0);
    assert.deepEqual(errors, []);
    assert.deepEqual(unexpected, []);
    const overflow = await page.evaluate(() => (
      document.documentElement.scrollWidth > window.innerWidth
    ));
    assert.equal(overflow, false, "The fixture must not overflow the viewport.");
    return {
      variant, width, samples: samples.length, injectedAuthDelayMs: 500, cpuThrottle: 4,
      busyMs: { median: percentile(samples.map((s) => s.busyMs), 0.5), p95: percentile(samples.map((s) => s.busyMs), 0.95) },
      nextFrameMs: { median: percentile(samples.map((s) => s.nextFrameMs), 0.5), p95: percentile(samples.map((s) => s.nextFrameMs), 0.95) },
      mockStudyRequests, pageErrors: errors.length, horizontalOverflow: overflow,
    };
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const results = [];
    for (const width of [390, 1440]) {
      for (const variant of ["baseline", "candidate"]) {
        results.push(await measure(browser, variant, width));
      }
    }
    const report = {
      baselineRevision: revision,
      candidateAssetsSha256: Object.fromEntries(assets.map((name) => [
        name, createHash("sha256").update(candidate[name]).digest("hex"),
      ])),
      browser: browser.version(), results,
      limitation: "Synthetic session-delay diagnostic, not live latency, INP or model performance. Next-frame timing is a paint proxy only. External page HTTP requests are blocked and speculative connection hints removed; this is not an OS-level network sandbox.",
    };
    writeFileSync(path.join(output, "report.json"), `${JSON.stringify(report, null, 2)}\n`);
    console.log(JSON.stringify(report, null, 2));
    console.error(`Synthetic screenshots and report: ${output}`);
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
