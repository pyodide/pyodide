// Measures Pyodide startup in a fresh process, see ../suites/startup.mjs.
//
// Usage: node startup_child.mjs DIST_DIR (default|snapshot)
//
// Prints the timings in ms as JSON to stdout.

import { writeSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [distDir, mode] = process.argv.slice(2);

const t0 = performance.now();
const { loadPyodide } = await import(
  pathToFileURL(path.join(distDir, "pyodide.mjs")).href
);
const t1 = performance.now();
const options = { indexURL: distDir + "/" };
if (mode === "snapshot") {
  // Reading the snapshot is part of the startup cost, like reading
  // pyodide.asm.wasm and python_stdlib.zip is in the default mode.
  options._loadSnapshot = await readFile(path.join(distDir, "snapshot.bin"));
}
let pyodide;
try {
  pyodide = await loadPyodide(options);
} catch (e) {
  if (mode === "snapshot") {
    e.message +=
      "\nsnapshot.bin may not match the build, regenerate it with " +
      "`cd dist && node makesnap.mjs`";
  }
  throw e;
}
const t2 = performance.now();
const two = pyodide.runPython("1 + 1");
const t3 = performance.now();
// Not imported during startup (checked by the assertion below), so this
// measures the first import of a module from the standard library zip.
pyodide.runPython(`
import sys
assert "email.message" not in sys.modules
import email.message
`);
const t4 = performance.now();

if (two !== 2) {
  throw new Error(`Unexpected result: ${two}`);
}
writeSync(
  1,
  JSON.stringify({
    importModule: t1 - t0,
    loadPyodide: t2 - t1,
    firstRunPython: t3 - t2,
    firstImport: t4 - t3,
  }) + "\n",
);
process.exit(0);
