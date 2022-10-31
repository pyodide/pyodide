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
 * Load a dynamic library. This is an async operation and Python imports are
 * synchronous so we have to do it ahead of time. When we add more support for
 * synchronous I/O, we could consider doing this later as a part of a Python
 * import hook.
 *
 * @param lib The file system path to the library.
 * @param shared Is this a shared library or not?
 * @private
 */
export async function loadDynlib(lib: string, shared: boolean) {
  const releaseDynlibLock = await acquireDynlibLock();
  const loadGlobally = shared;

  if (DEBUG) {
    console.debug(`Loading a dynamic library ${lib}`);
  }

  // This is a fake FS-like object to make emscripten
  // load shared libraries from the file system.
  const libraryFS = {
    _ldLibraryPaths: ["/usr/lib", API.sitepackages],
    _resolvePath: (path: string) => {
      if (DEBUG) {
        console.debug(`Searching a library from ${path}, required by ${lib}.`);
      }

      if (Module.PATH.isAbs(path)) {
        if (Module.FS.findObject(path) !== null) {
          return path;
        }

        // If the path is absolute but doesn't exist, we try to find it from
        // the library paths.
        path = path.substring(path.lastIndexOf("/") + 1);
      }

      for (const dir of libraryFS._ldLibraryPaths) {
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
        console.log(`Library ${path} found at ${obj}`);
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
      global: loadGlobally,
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
