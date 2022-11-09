/* Handle dynamic library loading. */

declare var Module: any;
declare var API: any;
declare var DEBUG: boolean;

import { createLock } from "./lock";

type ReadFileType = (path: string) => Uint8Array;

// File System-like type which can be passed to
// Module.loadDynamicLibrary or Module.loadWebAssemblyModule
type LoadDynlibFS = {
  readFile: ReadFileType;
  findObject: (path: string, dontResolveLastLink: boolean) => any;
};

/**
 * Creates a filesystem-like object to be passed to Module.loadDynamicLibrary or Module.loadWebAssemblyModule
 * which helps searching for libraries
 *
 * @param lib The path to the library to load
 * @param searchDirs The list of directories to search for the library
 * @returns A filesystem-like object
 */
function createDynlibFS(lib: string, searchDirs?: string[]): LoadDynlibFS {
  searchDirs = searchDirs || [];

  const libBasename = lib.substring(0, lib.lastIndexOf("/"));
  const defaultSearchDirs = ["/usr/lib", API.sitepackages, libBasename];
  const libSearchDirs = searchDirs.concat(defaultSearchDirs);

  const resolvePath = (path: string) => {
    if (DEBUG) {
      if (Module.PATH.basename(path) !== Module.PATH.basename(lib)) {
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

  let readFile: ReadFileType = (path: string) =>
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
 * @private
 */
export async function loadDynlib(lib: string, global: boolean) {
  const releaseDynlibLock = await acquireDynlibLock();

  if (DEBUG) {
    console.debug(`Loading a dynamic library ${lib}`);
  }

  const fs = createDynlibFS(lib);

  try {
    await Module.loadDynamicLibrary(lib, {
      loadAsync: true,
      nodelete: true,
      allowUndefined: true,
      global,
      fs,
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
