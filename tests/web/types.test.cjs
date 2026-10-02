const assert = require("node:assert/strict");
const { test } = require("node:test");
const path = require("node:path");
const ts = require("typescript");

test("strict TypeScript contracts reject invalid DOM, state and analysis result usage", () => {
  const root = path.resolve(__dirname, "../..");
  const configPath = path.join(root, "tsconfig.json");
  const configFile = ts.readConfigFile(configPath, ts.sys.readFile);
  assert.equal(configFile.error, undefined);
  const config = ts.parseJsonConfigFileContent(configFile.config, ts.sys, root);
  assert.equal(config.errors.length, 0);
  assert.equal(config.options.strict, true);
  const program = ts.createProgram(
    [...config.fileNames, path.join(__dirname, "type-contracts.ts")], config.options,
  );
  const diagnostics = ts.getPreEmitDiagnostics(program);
  assert.equal(diagnostics.length, 0, ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: name => name, getCurrentDirectory: () => root, getNewLine: () => "\n",
  }));
});
