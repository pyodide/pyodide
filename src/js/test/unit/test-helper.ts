import { PackageManagerAPI, PackageManagerModule } from "../../types.ts";

export const genMockAPI = (
  config: Partial<PackageManagerAPI["config"]> = {},
): PackageManagerAPI => {
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
      sharedLibraryPreloadThreshold: 8 * 1024 * 1024,
      ...config,
    },
    lockfile_packages: {},
    bootstrapFinalizedPromise: Promise.resolve(),
    sitepackages: "",
    defaultLdLibraryPath: [],
  };
};

export const genMockModule = (): PackageManagerModule => {
  return {
    FS: {
      stat: (_path: string) => ({ size: 0 }),
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
