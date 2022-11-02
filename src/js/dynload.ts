/* Handle dynamic library loading. */

declare var Module: any;
declare var API: any;
declare var DEBUG: boolean;

import { createLock } from "./lock";

// Emscripten has a lock in the corresponding code in library_browser.js. I
// don't know why we need it, but quite possibly bad stuff will happen without
// it.
const acquireDynlibLock = createLock();

/**
 * Decide whether a library should be loaded globally or locally.
 * @param lib The path to the library to load
 * @private
 */
function shouldLoadGlobally(lib: string, neededLibs: Set<string>): boolean {
  // We need to load libraries globally if they are required by other libraries
  // This is a heuristic to determine if the library is a shared library.
  // Normally a system library would start with "lib",
  // and will not contain extension suffixes like "cpython-3.10-wasm32-emscripten.so"
  // const libname = Module.PATH.basename(lib);
  // return libname.startsWith("lib") && !libname.includes(API.extension_suffix);

  const basename = Module.PATH.basename(lib);
  return neededLibs.has(basename);
}

/**
 * Calculate which libraries are dependencies of other libraries.
 * @param libs The list of path to libraries
 * @private
 */
function calculateNeededLibs(libs: string[]): Set<string> {
  // Note: For scipy which contains 111 shared libraries,
  //       This function took around ~150ms.
  // TODO: We are reading a library twice here and inside loadDynamicLibrary().
  //      Finding a way to read a file only once would avoid the extra
  //      overhead.
  const neededLibs = new Set<string>();
  for (const lib of libs) {
    const binary = Module.FS.readFile(lib);
    Module.getDylinkMetadata(binary).neededDynlibs.forEach((lib: string) => {
      neededLibs.add(lib);
    });
  }

  return neededLibs;
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
 * @private
 */
export async function loadDynlib(
  lib: string,
  global: boolean,
  searchDirs: string[],
) {
  const releaseDynlibLock = await acquireDynlibLock();

  searchDirs = searchDirs || [];
  searchDirs = searchDirs.concat(["/usr/lib", API.sitepackages]);

  if (DEBUG) {
    console.debug(`Loading a dynamic library ${lib}`);
  }

  // This is a fake FS-like object to make emscripten
  // load shared libraries from the file system.
  const libraryFS = {
    _resolvePath: (path: string) => {
      if (DEBUG) {
        if (path !== lib) {
          console.debug(
            `Searching a library from ${path}, required by ${lib}.`,
          );
        }
      }

      for (const dir of searchDirs) {
        const fullPath = Module.PATH.join2(dir, path);
        if (Module.FS.findObject(fullPath) !== null) {
          return fullPath;
        }
      }
      return path;
    },
    findObject: (path: string, dontResolveLastLink: boolean) => {
      let obj = Module.FS.findObject(
        libraryFS._resolvePath(path),
        dontResolveLastLink,
      );
      if (DEBUG) {
        if (obj === null) {
          console.debug(`Failed to find a library: ${path}`);
        } else {
          console.debug(
            `Library ${path} found at ${libraryFS._resolvePath(path)}`,
          );
        }
      }
      return obj;
    },
    readFile: (path: string) =>
      Module.FS.readFile(libraryFS._resolvePath(path)),
  };

  try {
    await Module.loadDynamicLibrary(lib, {
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

API.loadDynlib = loadDynlib;
