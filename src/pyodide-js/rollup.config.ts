import typescript from 'rollup-plugin-typescript2';
import replace from '@rollup/plugin-replace';

const pkg = require("./package.json");

const pyodideCdnUrl = process.env["PYODIDE_CDN_URL"] || `https://cdn.jsdelivr.net/pyodide/${pkg.version}/full/`;
const pyodideAbiNumber = process.env["PYODIDE_PACKAGE_ABI"] === undefined ? `1` : process.env["PYODIDE_PACKAGE_ABI"];

const plugins = [
    typescript(),
    replace({
        "__PYODIDE_CDN_URL__": pyodideCdnUrl,
        "__PYODIDE_PACKAGE_ABI__": pyodideAbiNumber
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