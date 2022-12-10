import commonjs from "@rollup/plugin-commonjs";
import { nodeResolve } from "@rollup/plugin-node-resolve";
import { terser } from "rollup-plugin-terser";
import ts from "rollup-plugin-ts";

const DEBUG = !!process.env.PYODIDE_DEBUG_JS;

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
            compress: {
              defaults: !DEBUG,
              dead_code: true,
              global_defs: {
                DEBUG,
              },
            },
            mangle: false,
            format: {
              beautify: DEBUG,
              comments: /^\s*webpackIgnore/,
            },
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
