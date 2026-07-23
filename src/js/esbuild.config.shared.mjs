import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const DEBUG = !!process.env.PYODIDE_DEBUG_JS;

// According to the docs:
//
// "Sanitizers or source map is currently not supported if overriding
// WebAssembly instantiation with Module.instantiateWasm."
// https://emscripten.org/docs/api_reference/module.html?highlight=instantiatewasm#Module.instantiateWasm
//
// But this isn't apparently true anymore with sanitizers, only with
// `-gseparate-dwarf`. I think builds with DISABLE_INSTANTIATE_WASM are broken
// anyways...
// TODO: Fix.
const DISABLE_INSTANTIATE_WASM = !!process.env.PYODIDE_SOURCEMAP;

const __dirname = dirname(new URL(import.meta.url).pathname);

const makefileEnvs = readFileSync(join(__dirname, "..", "..", "Makefile.envs"), {
  encoding: "utf-8",
});

// Read a build variable, preferring the environment (exported by Makefile.envs
// when building via `make`) and falling back to parsing Makefile.envs directly
// so that the values stay correct even when esbuild is invoked on its own.
function getBuildVar(name) {
  if (process.env[name]) {
    return process.env[name];
  }
  const match = makefileEnvs.match(new RegExp(`^export ${name} \\?= (.*)$`, "m"));
  if (!match) {
    throw new Error(
      `Could not determine ${name} from the environment or Makefile.envs`,
    );
  }
  return match[1].trim();
}

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
const constants = {
  DEBUG,
  DISABLE_INSTANTIATE_WASM,
  API_VERSION: getBuildVar("PYODIDE_VERSION"),
  ABI_VERSION: getBuildVar("PYODIDE_ABI_VERSION"),
  cDefs: origConstants.defines,
};
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
    "node:net",
    "node:tls",
    "node:stream",
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
