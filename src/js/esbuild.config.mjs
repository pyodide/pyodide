import { dirname, join } from "node:path";
import { readFileSync, writeFileSync } from "node:fs";

import { build } from "esbuild";

const DEBUG = !!process.env.PYODIDE_DEBUG_JS;
const SOURCEMAP = !!(
  process.env.PYODIDE_SOURCEMAP || process.env.PYODIDE_SYMBOLS
);

const __dirname = dirname(new URL(import.meta.url).pathname);

const outputs = [
  {
    input: "pyodide",
    output: "dist/pyodide.mjs",
    format: "esm",
  },
  {
    input: "pyodide.umd",
    output: "dist/pyodide.js",
    format: "iife",
    name: "loadPyodide",
  },
  {
    input: "api",
    output: "src/js/generated/_pyodide.out.js",
    format: "iife",
  },
];

const dest = (output) => join(__dirname, "..", "..", output);

function toDefines(o, path = "") {
  return Object.entries(o).flatMap(([x, v]) => {
    // Drop anything that's not a valid identifier
    if (!/^[A-Za-z_$]*$/.test(x)) {
      return [];
    }
    // Flatten objects
    if (typeof v === "object") {
      return toDefines(v, path + x + ".");
    }
    // Else convert to string
    return [[path + x, v.toString()]];
  });
}

const cdefsFile = join(__dirname, "generated_struct_info32.json");
const origConstants = JSON.parse(readFileSync(cdefsFile));
const constants = { DEBUG, SOURCEMAP, cDefs: origConstants.defines };
const DEFINES = Object.fromEntries(toDefines(constants));

const config = ({ input, output, format, name: globalName }) => ({
  entryPoints: [join(__dirname, input + ".ts")],
  outfile: dest(output),
  external: [
    "child_process",
    "crypto",
    "fs",
    "fs/promises",
    "node-fetch",
    "path",
    "tty",
    "url",
    "vm",
    "ws",
  ],
  define: DEFINES,
  minify: !DEBUG,
  keepNames: true,
  sourcemap: true,
  bundle: true,
  format,
  globalName,
});

const builds = [];
for (const output of outputs) {
  builds.push(build(config(output)));
}

try {
  await Promise.all(builds);
  for (const { input, name, output } of outputs) {
    if (!input.endsWith(".umd")) {
      continue;
    }
    const outfile = dest(output);
    let content = readFileSync(outfile, { encoding: "utf-8" });

    // simplify the umd dance for CommonJS by trying to set info on `exports`
    content = content.replace(
      "//# sourceMappingURL",
      `try{Object.assign(exports,${name})}catch(_){}\nglobalThis.${name}=${name}.${name};\n//# sourceMappingURL`,
    );

    writeFileSync(outfile, content);
  }
} catch ({ message }) {
  console.error(message);
}
