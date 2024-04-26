/* Handle dynamic library loading. */

declare var DEBUG: boolean;

import { createLock } from "./lock";
import { memoize } from "./pyodide-util";
import { InternalPackageData } from "./load-package";
import { LoadDynlibFS, ReadFileType } from "./types";

// File System-like type which can be passed to
// Module.loadDynamicLibrary or Module.loadWebAssemblyModule

/**
 * Creates a filesystem-like object to be passed to Module.loadDynamicLibrary or Module.loadWebAssemblyModule
 * which helps searching for libraries
 *
 * @param lib The path to the library to load
 * @param searchDirs The list of directories to search for the library
 * @param readFileFunc The function to read a file, if not provided, Module.FS.readFile will be used
 * @returns A filesystem-like object
 * @private
 */
function createDynlibFS(
  lib: string,
  searchDirs?: string[],
  readFileFunc?: ReadFileType,
): LoadDynlibFS {
  const dirname = lib.substring(0, lib.lastIndexOf("/"));

  let _searchDirs = searchDirs || [];
  _searchDirs = _searchDirs.concat(API.defaultLdLibraryPath, [dirname]);

  const resolvePath = (path: string) => {
    if (DEBUG) {
      if (Module.PATH.basename(path) !== Module.PATH.basename(lib)) {
        console.debug(`Searching a library from ${path}, required by ${lib}.`);
      }
    }

    for (const dir of _searchDirs) {
      const fullPath = Module.PATH.join2(dir, path);
      if (Module.FS.findObject(fullPath) !== null) {
        return fullPath;
      }
    }
    return path;
  };

  let readFile: ReadFileType = (path: string) =>
    Module.FS.readFile(resolvePath(path));
  if (readFileFunc !== undefined) {
    readFile = (path: string) => readFileFunc(resolvePath(path));
  }

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
 * @param readFileFunc The function to read a file, if not provided, Module.FS.readFile will be used
 * @private
 */
export async function loadDynlib(
  lib: string,
  global: boolean,
  searchDirs?: string[],
  readFileFunc?: ReadFileType,
) {
  const releaseDynlibLock = await acquireDynlibLock();

  if (DEBUG) {
    console.debug(`Loading a dynamic library ${lib} (global: ${global})`);
  }

  const fs = createDynlibFS(lib, searchDirs, readFileFunc);

  try {
    await Module.loadDynamicLibrary(lib, {
      loadAsync: true,
      nodelete: true,
      allowUndefined: true,
      global,
      fs,
    });

    // Emscripten saves the list of loaded libraries in LDSO.loadedLibsByName.
    // However, since emscripten dylink metadata only contains the name of the
    // library not the full path, we need to update it manually in order to
    // prevent loading same library twice.
    if (global && Module.PATH.isAbs(lib)) {
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

  // This prevents from reading large libraries multiple times.
  const readFileMemoized: ReadFileType = memoize(Module.FS.readFile);

  const forceGlobal: boolean = !!pkg.shared_library;

  type Dynlib = { path: string; global: boolean };
  let dynlibs: Dynlib[];

  if (forceGlobal) {
    dynlibs = dynlibPaths.map((path) => {
      return {
        path: path,
        global: true,
      };
    });
  } else {
    const globalLibs: Set<string> = calculateGlobalLibs(
      dynlibPaths,
      readFileMemoized,
    );

    dynlibs = dynlibPaths.map((path) => {
      const global = globalLibs.has(Module.PATH.basename(path));
      return {
        path: path,
        global: global || !!pkg.shared_library,
      };
    });
  }

  // Sort libraries so that global libraries can be loaded first.
  // TODO(ryanking13): It is not clear why global libraries should be loaded first.
  //    But without this, we get a fatal error when loading the libraries.
  type T = { global: boolean };
  dynlibs.sort((lib1: T, lib2: T) => Number(lib2.global) - Number(lib1.global));

  for (const { path, global } of dynlibs) {
    await loadDynlib(path, global, [auditWheelLibDir], readFileMemoized);
  }
}

/**
 * Given a list of libraries, return a list of libraries to load globally.
 * @param libs The list of path to libraries
 * @param readFileFunc A function to read the file, if not provided, use Module.FS.readFile
 * @returns A list of libraries needed to be loaded globally
 * @private
 */
function calculateGlobalLibs(
  libs: string[],
  readFileFunc?: ReadFileType,
): Set<string> {
  let readFile: ReadFileType = Module.FS.readFile;
  if (readFileFunc !== undefined) {
    readFile = readFileFunc;
  }

  const globalLibs = new Set<string>();

  libs.forEach((lib: string) => {
    const binary = readFile(lib);
    const needed = Module.getDylinkMetadata(binary).neededDynlibs;
    needed.forEach((lib: string) => {
      globalLibs.add(lib);
    });
  });

  return globalLibs;
}

API.loadDynlib = loadDynlib;
API.loadDynlibsFromPackage = loadDynlibsFromPackage;
