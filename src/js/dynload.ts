/* Handle dynamic library loading. */

declare var Module: any;
declare var API: any;
declare var DEBUG: boolean;

import { createLock } from "./lock";
import { PackageData } from "./load-package";

type ReadFileType = (path: string) => Uint8Array;

// File System-like type which can be passed to
// Module.loadDynamicLibrary or Module.loadWebAssemblyModule
type LoadDynlibFS = {
  readFile: ReadFileType;
  findObject: (path: string, dontResolveLastLink: boolean) => any;
};

// Emscripten has a lock in the corresponding code in library_browser.js. I
// don't know why we need it, but quite possibly bad stuff will happen without
// it.
const acquireDynlibLock = createLock();

/**
 * @param fn A function to be memoized.
 * @returns
 */
const memoize = (fn: CallableFunction) => {
  let cache: any = {};
  return (...args: any) => {
    let n = args[0];
    if (n in cache) {
      return cache[n];
    } else {
      let result = fn(n);
      cache[n] = result;
      return result;
    }
  };
};

/**
 * Decide whether a library should be loaded globally or locally.
 * @param lib The path to the library to load
 * @param globalLibs A list of libraries to load globally
 * @private
 */
export function shouldLoadGlobally(
  lib: string,
  globalLibs: Set<string>,
): boolean {
  // We need to load libraries globally if they are required by other libraries
  // This is a heuristic to determine if the library is a shared library.
  // Normally a system library would start with "lib",
  // and will not contain extension suffixes like "cpython-3.10-wasm32-emscripten.so"
  // const libname = Module.PATH.basename(lib);
  // return libname.startsWith("lib") && !libname.includes(API.extension_suffix);

  const basename = Module.PATH.basename(lib);
  return globalLibs.has(basename);
}

/**
 * Given a list of libraries, return a list of libraries to load globally.
 * @param libs The list of path to libraries
 * @returns A list of libraries needed to be loaded globally
 * @private
 */
export function calculateGlobalLibs(
  libs: string[],
  readFileFunc: ReadFileType,
): Set<string> {
  let readFile: ReadFileType = Module.FS.readFile;
  if (readFileFunc !== undefined) {
    readFile = readFileFunc;
  }

  const neededLibs = new Set<string>();
  for (const lib of libs) {
    const binary = readFile(lib);
    Module.getDylinkMetadata(binary).neededDynlibs.forEach((lib: string) => {
      neededLibs.add(lib);
    });
  }

  return neededLibs;
}

/**
 * Creates a filesystem-like object to be passed to Module.loadDynamicLibrary or Module.loadWebAssemblyModule
 * which helps searching for libraries
 *
 * @param lib The path to the library to load
 * @param searchDirs The list of directories to search for the library
 * @param readFileFunc The function to read a file, if not provided, Module.FS.readFile will be used
 * @returns A filesystem-like object
 */
export function createDynlibFS(
  lib: string,
  searchDirs?: string[],
  readFileFunc?: ReadFileType,
): LoadDynlibFS {
  let libSearchDirs: string[] = searchDirs || [];

  libSearchDirs.concat(["/usr/lib", API.sitepackages]);

  const resolvePath = (path: string) => {
    if (DEBUG) {
      if (path !== lib) {
        console.debug(`Searching a library from ${path}, required by ${lib}.`);
      }
    }

    for (const dir of libSearchDirs) {
      const fullPath = Module.PATH.join2(dir, path);
      if (Module.FS.findObject(fullPath) !== null) {
        return fullPath;
      }
    }
    return path;
  };

  let readFile: (path: string) => Uint8Array;
  if (readFileFunc === undefined) {
    readFile = (path: string) => Module.FS.readFile(resolvePath(path));
  } else {
    readFile = (path: string) => readFileFunc(resolvePath(path));
  }

  const fs: LoadDynlibFS = {
    findObject: (path: string, dontResolveLastLink: boolean) => {
      let obj = Module.FS.findObject(resolvePath(path), dontResolveLastLink);
      if (DEBUG) {
        if (obj === null) {
          console.debug(`Failed to find a library: ${path}`);
        } else {
          console.debug(`Library ${path} found at ${resolvePath(path)}`);
        }
      }
      return obj;
    },
    readFile: readFile,
  };

  return fs;
}

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
    console.debug(`Loading a dynamic library ${lib}`);
  }

  const libDir = Module.PATH.dirname(lib);
  const libName = Module.PATH.basename(lib);

  let libSearchDirs = searchDirs || [];
  if (Module.PATH.isAbs(lib)) {
    libSearchDirs.unshift(libDir);
  }

  const libraryFS = createDynlibFS(lib, libSearchDirs, readFileFunc);

  try {
    // Note: Emscripten uses the value passed to Module.loadDynamicLibrary as the
    // key to store the loaded library in Module.LDSO.loadedLibsByName.
    // So in order to prevent from loading the same library twice,
    // we only pass the library name to Module.loadDynamicLibrary
    await Module.loadDynamicLibrary(libName, {
      loadAsync: true,
      nodelete: true,
      global: global,
      fs: libraryFS,
      allowUndefined: true,
    });
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
 * - We need to load libraries in the correct order.
 * - We need to load libraries globally if they are required by other libraries.
 * - We need to tell where to search for libraries.
 * - Emscripten dylink metadata only contains the library name, not the path. So we need to handle the carefully
 *   to avoid loading the same library twice.
 *
 * @param pkg The package data
 * @param dynlibPaths The list of dynamic libraries inside a package
 * @private
 */
export async function loadDynlibsFromPackage(
  pkg: PackageData,
  dynlibPaths: string[],
) {
  // assume that shared libraries of a package are located in <package-name>.libs directory,
  // following the convention of auditwheel.
  const auditWheelLibDir = `${API.sitepackages}/${
    pkg.file_name.split("-")[0]
  }.libs`;

  // This prevents from reading large libraries multiple times.
  const readFileMemoized: ReadFileType = memoize(Module.FS.readFile);

  const globalLibs: Set<string> = calculateGlobalLibs(
    dynlibPaths,
    readFileMemoized,
  );
  const dynlibs = dynlibPaths.map((path) => {
    const global = Module.PATH.basename(path) in globalLibs;
    return {
      path: path,
      global: global,
    };
  });

  // Sort libraries so that global libraries can be loaded first.
  // TODO(ryanking13): It is not clear why global libraries should be loaded first.
  //    But without this, we get a fatal error when loading the libraries.
  dynlibs.sort((lib: { global: boolean }) => (lib.global ? -1 : 1));

  for (const { path, global } of dynlibs) {
    await loadDynlib(path, global, [auditWheelLibDir]);
  }
}

API.loadDynlib = loadDynlib;
API.loadDynlibsFromPackage = loadDynlibsFromPackage;
