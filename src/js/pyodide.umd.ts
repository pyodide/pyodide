import { loadPyodide, version } from "./pyodide";
export { loadPyodide, version };
(globalThis as any).loadPyodide = loadPyodide;
