import { loadPyodide } from "../pyodide";
import path from "path";

declare global {
  var path: path.PlatformPath;
  var pyodide: any;
}

globalThis.path = path;

before(async () => {
  globalThis.pyodide = await loadPyodide({
    indexURL: path.resolve(__dirname, "../../../", "dist"),
  });
});
