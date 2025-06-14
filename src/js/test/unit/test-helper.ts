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
      lockFileURL: "",
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
    stringToNewUTF8: (str: string) => {
      return 0;
    },
    stringToUTF8OnStack: (str: string) => {
      return 0;
    },
    stackSave: () => 0,
    stackRestore: (ptr: number) => {},
    _print_stdout(ptr: number) {},
    _print_stderr(ptr: number) {},
    _emscripten_dlopen_promise: (libptr: number, flags: number) => {
      return 0;
    },
    getPromise: (pid: number) => {
      return Promise.resolve();
    },
    promiseMap: {
      free: (pid: number) => {},
    },
  };
};
