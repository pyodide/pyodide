// A published pyodide package version is used as a placeholder and
// the contents are replaced with the local build before running.
// See README.md for details
import pyodideModule from "npm:pyodide@0.23.1/pyodide.js";
const { loadPyodide } = pyodideModule;

console.time("[load pyodide]");
const pyodide = await loadPyodide();
console.timeEnd("[load pyodide]");

console.time("[run pyodide]");
const result = await pyodide.runPythonAsync(`
3+4
`);
console.timeEnd("[run pyodide]");

console.log("result:", result.toString());
