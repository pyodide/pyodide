import { loadPyodide } from "./pyodide.js";
import { writeFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const py = await loadPyodide({ _makeSnapshot: true });
writeFileSync(__dirname + "/snapshot.bin", py.makeMemorySnapshot());
