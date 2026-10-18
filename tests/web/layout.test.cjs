const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { transformSync } = require("esbuild");

// The only chromatic literals: one sparse UI red (light, dark and the permanently dark
// panels) and four festival data colours (light and dark). Everything else stays grey.
const ACCENT_DECLARATION = /(?<![\w-])(--signal|--festival-(?:now|soon|later|awards)):\s*#[\da-f]{6};/gi;

test("welcome entry has no focus box but retains an underlined keyboard cue", () => {
  const root = path.resolve(__dirname, "../..");
  const stylesheet = process.env.FIRSTROLL_TEST_APP
    ? path.join(path.dirname(path.resolve(root, process.env.FIRSTROLL_TEST_APP)), "styles.css")
    : path.join(root, "app/web/styles.css");
  const css = transformSync(readFileSync(stylesheet, "utf8"), { loader: "css" }).code;
  assert.match(css, /\.welcome-enter:focus-visible\s*\{[^}]*outline: none;[^}]*text-decoration: underline;/);
  // Static text colours key off the state mirrored onto the dialog, not :has() (Firefox < 121).
  assert.match(css, /\.welcome-screen\[data-shader-state=static\] \.welcome-enter[^{]*\{[^}]*color: var\(--ink\);/);
  assert.doesNotMatch(css, /:has\([^)]*discovery-shader/);
});

test("UI stylesheet is grey apart from named accent tokens, without filtering film artwork", () => {
  const root = path.resolve(__dirname, "../..");
  const stylesheet = process.env.FIRSTROLL_TEST_APP
    ? path.join(path.dirname(path.resolve(root, process.env.FIRSTROLL_TEST_APP)), "styles.css")
    : path.join(root, "app/web/styles.css");
  const source = transformSync(readFileSync(stylesheet, "utf8"), { loader: "css" }).code;
  const counts = {};
  for (const [, token] of source.matchAll(ACCENT_DECLARATION)) counts[token] = (counts[token] || 0) + 1;
  assert.deepEqual(counts, { "--signal": 3, "--festival-now": 2, "--festival-soon": 2, "--festival-later": 2, "--festival-awards": 2 });
  const css = source.replace(ACCENT_DECLARATION, "");
  for (const [, hex] of css.matchAll(/#([\da-f]{6}|[\da-f]{3})\b/gi)) {
    const expanded = hex.length === 3 ? [...hex].map(c => c + c).join("") : hex;
    assert.equal(expanded.slice(0, 2), expanded.slice(2, 4), hex);
    assert.equal(expanded.slice(2, 4), expanded.slice(4, 6), hex);
  }
  for (const [, red, green, blue] of css.matchAll(/rgba?\((\d+),\s*(\d+),\s*(\d+)/g)) {
    assert.equal(red, green);
    assert.equal(green, blue);
  }
  assert.doesNotMatch(css, /grayscale\(/);
  assert.match(css, /--accent:/);
  assert.match(css, /--focus:/);
  // Keep the red sparse: only these rules may paint with the signal token.
  const signalRules = [...source.matchAll(/([^{}]+)\{[^{}]*var\(--signal\)[^{}]*\}/g)].map(([, selector]) => selector.trim()).sort();
  assert.deepEqual(signalRules, [
    ".brand-mark",
    ".inline-fetch-track i",
    ".nav-link.active",
    ".progress-bar",
    "html[data-build-channel=live] .build-identity",
  ]);
  // Festival data colours stay inside the atlas.
  for (const [, selector] of source.matchAll(/([^{}]+)\{[^{}]*var\(--festival-[^{}]*\}/g)) {
    assert.match(selector.trim(), /^\.festival-/, selector);
  }
});

test("small-screen header keeps shrinkable tracks and a later stacked brand override", () => {
  const root = path.resolve(__dirname, "../..");
  const stylesheet = process.env.FIRSTROLL_TEST_APP
    ? path.join(path.dirname(path.resolve(root, process.env.FIRSTROLL_TEST_APP)), "styles.css")
    : path.join(root, "app/web/styles.css");
  // Protect the cascade contract in source and released CSS; browser measurements
  // are still required to establish that the layout actually fits.
  const css = transformSync(readFileSync(stylesheet, "utf8"), { loader: "css" }).code;
  const narrow = css.lastIndexOf("@media (max-width: 380px)");
  const mobile = css.lastIndexOf("@media (max-width: 640px)");
  assert.ok(narrow > mobile && mobile > 0);
  // Five destinations, the build label and the longest signed-in identity overflow one row
  // below about 1,190px (measured with the real fonts), so the nav takes its own row below
  // 1,200px; phones then refine it.
  const tablet = css.lastIndexOf("@media (max-width: 1199px)");
  assert.ok(tablet > 0 && tablet < mobile);
  const tabletRules = css.slice(tablet, css.indexOf("\n}", tablet));
  assert.match(tabletRules, /\.site-header\s*\{[^}]*grid-template-columns: minmax\(0, 1fr\) auto;/);
  assert.match(tabletRules, /\.site-header\s*\{[^}]*grid-template-areas: "brand tools" "nav nav";/);
  assert.match(tabletRules, /\.brand\s*\{[^}]*grid-area: brand;/);
  assert.match(tabletRules, /\.primary-nav\s*\{[^}]*grid-area: nav;/);
  assert.match(tabletRules, /\.header-tools\s*\{[^}]*grid-area: tools;/);
  const rules = css.slice(mobile, narrow);
  assert.match(rules, /\.site-header\s*\{[^}]*grid-template-columns: minmax\(0, 1fr\) auto;/);
  assert.match(rules, /\.primary-nav\s*\{[^}]*min-width: 0;/);
  assert.match(rules, /\.primary-nav \.nav-link\s*\{[^}]*min-width: 0;[^}]*min-height: 44px;/);
  assert.match(css.slice(narrow), /\.brand\s*\{[^}]*display: grid;/);
  assert.match(css.slice(narrow), /\.brand \.build-identity\s*\{[^}]*grid-column: 1 \/ -1;/);
});

test("days with no films keep their label contrast and are marked by a dashed rule", () => {
  const root = path.resolve(__dirname, "../..");
  const stylesheet = process.env.FIRSTROLL_TEST_APP
    ? path.join(path.dirname(path.resolve(root, process.env.FIRSTROLL_TEST_APP)), "styles.css")
    : path.join(root, "app/web/styles.css");
  const css = transformSync(readFileSync(stylesheet, "utf8"), { loader: "css" }).code;
  // A quiet day is still an enabled toggle, so fading it would take its label below 4.5:1.
  assert.match(css, /\.screenings-days button\.is-quiet\s*\{[^}]*border-style: dashed;/);
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!/\.screenings-days button(?![\w-]| span)/.test(selector)) continue;
    assert.doesNotMatch(body, /opacity:/, selector.trim());
  }
});
