import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const DEBUG = !!process.env.PYODIDE_DEBUG_JS;
const SOURCEMAP = !!(
  process.env.PYODIDE_SOURCEMAP || process.env.PYODIDE_SYMBOLS
);

const __dirname = dirname(new URL(import.meta.url).pathname);

function toDefines(o, path = "") {
  return Object.entries(o).flatMap(([x, v]) => {
    // Drop anything that's not a valid identifier
    if (!/^[A-Za-z_$]*$/.test(x)) {
      return [];
    }
    // Flatten objects
    if (typeof v === "object") {
      return toDefines(v, path + x + ".");
    }
    if (typeof v === "string" && !v.startsWith('"')) {
      return [[path + x, `"${v}"`]];
    }
    // Else convert to string
    return [[path + x, v.toString()]];
  });
}

const cdefsFile = join(__dirname, "struct_info_generated.json");
const origConstants = JSON.parse(readFileSync(cdefsFile));
const constants = { DEBUG, SOURCEMAP, cDefs: origConstants.defines };
const DEFINES = Object.fromEntries(toDefines(constants));

export const dest = (output) => join(__dirname, "..", "..", output);
export const config = ({
  input,
  output,
  format,
  name: globalName,
  extraDefines,
  loader,
}) => ({
  entryPoints: [join(__dirname, input + ".ts")],
  outfile: dest(output),
  external: [
    "node:child_process",
    "node:crypto",
    "node:fs",
    "node:fs/promises",
    "node:path",
    "node:tty",
    "node:url",
    "node:vm",
    "ws",
  ],
  define: { ...DEFINES, ...Object.fromEntries(toDefines(extraDefines ?? {})) },
  minify: !DEBUG,
  keepNames: true,
  sourcemap: true,
  bundle: true,
  format,
  globalName,
  loader,
});
