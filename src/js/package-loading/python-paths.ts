/**
 * Pure-TypeScript computation of the Python filesystem paths and extension
 * (shared library) tags.
 *
 * The functions in this file is meanted to be used before the Python interpreter
 * is bootstrapped, so that packages can be installed without running any
 * Python code.
 *
 * In this file, we assume that the library is installed to /usr/lib,
 * which is not true when Pyodide runs as a CLI with `pyodide venv`.
 * However, we do not expect these functions are used in `pyodide venv` case,
 * as the packages should be pre-installed through pip not by `pyodide.loadPackage.
 *
 * @private
 */

const PLATFORM_TRIPLET = "wasm32-emscripten";
const PREFIX = "/";
const PLATLIBDIR = "lib";
const DSO_DIR = "/usr/lib";

/** @private */
export type InstallTarget = "site" | "dynlib";

/**
 * Paths related to Python package installation.
 * @private
 * */
export interface PythonPaths {
  prefix: string;
  sitePackages: string;
  dsoDir: string;
  soabi: string;
  extensionSuffixes: string[];
  extensionTags: string[];
}

/**
 * Compute the Python install paths and extension tags for a given Python
 * version.
 *
 * @param version The `[major, minor, micro]` Python version tuple.
 * Needed to compute the SOABI and extension tags.
 * @returns The computed paths and extension tags.
 * @private
 */
export function computePythonPaths(
  version: readonly [number, number, number] | readonly [number, number],
): PythonPaths {
  const [major, minor] = version;

  const sitePackages = `${PREFIX}${PLATLIBDIR}/python${major}.${minor}/site-packages`;
  const soabi = `cpython-${major}${minor}-${PLATFORM_TRIPLET}`;
  const extensionSuffixes = [`.${soabi}.so`, ".abi3.so", ".so"];
  const extensionTags = extensionSuffixes.map((suffix) =>
    suffix.endsWith(".so") ? suffix.slice(0, -".so".length) : suffix,
  );

  return {
    prefix: PREFIX,
    sitePackages,
    dsoDir: DSO_DIR,
    soabi,
    extensionSuffixes,
    extensionTags,
  };
}

/**
 * Get the install directory for a given target.
 *
 * @param paths The computed Python paths.
 * @param target The install target (`"site"` or `"dynlib"`), or undefined.
 * @returns The absolute install directory.
 * @private
 */
export function getInstallDir(
  paths: PythonPaths,
  target?: InstallTarget | string | null,
): string {
  if (target === "dynlib") {
    return paths.dsoDir;
  }
  return paths.sitePackages;
}
