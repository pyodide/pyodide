// Runner for Pyodide benchmarks in Node.js.
//
// Usage:
//   node benchmark/node/run.mjs [options] [DIST]
//     Print absolute timings for one build (default: dist).
//   node benchmark/node/run.mjs [options] BASE NEW
//     Compare two builds. The ratio column is NEW time / BASE time, so
//     values below 1 mean NEW is faster.
//
// DIST / BASE / NEW are dist directories or URLs of a Pyodide distribution
// (e.g. https://cdn.jsdelivr.net/pyodide/dev/full/). For URLs, the core files
// are downloaded into a temporary directory.
//
// Options:
//   --suite NAME    Only run the given suite (can be repeated).
//   --filter REGEX  Only run cases whose "suite/case" name matches REGEX.
//   --rounds N      Run each suite N times per build (default: 1),
//                   and report the median over the rounds.
//   --json FILE     Also write the results to FILE as JSON.
//   --list          List the available suites and exit.
//
// Each suite is a module in ./suites/ and is run in a fresh Node process for
// each build, so that JIT state from one suite or build cannot affect another.
// A suite module exports:
//
//   export const description = "...";   // shown by --list
//   export async function run(pyodide, ctx) {
//     // ctx.filter(caseName) -> whether the case was selected by --filter
//     // await ctx.measure(fn) -> median time of fn() in ms (fn may be async)
//     return { [caseName]: { [metricName]: ms, ... }, ... };
//   }
//
// A suite should throw if it detects incorrect results; the runner then exits
// with a non-zero status.

import { spawn } from "node:child_process";
import { mkdtemp, readdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const SUITES_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "suites",
);
const WARMUP = 2;
const REPEATS = 7;

const CORE_FILES = [
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
];

function median(xs) {
  const s = [...xs].sort((a, b) => a - b);
  return s[s.length >> 1];
}

async function measure(fn) {
  const call = async () => {
    const result = fn();
    if (result && typeof result.then === "function") {
      await result;
    }
  };
  for (let i = 0; i < WARMUP; i++) {
    await call();
  }
  const samples = [];
  for (let i = 0; i < REPEATS; i++) {
    const t0 = performance.now();
    await call();
    samples.push(performance.now() - t0);
  }
  return median(samples);
}

// Runs a single suite against a single build, in this process.
async function runWorker(suiteName, distDir, filter, outFile) {
  const suite = await import(
    pathToFileURL(path.join(SUITES_DIR, `${suiteName}.mjs`)).href
  );
  const { loadPyodide } = await import(
    pathToFileURL(path.join(distDir, "pyodide.mjs")).href
  );
  const pyodide = await loadPyodide({ indexURL: distDir + "/" });
  const regex = filter ? new RegExp(filter) : null;
  const ctx = {
    filter: (caseName) => !regex || regex.test(`${suiteName}/${caseName}`),
    measure,
  };
  const results = await suite.run(pyodide, ctx);
  await writeFile(outFile, JSON.stringify(results));
}

async function resolveDist(dist) {
  if (!/^https?:\/\//.test(dist)) {
    return path.resolve(dist);
  }
  const base = dist.endsWith("/") ? dist : dist + "/";
  const dir = await mkdtemp(path.join(os.tmpdir(), "pyodide-bench-"));
  for (const file of CORE_FILES) {
    const resp = await fetch(base + file);
    if (!resp.ok) {
      throw new Error(`Failed to download ${base + file}: ${resp.status}`);
    }
    await writeFile(
      path.join(dir, file),
      Buffer.from(await resp.arrayBuffer()),
    );
  }
  return dir;
}

async function listSuites() {
  return (await readdir(SUITES_DIR))
    .filter((f) => f.endsWith(".mjs"))
    .map((f) => f.slice(0, -".mjs".length))
    .sort();
}

async function runInChild(suiteName, distDir, filter) {
  const outFile = path.join(
    await mkdtemp(path.join(os.tmpdir(), "pyodide-bench-out-")),
    "results.json",
  );
  const args = [
    fileURLToPath(import.meta.url),
    "--worker",
    suiteName,
    "--out",
    outFile,
  ];
  if (filter) {
    args.push("--filter", filter);
  }
  args.push(distDir);
  const code = await new Promise((resolve, reject) => {
    spawn(process.execPath, args, { stdio: "inherit" })
      .on("error", reject)
      .on("exit", resolve);
  });
  if (code !== 0) {
    throw new Error(
      `Suite ${suiteName} failed for ${distDir} (exit code ${code})`,
    );
  }
  return JSON.parse(await readFile(outFile, "utf8"));
}

