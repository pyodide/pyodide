import { loadPyodide } from "../dist/pyodide.js";

console.log("Start!");
const py = await loadPyodide();
console.log("Loaded");
py.runPython("print('hello!')");
print(py.runPython("import random; random.random()"));
console.log("Done...");
