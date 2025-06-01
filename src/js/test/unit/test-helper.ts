import { PackageManagerAPI, PackageManagerModule } from "../../types.ts";

export const genMockAPI = (): PackageManagerAPI => {
  return {
    importlib: {
      invalidate_caches: () => {},
    },
    package_loader: {
      get_install_dir: () => "",
      init_loaded_packages: () => {},
      unpack_buffer: {
        callKwargs: () => {},
      },
    },
    config: {
      indexURL: "",
      packageCacheDir: "",
    },
    lockfile_packages: {},
    bootstrapFinalizedPromise: Promise.resolve(),
    sitepackages: "",
    defaultLdLibraryPath: [],
  };
};

export const genMockModule = (): PackageManagerModule => {
  return {
    reportUndefinedSymbols: () => {},
    LDSO: {
      loadedLibsByName: {},
    },
    PATH: {},
    FS: {
      readdir: (path: string) => [],
      isDir: (mode: number) => true,
      findObject: (path: string, dontResolveLastLink?: boolean) => {},
      readFile: (path: string) => new Uint8Array(),
      lookupPath: (
        path: string,
        options?: {
          follow_mount?: boolean;
        },
      ) => {
        return {
          node: {
            timestamp: 1,
            rdev: 2,
            contents: new Uint8Array(),
            mode: 3,
          },
        };
      },
    },
    stringToUTF8OnStack: (str: string) => {
      return 0;
    },
    stackSave: () => 0,
    stackRestore: (ptr: number) => {},
    _print_stdout(ptr: number) {},
    _print_stderr(ptr: number) {},
    addFunction(f: Function, sig: string) { return 0 },
    _emscripten_dlopen(
      filename: number,
      flags: number,
      userData: number,
      onsuccess: number,
      onerror: number,
    ) {}
  };
};
