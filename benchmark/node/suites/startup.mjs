// Startup time of Pyodide.
//
// Startup only happens once per process, so each sample starts a new Node
// process (see ../helpers/startup_child.mjs). The child measures its own
// timings with performance.now(), so the time to start Node itself is not
// included. The first process of each mode is discarded to warm up the OS file
// cache, and the modes are interleaved so that changes in machine load during
// the run affect them equally.
//
// Cases:
//   import_pyodide_mjs:   import("pyodide.mjs")
//   loadPyodide:          loadPyodide()
//   loadPyodide_snapshot: loadPyodide() from dist/snapshot.bin, including
//                         reading it. Skipped if there is no snapshot.bin.
//   first_runPython:      the first runPython("1 + 1") after loading
//   first_import:         the first import of a stdlib module (email.message)

import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

export const description = "Startup time of Pyodide, in fresh processes";
export const usesPyodide = false;

const SAMPLES = 7;
const CHILD = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "helpers",
  "startup_child.mjs",
);

async function runChild(distDir, mode) {
  const { stdout } = await promisify(execFile)(process.execPath, [
    CHILD,
    distDir,
    mode,
  ]);
  return JSON.parse(stdout);
}

function median(xs) {
  const s = [...xs].sort((a, b) => a - b);
  return s[s.length >> 1];
}

export async function run(_pyodide, { filter, distDir }) {
  const modes = ["default"];
  if (
    filter("loadPyodide_snapshot") &&
    existsSync(path.join(distDir, "snapshot.bin"))
  ) {
    modes.push("snapshot");
  }

  const samples = Object.fromEntries(modes.map((m) => [m, []]));
  for (const mode of modes) {
    await runChild(distDir, mode); // warm up
  }
  for (let i = 0; i < SAMPLES; i++) {
    for (const mode of modes) {
      samples[mode].push(await runChild(distDir, mode));
    }
  }

  const stat = (mode, key) => ({
    time: median(samples[mode].map((s) => s[key])),
  });
  const results = {
    import_pyodide_mjs: stat("default", "importModule"),
    loadPyodide: stat("default", "loadPyodide"),
    first_runPython: stat("default", "firstRunPython"),
    first_import: stat("default", "firstImport"),
  };
  if (modes.includes("snapshot")) {
    results.loadPyodide_snapshot = stat("snapshot", "loadPyodide");
  }
  return Object.fromEntries(
    Object.entries(results).filter(([caseName]) => filter(caseName)),
  );
}
