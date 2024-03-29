import { loadPyodide } from "./pyodide.mjs";
import { writeFileSync } from "fs";

const py = await loadPyodide({ _makeSnapshot: true });
writeFileSync("snapshot.bin", py._snapshot);
