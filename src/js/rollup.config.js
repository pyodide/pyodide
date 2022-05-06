import commonjs from "@rollup/plugin-commonjs";
import { nodeResolve } from "@rollup/plugin-node-resolve";
import { terser } from "rollup-plugin-terser";
import ts from "rollup-plugin-ts";

function config({ input, output, name, format, minify }) {
  return {
    input: `./src/js/${input}.ts`,
    output: {
      file: output,
      name,
      format,
      sourcemap: true,
    },
    external: [
      "path",
      "fs/promises",
      "node-fetch",
      "vm",
      "fs",
      "crypto",
      "ws",
      "child_process",
    ],
    plugins: [
      commonjs(),
      ts({
        tsconfig: "src/js/tsconfig.json",
      }),
      // The nodeResolve plugin allows us to import packages from node_modules.
      // We need to include node-only packages in `external` to ensure they
      // aren't bundled for use in browser.
      nodeResolve(),
      minify
        ? terser({
            compress: true,
            mangle: false,
          })
        : undefined,
    ].filter(Boolean),
  };
}

export default [
  {
    input: "pyodide",
    output: "dist/pyodide.mjs",
    format: "esm",
    minify: true,
  },
  {
    input: "pyodide.umd",
    output: "dist/pyodide.js",
    format: "umd",
    name: "loadPyodide",
    minify: true,
  },
  {
    input: "api",
    output: "src/js/_pyodide.out.js",
    format: "iife",
    minify: true,
  },
].map(config);
