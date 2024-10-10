import {
  PackageManager,
  PackageManagerAPI,
  PackageManagerModule,
} from "../../load-package.ts";

describe("PackageManager", () => {
  // TODO: add more unittests
  it("should initialize with API and Module", () => {
    const mockApi: PackageManagerAPI = {
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
    };
    const mockMod: PackageManagerModule = {
      reportUndefinedSymbols: () => {},
    };

    const _ = new PackageManager(mockApi, mockMod);
  });
});
