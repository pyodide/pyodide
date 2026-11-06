// Runs the benchmark scripts of the pyperformance package.
// pyperf and pyperformance are installed on the host with `pip install --target` into DEPS_DIR (on the first run)
// and mounted into Pyodide with NODEFS, see ../helpers/pyperformance_child.mjs.
//
// Each benchmark runs in a fresh Node process, because some benchmarks change
// global state (e.g. sys.modules or the gc). pyperf measures the time, the
// reported time is the median of its values. Benchmarks that fail (e.g.
// because an older build lacks a fix they need) are reported on stderr and
// left out of the results.
//
// This suite is slow, so it only runs when selected with
// `--suite pyperformance`. Use --filter to select benchmarks by their
// pyperformance name, e.g. --filter 'pyperformance/(nbody|richards)'.
//
// Environment variables:
//   PYPERFORMANCE_DEPS_DIR  Where to install the packages
//                           (default: benchmark/node/.pyperformance).
//   PYPERFORMANCE_ARGS      Options for pyperf (default: "--fast"),
//                           e.g. "--rigorous" or "--values 3 --processes 5".
//   PYTHON                  The host Python to run pip with (default: python3).

import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

export const description =
  "pyperformance benchmarks (slow, only runs with --suite pyperformance)";
export const usesPyodide = false;
export const runByDefault = false;

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CHILD = path.join(HERE, "..", "helpers", "pyperformance_child.mjs");

const REQUIREMENTS = [
  "pyperformance==1.14.0",
  "packaging",
  // Remove pin when pyperf 2.11.0 is out
  "pyperf @ git+https://github.com/psf/pyperf@6c20d27abb9752ed9da75559e3bca260126cb25b",
];

const execFileAsync = promisify(execFile);

async function installDeps(depsDir) {
  // Install again if REQUIREMENTS changed since the last install.
  const marker = path.join(depsDir, "requirements.txt");
  const wanted = REQUIREMENTS.join("\n") + "\n";
  if (existsSync(marker) && (await readFile(marker, "utf8")) === wanted) {
    return;
  }
  await rm(depsDir, { recursive: true, force: true });
  await mkdir(depsDir, { recursive: true });
  console.error(`Installing pyperformance into ${depsDir}`);
  await execFileAsync(process.env.PYTHON ?? "python3", [
    "-m",
    "pip",
    "install",
    "--quiet",
    "--no-deps",
    "--target",
    depsDir,
    ...REQUIREMENTS,
  ]);
  await writeFile(marker, wanted);
}

async function runChild(distDir, depsDir, args) {
  const { stdout } = await execFileAsync(
    process.execPath,
    ["--experimental-wasm-jspi", CHILD, distDir, depsDir, ...args],
    { maxBuffer: 64 * 1024 * 1024 },
  );
  return JSON.parse(stdout);
}

export async function run(_pyodide, { filter, distDir }) {
  const depsDir = path.resolve(
    process.env.PYPERFORMANCE_DEPS_DIR ??
      path.join(HERE, "..", ".pyperformance"),
  );
  const pyperfArgs = (process.env.PYPERFORMANCE_ARGS ?? "--fast")
    .split(/\s+/)
    .filter(Boolean);
  await installDeps(depsDir);

  const names = (await runChild(distDir, depsDir, ["list"])).filter(filter);
  // Progress goes to stderr, the results are printed by the runner at the end
  console.error(`pyperformance: ${names.length} benchmarks for ${distDir}`);
  const results = {};
  for (const [i, name] of names.entries()) {
    const progress = `[${i + 1}/${names.length}] pyperformance/${name}`;
    const t0 = performance.now();
    let times;
    try {
      times = await runChild(distDir, depsDir, ["run", name, ...pyperfArgs]);
    } catch (e) {
      const stderr = e.stderr?.trim().split("\n").slice(-20).join("\n");
      console.error(`${progress} failed:\n${stderr ?? e}`);
      continue;
    }
    const seconds = ((performance.now() - t0) / 1000).toFixed(1);
    console.error(`${progress} (${seconds} s)`);
    for (const [caseName, time] of Object.entries(times)) {
      results[caseName] = { time };
    }
  }
  return results;
}
