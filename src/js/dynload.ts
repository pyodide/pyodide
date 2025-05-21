/* Handle dynamic library loading. */

import { PackageManagerAPI, PackageManagerModule } from "./types";

import { createLock } from "./common/lock";
import { createResolvable } from "./common/resolveable";

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
   * @param searchDirs Directories to search for the library.
   * @private
   */
  public async loadDynlib(lib: string, global: boolean, searchDirs?: string[]) {
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
      // await this.#module.loadDynamicLibrary(
      //   lib,
      //   {
      //     loadAsync: true,
      //     nodelete: true,
      //     allowUndefined: true,
      //     global,
      //     fs,
      //   },
      //   localScope,
      // );
      // https://github.com/ryanking13/emscripten/blob/2e41541ba5478b454eb2d912d474810fa4ca2896/system/lib/libc/dynlink.c#L604
      const resolveable = createResolvable();
      const libUTF8 = this.#module.stringToNewUTF8(lib);

      const onsuccess = Module.addFunction(
        (userData: number, handle: number) => {
          DEBUG && console.debug(`Loaded dynamic library ${lib}`);
          resolveable.resolve();
        },
        "vii",
      );
      const onerror = Module.addFunction((error: number) => {
        resolveable.reject(
          new Error(`Failed to load dynamic library ${lib}, error: ${error}`),
        );
      }, "vi");

      try {
        this.#module._emscripten_dlopen(
          libUTF8,
          flags,
          0, // user_data is not used,
          onsuccess,
          onerror,
        );
        await resolveable;
      } finally {
        Module.removeFunction(onsuccess);
        Module.removeFunction(onerror);
      }

      // TODO(@ryanking13): check if this is still needed
      // Emscripten saves the list of loaded libraries in LDSO.loadedLibsByName.
      // However, since emscripten dylink metadata only contains the name of the
      // library not the full path, we need to update it manually in order to
      // prevent loading same library twice.
      if (this.#module.PATH.isAbs(lib)) {
        const libName: string = this.#module.PATH.basename(lib);
        const dso: any = this.#module.LDSO.loadedLibsByName[libName];
        if (!dso) {
          this.#module.LDSO.loadedLibsByName[libName] =
            this.#module.LDSO.loadedLibsByName[lib];
        }
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
    // assume that shared libraries of a package are located in <package-name>.libs directory,
    // following the convention of auditwheel.
    const auditWheelLibDir = `${this.#api.sitepackages}/${
      pkg.file_name.split("-")[0]
    }.libs`;

    for (const path of dynlibPaths) {
      await this.loadDynlib(path, false, [auditWheelLibDir]);
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
