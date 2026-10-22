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
    pyVersionTuple: [3, 14, 2],
  };
};

export const genMockModule = (): PackageManagerModule => {
  return {
    FS: {
      mkdirTree: (_path: string) => {},
      writeFile: (_path: string, _data: Uint8Array, _opts?: object) => {},
    } as unknown as PackageManagerModule["FS"],
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
