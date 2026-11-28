// Runs pyperformance in Pyodide in a fresh process.
//
// Usage:
//   node pyperformance_child.mjs DIST_DIR DEPS_DIR list
//   node pyperformance_child.mjs DIST_DIR DEPS_DIR run NAME APPEND_FILE [PYPERF_ARGS...]
//
// DEPS_DIR is a directory with pyperf and pyperformance installed in it.
// If APPEND_FILE isn't empty, the pyperf results are added to it.
//
// Prints the result of pyperformance_driver.list_benchmarks() or
// run_benchmark() to stdout. The output of Python goes to stderr.

import { writeSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const [distDir, depsDir, mode, name, appendFile, ...pyperfArgs] =
  process.argv.slice(2);

const { loadPyodide } = await import(
  pathToFileURL(path.join(distDir, "pyodide.mjs")).href
);
const pyodide = await loadPyodide({
  indexURL: distDir + "/",
  stdout: (s) => process.stderr.write(s + "\n"),
  stderr: (s) => process.stderr.write(s + "\n"),
});
// Mount host directories at the same paths
const mounts = [depsDir];
if (appendFile) {
  mounts.push(path.dirname(appendFile));
}
for (const dir of mounts) {
  pyodide.FS.mkdirTree(dir);
  pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root: dir }, dir);
}
pyodide.runPython("import sys; sys.path.insert(0, DEPS_DIR)", {
  globals: pyodide.toPy({ DEPS_DIR: depsDir }),
});

const driver = pyodide.runPython(
  "import types; types.ModuleType('pyperformance_driver')",
);
const source = await readFile(
  path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "pyperformance_driver.py",
  ),
  "utf8",
);
pyodide.runPython(source, { globals: driver.__dict__ });

let result;
try {
  if (mode === "list") {
    result = driver.list_benchmarks();
  } else if (mode === "run") {
    // callPromising so that the asyncio benchmarks can use
    // loop.run_until_complete(), which needs JSPI.
    result = await driver.run_benchmark.callPromising(
      name,
      pyodide.toPy(pyperfArgs),
      appendFile,
    );
  } else {
    throw new Error(`Unknown mode ${mode}`);
  }
} catch (e) {
  console.error(e.message);
  process.exit(1);
}
writeSync(1, result + "\n");
process.exit(0);
