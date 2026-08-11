/* Handle dynamic library loading. */

import { PackageManagerAPI, PackageManagerModule } from "./types";

import { createLock } from "./common/lock";
import {
  DynlibEntry,
  shouldPreloadDynlib,
} from "./package-loading/dynlib-preload";

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
   * Compile and load a dynamic library asynchronously.
   *
   * Most libraries are instead compiled by CPython's import machinery, which
   * `dlopen()`s them synchronously. This is for the ones that are too large for
   * a runtime to compile synchronously, and for callers that need the library
   * resident before any Python code runs.
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
        throw new Error(`Failed to load dynamic library ${lib}: ${error ?? e}`);
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
   * Compile the shared libraries of a package that cannot be left to CPython's
   * import machinery.
   *
   * @param dynlibs The shared libraries found in the package.
   * @param preloadAll Whether to compile every library rather than only the
   * ones that cannot be compiled synchronously later.
   * @private
   */
  public async preloadDynlibs(
    dynlibs: readonly DynlibEntry[],
    preloadAll: boolean,
  ) {
    for (const entry of dynlibs) {
      if (shouldPreloadDynlib(entry, preloadAll)) {
        await this.loadDynlib(entry.path);
      }
    }
  }
}

if (typeof API !== "undefined" && typeof Module !== "undefined") {
  const singletonDynlibLoader = new DynlibLoader(API, Module);

  // TODO: Find a better way to register these functions
  API.loadDynlib = singletonDynlibLoader.loadDynlib.bind(singletonDynlibLoader);
}
