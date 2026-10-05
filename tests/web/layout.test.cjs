const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { transformSync } = require("esbuild");

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
  const rules = css.slice(mobile, narrow);
  assert.match(rules, /\.site-header\s*\{[^}]*grid-template-columns: minmax\(0, 1fr\) auto;/);
  assert.match(rules, /\.primary-nav\s*\{[^}]*min-width: 0;/);
  assert.match(rules, /\.primary-nav \.nav-link\s*\{[^}]*min-width: 0;[^}]*min-height: 44px;/);
  assert.match(css.slice(narrow), /\.brand\s*\{[^}]*display: grid;/);
  assert.match(css.slice(narrow), /\.brand \.build-identity\s*\{[^}]*grid-column: 1 \/ -1;/);
});
