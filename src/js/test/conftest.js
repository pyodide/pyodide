import { loadPyodide } from "../pyodide.js";
import path from "path";
globalThis.path = path;

before(async () => {
  let indexURL = process.env.PYODIDE_BASE_URL || "../../build/";
  globalThis.pyodide = await loadPyodide({ indexURL: indexURL });
});
