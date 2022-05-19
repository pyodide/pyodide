import { loadPyodide } from "./pyodide";
export { loadPyodide };
(globalThis as any).loadPyodide = loadPyodide;
