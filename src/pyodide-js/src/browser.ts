import { loadPyodide } from "./index";

(self as any).languageLoaderPlugin = loadPyodide();
