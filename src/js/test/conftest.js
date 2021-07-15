import { loadPyodide } from "../pyodide.js";
import path from "path";
globalThis.path = path;

// arrow functions don't bind their own `this`, so we use a regular function.
before(async function () {
  this.timeout(20000);
  globalThis.pyodide = await loadPyodide({ indexURL: "../../build/" });
});
