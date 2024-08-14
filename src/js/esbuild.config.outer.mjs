import { readFileSync, writeFileSync } from "node:fs";
import { config, dest } from "./esbuild.config.shared.mjs";

import { build } from "esbuild";

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
];

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

    // inject webpackIgnore comments
    content = content.replaceAll("import(", "import(/* webpackIgnore */");

    writeFileSync(outfile, content);
  }
} catch ({ message }) {
  console.error(message);
}
