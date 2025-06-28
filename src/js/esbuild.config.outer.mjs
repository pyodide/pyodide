import { readFileSync, writeFileSync } from "node:fs";
import { config, dest } from "./esbuild.config.shared.mjs";
import { createReadStream } from "node:fs";
import { createHash } from "node:crypto";
import { build } from "esbuild";

async function hashFiles(files) {
  const hash = createHash("sha256");
  for (const file of files) {
    createReadStream(file).pipe(hash);
  }
  let result = "";
  for await (const chunk of hash.setEncoding("hex")) {
    result += chunk;
  }
  return result;
}

const extraDefines = {
  BUILD_ID: await hashFiles([
    dest("dist/pyodide.asm.js"),
    dest("dist/pyodide.asm.wasm"),
  ]),
};

const outputs = [
  {
    input: "pyodide",
    output: "dist/pyodide.mjs",
    format: "esm",
    extraDefines,
    loader: { ".wasm": "binary" },
  },
  {
    input: "pyodide.umd",
    output: "dist/pyodide.js",
    format: "iife",
    name: "loadPyodide",
    extraDefines,
    loader: { ".wasm": "binary" },
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
