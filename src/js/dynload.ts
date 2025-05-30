/* Handle dynamic library loading. */

import { PackageManagerAPI, PackageManagerModule } from "./types";

import { createLock } from "./common/lock";
import { createResolvable, ResolvablePromise } from "./common/resolveable";

/** Dynamic linking flags */
const RTLD_LAZY = 1; // Lazy symbol resolution
const RTLD_NOW = 2; // Immediate symbol resolution
const RTLD_NOLOAD = 4; // Don't load library
const RTLD_NODELETE = 4096; // Symbols persist for the lifetime of the process
const RTLD_GLOBAL = 256; // Symbols made available to subsequently loaded libraries
const RTLD_LOCAL = 0; // Symbols not made available to other libraries

/** @hidden */
export class DynlibLoader {
  #api: PackageManagerAPI;
  #module: PackageManagerModule;

  // Emscripten has a lock in the corresponding code in library_browser.js. I
  // don't know why we need it, but quite possibly bad stuff will happen without
  // it.
  private _lock = createLock();

  constructor(api: PackageManagerAPI, pyodideModule: PackageManagerModule) {
    this.#api = api;
    this.#module = pyodideModule;
  }

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
  public async loadDynlib(lib: string, global: boolean) {
    const releaseDynlibLock = await this._lock();

    DEBUG &&
      console.debug(`Loading a dynamic library ${lib} (global: ${global})`);

    let flags = RTLD_NOW;
    if (global) {
      flags |= RTLD_GLOBAL;
    } else {
      flags |= RTLD_LOCAL;
    }

    try {
      const libUTF8 = this.#module.stringToNewUTF8(lib);

      try {
        Module.pyodidePromiseLibraryLoading = createResolvable();
        this.#module._emscripten_dlopen_wrapper(libUTF8, flags);
        await Module.pyodidePromiseLibraryLoading;
      } catch (e: any) {
        console.error(`Failed to load dynamic library ${lib}:`, e);
      } finally {
        Module.pyodidePromiseLibraryLoading = undefined;
      }
    } catch (e: any) {
      if (
        e &&
        e.message &&
        e.message.includes("need to see wasm magic number")
      ) {
        console.warn(
          `Failed to load dynlib ${lib}. We probably just tried to load a linux .so file or something.`,
        );
        return;
      }
      throw e;
    } finally {
      releaseDynlibLock();
    }

    DEBUG && console.debug(`Loaded dynamic library ${lib} (global: ${global})`);
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
  public async loadDynlibsFromPackage(
    // TODO: Simplify the type of pkg after removing usage of this function in micropip.
    pkg: { file_name: string },
    dynlibPaths: string[],
  ) {
    for (const path of dynlibPaths) {
      await this.loadDynlib(path, false);
    }
  }
}

if (typeof API !== "undefined" && typeof Module !== "undefined") {
  const singletonDynlibLoader = new DynlibLoader(API, Module);

  // TODO: Find a better way to register these functions
  API.loadDynlib = singletonDynlibLoader.loadDynlib.bind(singletonDynlibLoader);
  API.loadDynlibsFromPackage =
    singletonDynlibLoader.loadDynlibsFromPackage.bind(singletonDynlibLoader);
}
