import { PyodideLoader } from "./pyodide";

let loader: PyodideLoader | undefined;

export function loadPyodide() {
    if (!loader) {
      loader = new PyodideLoader();
      loader.setup();
    }
    return loader.ready;
}
