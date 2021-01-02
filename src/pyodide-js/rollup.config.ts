import typescript from 'rollup-plugin-typescript2';
import replace from '@rollup/plugin-replace';

const pkg = require("./package.json");

const pyodideBaseUrl = process.env["PYODIDE_BASE_URL"] || `https://cdn.jsdelivr.net/pyodide/${pkg.version}/full/`;

const plugins = [
    typescript(),
    replace({
        "__PYODIDE_BASE_URL__": pyodideBaseUrl,
    })
]


export default [
{
  input: `src/index.ts`,
  output: [
    {file: 'dist/index.mjs', format: 'es'},
    {file: 'dist/index.cjs', format: 'commonjs'},
  ],
  plugins
},
{
    input: `src/browser.ts`,
    output: [
      {file: 'dist/browser.js', format: 'iife'},
    ],
    plugins
},
{
    input: `src/webworker.ts`,
    output: [
      {file: 'dist/webworker.js', format: 'iife'},
    ],
    plugins
}
]
;
