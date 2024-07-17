import { loadPyodide } from "pyodide";

console.time("[load pyodide]");
const pyodide = await loadPyodide();
console.timeEnd("[load pyodide]");

console.time("[run pyodide]");
const result = await pyodide.runPythonAsync(`
3+4
`);
console.timeEnd("[run pyodide]");

console.log("result:", result.toString());
