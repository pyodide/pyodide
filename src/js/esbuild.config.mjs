import { dirname, join } from "node:path";
import { readFileSync, writeFileSync } from "node:fs";

import { build } from "esbuild";

const DEBUG = !!process.env.PYODIDE_DEBUG_JS;

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
    output: "src/js/_pyodide.out.js",
    format: "iife",
  },
];

const dest = (output) => join(__dirname, "..", "..", output);

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
    const outfile = dest(output);

    let content = readFileSync(outfile).toString();

    const isUMD = input.endsWith(".umd");
    const hasDEBUG = /\bDEBUG\b/.test(content);

    // append the DEBUG flag if used in the output
    if (hasDEBUG) {
      content = content.replace(
        "//# sourceMappingURL",
        `const DEBUG=${DEBUG};\n//# sourceMappingURL`,
      );
    }

    // simplify the umd dance for CommonJS by trying to set info on `exports`
    if (isUMD) {
      content = content.replace(
        "//# sourceMappingURL",
        `try{Object.assign(exports,${name})}catch(_){}\nglobalThis.${name}=${name}.${name};\n//# sourceMappingURL`,
      );
    }

    if (hasDEBUG || isUMD) {
      writeFileSync(outfile, content);
    }
  }
} catch ({ message }) {
  console.error(message);
}
