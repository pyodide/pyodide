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
