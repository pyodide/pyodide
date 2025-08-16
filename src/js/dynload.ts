/* Handle dynamic library loading. */

import { PackageManagerAPI, PackageManagerModule } from "./types";

import { createLock } from "./common/lock";

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
   * @private
   */
  public async loadDynlib(lib: string) {
    const releaseDynlibLock = await this._lock();

    DEBUG && console.debug(`Loading dynamic library ${lib}`);

    try {
      const stack = this.#module.stackSave();
      const libUTF8 = this.#module.stringToUTF8OnStack(lib);

      try {
        const pid = this.#module._emscripten_dlopen_promise(
          libUTF8,
          2, // RTLD_NOW (2) | RTLD_LOCAL (0)
        );
        this.#module.stackRestore(stack);
        const promise = this.#module.getPromise(pid);
        this.#module.promiseMap.free(pid);
        await promise;
      } catch (e: any) {
        const error = this.getDLError();
        throw new Error(
          `Failed to load dynamic library ${lib}: ${error ?? e}`,
        );
      }
    } catch (e: any) {
      if (
        e &&
        e.message &&
        e.message.includes("need to see wasm magic number")
      ) {
        throw new Error(
          `Failed to load dynamic library ${lib} $. We probably just tried to load a linux .so file or something.`,
        );
      }
      throw e;
    } finally {
      releaseDynlibLock();
    }

    DEBUG && console.debug(`Loaded dynamic library ${lib}`);
  }

  /**
   * @returns The error message from the last dynamic library load operation, or undefined if there was no error.
   */
  private getDLError(): string | undefined {
    const errorPtr = this.#module._dlerror();
    if (errorPtr === 0) {
      return undefined;
    }

    const error = this.#module.UTF8ToString(
      errorPtr,
      512, // Use enough space for the error message
    );
    return error.trim();
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
      await this.loadDynlib(path);
    }
  }
}

if (typeof API !== "undefined" && typeof Module !== "undefined") {
  const singletonDynlibLoader = new DynlibLoader(API, Module);

  // TODO: Find a better way to register these functions
  API.loadDynlib = singletonDynlibLoader.loadDynlib.bind(singletonDynlibLoader);
}
