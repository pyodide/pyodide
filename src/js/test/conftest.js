import { loadPyodide } from "../pyodide.js";
import path from "path";
globalThis.path = path;

before(async () => {
  globalThis.pyodide = await loadPyodide();
});
