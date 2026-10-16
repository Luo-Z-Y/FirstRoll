const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { transformSync } = require("esbuild");

const root = path.resolve(__dirname, "../..");
const stylesheet = process.env.FIRSTROLL_TEST_APP
  ? path.join(path.dirname(path.resolve(root, process.env.FIRSTROLL_TEST_APP)), "styles.css")
  : path.join(root, "app/web/styles.css");
const css = transformSync(readFileSync(stylesheet, "utf8"), { loader: "css" }).code;
const settings = readFileSync(path.join(root, "app/backend/settings.html"), "utf8").match(/<style>([\s\S]*?)<\/style>/)[1];

function declarations(source, selector) {
  const blocks = [...source.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, selectors]) => selectors.split(",").some(value => value.trim().replaceAll('"', "") === selector.replaceAll('"', "")));
  assert.ok(blocks.length, `Missing ${selector}`);
  return Object.fromEntries(blocks.flatMap(([, , body]) => [...body.matchAll(/([\w-]+):\s*([^;]+);/g)]
    .map(([, name, value]) => [name, value.trim()])));
}

function resolve(variables, name, seen = new Set()) {
  assert.ok(!seen.has(name), `Circular token ${name}`);
  seen.add(name);
  const value = variables[name];
  assert.ok(value, `Undefined token ${name}`);
  const alias = value.match(/^var\((--[\w-]+)\)$/);
  return alias ? resolve(variables, alias[1], seen) : value;
}

function channels(hex) {
  assert.match(hex, /^#[\da-f]{3}(?:[\da-f]{3})?$/i);
  const full = hex.length === 4 ? [...hex.slice(1)].map(digit => digit + digit).join("") : hex.slice(1);
  return full.match(/../g).map(pair => parseInt(pair, 16));
}

function contrast(a, b) {
  const luminance = hex => channels(hex).map(value => {
    const channel = value / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

for (const [name, source] of [["application", css], ["local Settings", settings]]) {
  test(`${name} uses neutral colour literals without filtering film content`, () => {
    const literals = [...source.matchAll(/#([\da-f]{8}|[\da-f]{6}|[\da-f]{4}|[\da-f]{3})\b|rgba?\(([^)]*)\)/gi)];
    assert.ok(literals.length > 40);
    for (const [literal, hex, rgb] of literals) {
      const values = hex
        ? channels(`#${hex.length <= 4 ? hex.slice(0, 3) : hex.slice(0, 6)}`)
        : rgb.trim().split(/[\s,\/]+/).slice(0, 3).map(Number);
      assert.equal(new Set(values).size, 1, `${name}: ${literal} is not neutral`);
    }
    assert.doesNotMatch(source, /grayscale\(/i, "Film images and measured colours must remain intact");
    const defined = new Set([...source.matchAll(/(--[\w-]+):/g)].map(match => match[1]));
    for (const [, token] of source.matchAll(/var\((--[\w-]+)/g)) {
      assert.ok(defined.has(token), `${name}: ${token} has no definition`);
    }
  });

  for (const theme of ["light", "dark"]) {
    test(`${name} ${theme} text, actions and focus retain contrast`, () => {
      const variables = { ...declarations(source, ":root"),
        ...(theme === "dark" ? declarations(source, 'html[data-theme="dark"]') : {}) };
      const value = token => resolve(variables, token);
      const muted = name === "application" ? "--ink-soft" : "--soft";
      const actionText = name === "application" ? "--action-text" : "--on-red";
      for (const text of ["--ink", muted]) assert.ok(contrast(value(text), value("--paper")) >= 4.5);
      for (const action of ["--red", "--red-dark"]) assert.ok(contrast(value(actionText), value(action)) >= 4.5);
      assert.ok(contrast(value("--focus"), value("--paper")) >= 3);
    });
  }
}

test("permanently dark panels scope readable actions and secondary text in both themes", () => {
  for (const theme of ["light", "dark"]) {
    for (const panel of [".card", ".detail-hero", ".deep-study", ".director-shelf", ".integration-quota", ".interface-state.is-inverse"]) {
      const variables = { ...declarations(css, ":root"),
        ...(theme === "dark" ? declarations(css, 'html[data-theme="dark"]') : {}),
        ...declarations(css, panel) };
      const value = token => resolve(variables, token);
      assert.ok(contrast(value("--ink-soft"), value("--night-panel")) >= 4.5, `${panel} secondary text`);
      for (const text of ["--ink", "--ink-soft"]) {
        assert.ok(contrast(value(text), value("--panel-bg")) >= 4.5, `${panel} nested interface state`);
      }
      assert.ok(contrast(value("--action-text"), value("--red")) >= 4.5, `${panel} action text`);
      assert.ok(contrast(value("--red"), value("--night-panel")) >= 3, `${panel} action boundary`);
      assert.ok(contrast(value("--focus"), value("--night-panel")) >= 3, `${panel} focus`);
    }
  }
  assert.equal(declarations(css, ".auth-dialog form button").color, "var(--action-text)");
  assert.equal(declarations(css, ".deep-study").background, "var(--night)");
});

test("monochrome festival and quality states retain non-colour distinctions", () => {
  assert.equal(declarations(css, ".festival-pin.is-soon .festival-pin-dot").fill, "var(--paper-light)");
  assert.ok(declarations(css, ".festival-pin.is-awards .festival-pin-dot")["stroke-dasharray"]);
  assert.ok(declarations(css, ".festival-pin.is-now .festival-pin-halo").fill);
  assert.ok(declarations(css, ".festival-legend .is-soon").border.includes("solid"));
  assert.ok(declarations(css, ".festival-legend .is-awards").border.includes("dashed"));
  assert.ok(declarations(css, ".festival-bar.is-soon")["box-shadow"].includes("inset"));
  assert.match(declarations(css, ".festival-bar.is-awards").background, /repeating-linear-gradient/);
  assert.equal(declarations(css, ".packet-status.is-limited")["border-style"], "dashed");
});
