/* Handle dynamic library loading. */

declare var DEBUG: boolean;

import { PackageManagerAPI, PackageManagerModule } from "./types";

import { createLock } from "./common/lock";
import { LoadDynlibFS, ReadFileType, InternalPackageData } from "./types";

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
   * Recursively get all subdirectories of a directory
   *
   * @param dir The absolute path to the directory
   * @returns A list of absolute paths to the subdirectories
   * @private
   */
  public *getSubDirs(dir: string): Generator<string> {
    const dirs = this.#module.FS.readdir(dir);

    for (const d of dirs) {
      if (d === "." || d === "..") {
        continue;
      }

      const subdir: string = this.#module.PATH.join2(dir, d);
      const lookup = this.#module.FS.lookupPath(subdir);
      if (lookup.node === null) {
        continue;
      }

      const mode = lookup.node.mode;
      if (!this.#module.FS.isDir(mode)) {
        continue;
      }

      yield subdir;
      yield* this.getSubDirs(subdir);
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
  public createDynlibFS(lib: string, searchDirs?: string[]): LoadDynlibFS {
    const dirname = lib.substring(0, lib.lastIndexOf("/"));

    let _searchDirs = searchDirs || [];
    _searchDirs = _searchDirs.concat(this.#api.defaultLdLibraryPath, [dirname]);

    // TODO: add rpath to Emscripten dsos and remove this logic
    const resolvePath = (path: string) => {
      if (DEBUG) {
        if (
          this.#module.PATH.basename(path) !== this.#module.PATH.basename(lib)
        ) {
          console.debug(
            `Searching a library from ${path}, required by ${lib}.`,
          );
        }
      }

      // If the path is absolute, we don't need to search for it.
      if (this.#module.PATH.isAbs(path)) {
        return path;
      }

      // Step 1) Try to find the library in the search directories
      for (const dir of _searchDirs) {
        const fullPath = this.#module.PATH.join2(dir, path);

        if (this.#module.FS.findObject(fullPath) !== null) {
          return fullPath;
        }
      }

      // Step 2) try to find the library by searching child directories of the library directory
      //         (This should not be necessary in most cases, but some libraries have dependencies in the child directories)
      for (const childDir of this.getSubDirs(dirname)) {
        const fullPath = this.#module.PATH.join2(childDir, path);
        if (this.#module.FS.findObject(fullPath) !== null) {
          return fullPath;
        }
      }

      return path;
    };

    const readFile: ReadFileType = (path: string) =>
      this.#module.FS.readFile(resolvePath(path));

    const fs: LoadDynlibFS = {
      findObject: (path: string, dontResolveLastLink: boolean) => {
        let obj = this.#module.FS.findObject(
          resolvePath(path),
          dontResolveLastLink,
        );
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

    if (DEBUG) {
      console.debug(`Loading a dynamic library ${lib} (global: ${global})`);
    }

    const fs = this.createDynlibFS(lib, searchDirs);
    const localScope = global ? null : {};

    try {
      await this.#module.loadDynamicLibrary(
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
    pkg: InternalPackageData,
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
