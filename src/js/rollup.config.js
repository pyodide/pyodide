import { terser } from "rollup-plugin-terser";

function config({ input, format, minify, ext = "js" }) {
  const dir = `build/`;
  // const minifierSuffix = minify ? ".min" : "";
  const minifierSuffix = "";
  return {
    input: `./src/js/${input}.js`,
    output: {
      name: "loadPyodide",
      file: `${dir}/${input}${minifierSuffix}.${ext}`,
      format,
      sourcemap: true,
    },
    plugins: [
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
