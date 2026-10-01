const path = require("node:path");
const { buildSync } = require("esbuild");
const { execFileSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");

// One compiler configuration for localhost, hosted releases and the request-race tests.
// The entry exports nothing: esbuild resolves imports into a classic-script-compatible file.
// Keep identifiers stable during this migration for the existing global-handler test harness.
function bundleApplication(options = {}) {
  const { minify = false, ...buildOptions } = options;
  return buildSync({
    absWorkingDir: root,
    entryPoints: ["app/web/src/main.ts"],
    bundle: true,
    format: "esm",
    target: ["es2020", "chrome100", "firefox100", "safari15.4"],
    minifyWhitespace: Boolean(minify),
    minifySyntax: Boolean(minify),
    minifyIdentifiers: false,
    ...buildOptions,
  });
}

module.exports = { bundleApplication };

if (require.main === module) {
  execFileSync(process.execPath, [require.resolve("typescript/bin/tsc"), "--noEmit"], {
    cwd: root, stdio: "inherit",
  });
  const local = process.argv[2] === "--local";
  const outfile = local ? "app/web/generated/app.js" : process.argv[2];
  if (!outfile) throw new Error("Supply an output path or --local.");
  bundleApplication({ outfile: path.resolve(root, outfile), minify: !local });
}
