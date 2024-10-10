/* Handle dynamic library loading. */

declare var DEBUG: boolean;

import { createLock } from "./common/lock";
import { LoadDynlibFS, ReadFileType, InternalPackageData } from "./types";

/**
 * Recursively get all subdirectories of a directory
 *
 * @param dir The absolute path to the directory
 * @returns A list of absolute paths to the subdirectories
 * @private
 */
function* getSubDirs(dir: string): Generator<string> {
  const dirs = Module.FS.readdir(dir);

  for (const d of dirs) {
    if (d === "." || d === "..") {
      continue;
    }

    const subdir: string = Module.PATH.join2(dir, d);
    const lookup = Module.FS.lookupPath(subdir);
    if (lookup.node === null) {
      continue;
    }

    const mode = lookup.node.mode;
    if (!Module.FS.isDir(mode)) {
      continue;
    }

    yield subdir;
    yield* getSubDirs(subdir);
  }
}

/**
 * Creates a filesystem-like object to be passed to Module.loadDynamicLibrary or Module.loadWebAssemblyModule
 * which helps searching for libraries
 *
 * @param lib The path to the library to load
 * @param searchDirs The list of directories to search for the library
 * @returns A filesystem-like object
 * @private
 */
function createDynlibFS(lib: string, searchDirs?: string[]): LoadDynlibFS {
  const dirname = lib.substring(0, lib.lastIndexOf("/"));

  let _searchDirs = searchDirs || [];
  _searchDirs = _searchDirs.concat(API.defaultLdLibraryPath, [dirname]);

  // TODO: add rpath to Emscripten dsos and remove this logic
  const resolvePath = (path: string) => {
    if (DEBUG) {
      if (Module.PATH.basename(path) !== Module.PATH.basename(lib)) {
        console.debug(`Searching a library from ${path}, required by ${lib}.`);
      }
    }

    // If the path is absolute, we don't need to search for it.
    if (Module.PATH.isAbs(path)) {
      return path;
    }

    // Step 1) Try to find the library in the search directories
    for (const dir of _searchDirs) {
      const fullPath = Module.PATH.join2(dir, path);

      if (Module.FS.findObject(fullPath) !== null) {
        return fullPath;
      }
    }

    // Step 2) try to find the library by searching child directories of the library directory
    //         (This should not be necessary in most cases, but some libraries have dependencies in the child directories)
    for (const childDir of getSubDirs(dirname)) {
      const fullPath = Module.PATH.join2(childDir, path);
      if (Module.FS.findObject(fullPath) !== null) {
        return fullPath;
      }
    }

    return path;
  };

  const readFile: ReadFileType = (path: string) =>
    Module.FS.readFile(resolvePath(path));

  const fs: LoadDynlibFS = {
    findObject: (path: string, dontResolveLastLink: boolean) => {
      let obj = Module.FS.findObject(resolvePath(path), dontResolveLastLink);
      if (DEBUG) {
        if (obj === null) {
          console.debug(`Failed to find a library: ${resolvePath(path)}`);
        }
      }
      return obj;
    },
    readFile: readFile,
  };

  return fs;
}

// Emscripten has a lock in the corresponding code in library_browser.js. I
// don't know why we need it, but quite possibly bad stuff will happen without
// it.
const acquireDynlibLock = createLock();

/**
 * Load a dynamic library. This is an async operation and Python imports are
 * synchronous so we have to do it ahead of time. When we add more support for
 * synchronous I/O, we could consider doing this later as a part of a Python
 * import hook.
 *
 * @param lib The file system path to the library.
 * @param global Whether to make the symbols available globally.
 * @param searchDirs Directories to search for the library.
 * @private
 */
export async function loadDynlib(
  lib: string,
  global: boolean,
  searchDirs?: string[],
) {
  const releaseDynlibLock = await acquireDynlibLock();

  if (DEBUG) {
    console.debug(`Loading a dynamic library ${lib} (global: ${global})`);
  }

  const fs = createDynlibFS(lib, searchDirs);
  const localScope = global ? null : {};

  try {
    await Module.loadDynamicLibrary(
      lib,
      {
        loadAsync: true,
        nodelete: true,
        allowUndefined: true,
        global,
        fs,
      },
      localScope,
    );

    // Emscripten saves the list of loaded libraries in LDSO.loadedLibsByName.
    // However, since emscripten dylink metadata only contains the name of the
    // library not the full path, we need to update it manually in order to
    // prevent loading same library twice.
    if (Module.PATH.isAbs(lib)) {
      const libName: string = Module.PATH.basename(lib);
      const dso: any = Module.LDSO.loadedLibsByName[libName];
      if (!dso) {
        Module.LDSO.loadedLibsByName[libName] =
          Module.LDSO.loadedLibsByName[lib];
      }
    }
  } catch (e: any) {
    if (e && e.message && e.message.includes("need to see wasm magic number")) {
      console.warn(
        `Failed to load dynlib ${lib}. We probably just tried to load a linux .so file or something.`,
      );
      return;
    }
    throw e;
  } finally {
    releaseDynlibLock();
  }
}

/**
 * Load dynamic libraries inside a package.
 *
 * This function handles some painful details of loading dynamic libraries:
 * - We need to load libraries in the correct order considering dependencies.
 * - We need to load libraries globally if they are required by other libraries.
 * - We need to tell Emscripten where to search for libraries.
 * - The dynlib metadata inside a wasm module only contains the library name, not the path.
 *   So we need to handle them carefully to avoid loading the same library twice.
 *
 * @param pkg The package metadata
 * @param dynlibPaths The list of dynamic libraries inside a package
 * @private
 */
export async function loadDynlibsFromPackage(
  pkg: InternalPackageData,
  dynlibPaths: string[],
) {
  // assume that shared libraries of a package are located in <package-name>.libs directory,
  // following the convention of auditwheel.
  const auditWheelLibDir = `${API.sitepackages}/${
    pkg.file_name.split("-")[0]
  }.libs`;

  for (const path of dynlibPaths) {
    await loadDynlib(path, false, [auditWheelLibDir]);
  }
}

if (typeof API !== "undefined") {
  API.loadDynlib = loadDynlib;
  API.loadDynlibsFromPackage = loadDynlibsFromPackage;
}
