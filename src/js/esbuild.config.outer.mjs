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
    input: "pyodide",
    output: "dist/pyodide.cjs",
    format: "cjs",
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
} catch ({ message }) {
  console.error(message);
}