// Combine the results of several rounds by taking the median of each metric.
function medianOfRounds(roundResults) {
  const combined = {};
  for (const caseName of Object.keys(roundResults[0])) {
    combined[caseName] = {};
    for (const metric of Object.keys(roundResults[0][caseName])) {
      combined[caseName][metric] = median(
        roundResults.map((r) => r[caseName][metric]),
      );
    }
  }
  return combined;
}

function printSuite(suiteName, labels, perDist) {
  const fmt = (x) => (x === undefined ? "-" : x.toFixed(2)).padStart(14);
  const caseNames = Object.keys(perDist[0]);
  if (caseNames.length === 0) {
    return;
  }
  const metrics = [
    ...new Set(caseNames.flatMap((c) => Object.keys(perDist[0][c]))),
  ];
  const width = Math.max(14, ...caseNames.map((c) => c.length + 2));
  console.log(`\n## ${suiteName} (ms)`);
  const header = ["case".padEnd(width)];
  for (const label of labels) {
    for (const m of metrics) {
      header.push(`${label} ${m}`.padStart(14));
    }
  }
  if (perDist.length === 2) {
    for (const m of metrics) {
      header.push(`${m} ratio`.padStart(14));
    }
  }
  console.log(header.join(""));
  for (const c of caseNames) {
    const row = [c.padEnd(width)];
    for (const r of perDist) {
      for (const m of metrics) {
        row.push(fmt(r[c]?.[m]));
      }
    }
    if (perDist.length === 2) {
      for (const m of metrics) {
        const base = perDist[0][c]?.[m];
        const cur = perDist[1][c]?.[m];
        row.push(
          fmt(base !== undefined && cur !== undefined ? cur / base : undefined),
        );
      }
    }
    console.log(row.join(""));
  }
}

async function main() {
  const { values: opts, positionals } = parseArgs({
    options: {
      suite: { type: "string", multiple: true },
      filter: { type: "string" },
      json: { type: "string" },
      rounds: { type: "string", default: "1" },
      list: { type: "boolean" },
      worker: { type: "string" },
      out: { type: "string" },
    },
    allowPositionals: true,
  });

  if (opts.worker) {
    await runWorker(opts.worker, positionals[0], opts.filter, opts.out);
    return;
  }

  const available = await listSuites();
  if (opts.list) {
    for (const name of available) {
      const suite = await import(
        pathToFileURL(path.join(SUITES_DIR, `${name}.mjs`)).href
      );
      console.log(`${name}: ${suite.description ?? ""}`);
    }
    return;
  }

  const suites = opts.suite ?? available;
  for (const name of suites) {
    if (!available.includes(name)) {
      throw new Error(
        `Unknown suite ${name}. Available: ${available.join(", ")}`,
      );
    }
  }
  const dists = positionals.length > 0 ? positionals : ["dist"];
  if (dists.length > 2) {
    throw new Error("Expected at most two dists (BASE and NEW)");
  }
  const labels = dists.length === 2 ? ["base", "new"] : ["dist"];
  const distDirs = [];
  for (const d of dists) {
    distDirs.push(await resolveDist(d));
  }

  const rounds = Number(opts.rounds);
  if (!Number.isInteger(rounds) || rounds < 1) {
    throw new Error(`--rounds must be a positive integer, got ${opts.rounds}`);
  }

  const results = Object.fromEntries(labels.map((l) => [l, {}]));
  for (const suiteName of suites) {
    // perRound[i][r] is the result of round r for build i
    const perRound = labels.map(() => []);
    for (let r = 0; r < rounds; r++) {
      for (let i = 0; i < dists.length; i++) {
        perRound[i].push(await runInChild(suiteName, distDirs[i], opts.filter));
      }
    }
    for (let i = 0; i < dists.length; i++) {
      results[labels[i]][suiteName] = medianOfRounds(perRound[i]);
    }
  }

  for (let i = 0; i < dists.length; i++) {
    console.log(`${labels[i]}: ${dists[i]}`);
  }
  console.log(
    `Times are medians of ${REPEATS} repeats` +
      (rounds > 1 ? `, then the median over ${rounds} rounds` : ""),
  );
  for (const suiteName of suites) {
    printSuite(
      suiteName,
      labels,
      labels.map((l) => results[l][suiteName]),
    );
  }

  if (opts.json) {
    const output = {
      unit: "ms",
      repeats: REPEATS,
      rounds,
      dists: Object.fromEntries(labels.map((l, i) => [l, dists[i]])),
      results,
    };
    await writeFile(opts.json, JSON.stringify(output, null, 2) + "\n");
  }
}

await main();
