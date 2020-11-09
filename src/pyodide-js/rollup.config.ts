import typescript from 'rollup-plugin-typescript2';
import replace from '@rollup/plugin-replace';

// @ts-ignore
const pkg = require("./package.json");

const pyodideCdnUrl = `https://cdn.jsdelivr.net/pyodide/${pkg.version}/full/`;
const plugins = [
    typescript(),
    replace({"__PYODIDE_CDN_URL__": pyodideCdnUrl})
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