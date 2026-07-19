/**
 * @private
 */

import { basename, resolvePosix } from "./posix-path";

// Matches a `.so` extension possibly followed by version components, e.g.
// `.so`, `.so.1`, `.so.1.2`.
const SHAREDLIB_REGEX = /\.so(.\d+)*$/;

// Matches an interpreter/platform tag such as `.cpython-313-wasm32-emscripten`.
const PLATFORM_TAG_REGEX = /^\.(cpython)-[0-9]{2,}[a-z]*(-[a-z0-9_-]*)?/;

// Reimplements pathlib.PurePath.suffixes: strip leading dots, ignore a trailing
// dot, then split the remainder on "." keeping each "." prefix.
function pathSuffixes(name: string): string[] {
  if (name.endsWith(".")) {
    return [];
  }
  const stripped = name.replace(/^\.+/, "");
  const parts = stripped.split(".");
  return parts.slice(1).map((part) => "." + part);
}

/**
 * Whether a path points to a shared library compatible with this interpreter.
 *
 * @param path A path (or filename) inside a package.
 * @param extensionTags The compatible extension tags,
 * @private
 */
export function shouldLoadDynlib(
  path: string,
  extensionTags: readonly string[],
): boolean {
  const name = basename(path);
  if (!SHAREDLIB_REGEX.test(name)) {
    return false;
  }

  const suffixes = pathSuffixes(name);
  const soIndex = suffixes.indexOf(".so");
  if (soIndex === -1) {
    return false;
  }
  const tag = suffixes.at(soIndex - 1);
  if (tag === undefined) {
    return false;
  }

  if (extensionTags.includes(tag)) {
    return true;
  }
  // Best effort: an unrelated `.so` with an extra dot (e.g. `some.name.so`) is
  // fine, but a wheel built for another platform (e.g. `*.cpython-39-x86_64-
  // linux-gnu.so`) is not.
  return !PLATFORM_TAG_REGEX.test(tag);
}

/**
 * From a list of archive member paths, return the resolved paths of the shared
 * libraries that should be loaded.
 *
 * @param paths Archive member paths (as stored in the archive).
 * @param targetDir The directory the archive is unpacked into.
 * @param extensionTags The compatible extension tags,
 * @private
 */
export function getDynlibs(
  paths: readonly string[],
  targetDir: string,
  extensionTags: readonly string[],
): string[] {
  return paths
    .filter((path) => shouldLoadDynlib(path, extensionTags))
    .map((path) => resolvePosix(targetDir, path));
}
