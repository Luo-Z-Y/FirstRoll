const path = require("node:path");
const { buildSync } = require("esbuild");
const { execFileSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");

// One compiler configuration for localhost, hosted releases and the request-race tests.
// The entry exports nothing: esbuild resolves imports into a classic-script-compatible file.
// Keep the composition-root name stable so tests can construct an independent application
// from the exact release bundle. Feature handlers are injected, never replaced by hoisting.
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

const adapterNames = ["auth", "entra-auth", "local-auth", "integrations", "config", "theme-init", "auth-loader", "festivals"];
function bundleAdapters(outdir, { minify = false } = {}) {
  return buildSync({
    absWorkingDir: root,
    entryPoints: adapterNames.map(name => `app/web/${name}.ts`),
    outdir, bundle: true, format: "iife", minify,
    target: ["es2020", "chrome100", "firefox100", "safari15.4"],
  });
}
module.exports = { bundleApplication, bundleAdapters };

if (require.main === module) {
  execFileSync(process.execPath, [require.resolve("typescript/bin/tsc"), "--noEmit"], {
    cwd: root, stdio: "inherit",
  });
  const local = process.argv[2] === "--local";
  const outfile = local ? "app/web/generated/app.js" : process.argv[2];
  if (!outfile) throw new Error("Supply an output path or --local.");
  bundleApplication({ outfile: path.resolve(root, outfile), minify: !local });
  bundleAdapters(path.dirname(path.resolve(root, outfile)), { minify: !local });
}
