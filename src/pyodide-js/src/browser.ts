import { loadPyodide } from "./index";

(self as any).languagePluginLoader = loadPyodide();
