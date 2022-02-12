import commonjs from "@rollup/plugin-commonjs";
import { nodeResolve } from "@rollup/plugin-node-resolve";
import { terser } from "rollup-plugin-terser";
import ts from "rollup-plugin-ts";

function config({ input, format, minify, ext = "js" }) {
  const dir = `build/`;
  // const minifierSuffix = minify ? ".min" : "";
  const minifierSuffix = "";
  return {
    input: `./src/js/${input}.ts`,
    output: {
      name: "loadPyodide",
      file: `${dir}/${input}${minifierSuffix}.${ext}`,
      format,
      sourcemap: true,
    },
    external: ["path", "fs/promises", "node-fetch", "vm"],
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
  // { input: "pyodide", format: "esm", minify: false, ext: "mjs" },
  { input: "pyodide", format: "esm", minify: true, ext: "mjs" },
  // { input: "pyodide", format: "umd", minify: false },
  { input: "pyodide", format: "umd", minify: true },
].map(config);
