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
    loadDynamicLibrary: () => {},
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
  };
};
