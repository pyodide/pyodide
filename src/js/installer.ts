
import { PackageManagerAPI } from "./types";

/**
 * The Installer class is responsible for installing packages into the Pyodide filesystem.
 * This includes
 * - extracting the package into the filesystem
 * - storing metadata about the Package
 * - installing data files
 * @hidden
 */
export class Installer {
  #api: PackageManagerAPI;

  constructor(api: PackageManagerAPI) {
    this.#api = api;
  }

  async install(
    buffer: Uint8Array,
    filename: string,
    installDir: string,
    metadata?: ReadonlyMap<string, string>,
  ) {
    this.#api.package_loader.unpack_buffer.callKwargs(
      {
        buffer,
        filename,
        extract_dir: installDir,
        metadata,
      },
    );
  }
}

/** @hidden */
export let install: typeof Installer.prototype.install;

if (typeof API !== "undefined") {
  const singletonInstaller = new Installer(API);

  install = singletonInstaller.install.bind(singletonInstaller);

  // TODO: Find a better way to register these functions
  API.install = install;
}
