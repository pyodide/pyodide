import { DynlibLoader } from "./dynload";
import { uriToPackageData } from "./packaging-utils";
import { PackageManagerAPI, PackageManagerModule } from "./types";

/**
 * The Installer class is responsible for installing packages into the Pyodide filesystem.
 * This includes
 * - extracting the package into the filesystem
 * - storing metadata about the Package
 * - loading shared libraries
 * - installing data files
 * @hidden
 */
export class Installer {
  #api: PackageManagerAPI;
  #dynlibLoader: DynlibLoader;

  constructor(api: PackageManagerAPI, pyodideModule: PackageManagerModule) {
    this.#api = api;
    this.#dynlibLoader = new DynlibLoader(api, pyodideModule);
  }

  async install(
    buffer: Uint8Array,
    filename: string,
    installDir: string,
    metadata?: ReadonlyMap<string, string>,
  ) {
    const dynlibs: string[] = this.#api.package_loader.unpack_buffer.callKwargs(
      {
        buffer,
        filename,
        extract_dir: installDir,
        metadata,
        calculate_dynlibs: true,
      },
    );

    DEBUG &&
      console.debug(
        `Found ${dynlibs.length} dynamic libraries inside ${filename}`,
      );

    await this.#dynlibLoader.loadDynlibsFromPackage(
      { file_name: filename },
      dynlibs,
    );
  }
}

/** @hidden */
export let install: typeof Installer.prototype.install;

if (typeof API !== "undefined" && typeof Module !== "undefined") {
  const singletonInstaller = new Installer(API, Module);

  install = singletonInstaller.install.bind(singletonInstaller);

  // TODO: Find a better way to register these functions
  API.install = install;
}
