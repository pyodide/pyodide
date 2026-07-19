import { DynlibLoader } from "./dynload";
import { PackageManagerAPI, PackageManagerModule } from "./types";
import { unpackArchive } from "./package-loading/archive";
import { extractArchiveToFS } from "./package-loading/fs-extract";
import {
  computePythonPaths,
  type PythonPaths,
} from "./package-loading/python-paths";
import { dirname, resolvePosix } from "./package-loading/posix-path";

const textEncoder = new TextEncoder();

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
  #module: PackageManagerModule;
  #dynlibLoader: DynlibLoader;
  #pythonPaths?: PythonPaths;

  constructor(api: PackageManagerAPI, pyodideModule: PackageManagerModule) {
    this.#api = api;
    this.#module = pyodideModule;
    this.#dynlibLoader = new DynlibLoader(api, pyodideModule);
  }

  // pyVersionTuple is only set during the stdlib preRun step, which runs after
  // this class is constructed. Compute the paths lazily on first use and cache.
  #getPythonPaths(): PythonPaths {
    return (this.#pythonPaths ??= computePythonPaths(this.#api.pyVersionTuple));
  }

  async install(
    buffer: Uint8Array,
    filename: string,
    installDir: string,
    metadata?: ReadonlyMap<string, string>,
  ) {
    const { prefix, extensionTags } = this.#getPythonPaths();
    const entries = unpackArchive(buffer, filename);
    const { dynlibs, distInfoDir, dataDir } = extractArchiveToFS(
      this.#module.FS,
      entries,
      installDir,
      extensionTags,
    );

    if (metadata && distInfoDir) {
      this.#writeWheelMetadata(installDir, distInfoDir, metadata);
    }

    if (dataDir) {
      this.#installDataFiles(entries, dataDir, prefix);
    }

    DEBUG &&
      console.debug(
        `Found ${dynlibs.length} dynamic libraries inside ${filename}`,
      );

    await this.#dynlibLoader.loadDynlibsFromPackage(
      { file_name: filename },
      dynlibs,
    );
  }

  #writeWheelMetadata(
    installDir: string,
    distInfoDir: string,
    metadata: ReadonlyMap<string, string>,
  ) {
    for (const [key, value] of metadata) {
      this.#module.FS.writeFile(
        `${installDir}/${distInfoDir}/${key}`,
        textEncoder.encode(value),
      );
    }
  }

  // Wheel `.data/data/<path>` entries are installed relative to sys.prefix, per
  // the "data" install scheme. Mirrors `install_datafiles` in _package_loader.py.
  #installDataFiles(
    entries: readonly { name: string; data: Uint8Array }[],
    dataDir: string,
    prefix: string,
  ) {
    const dataScheme = `${dataDir}/data/`;
    for (const { name, data } of entries) {
      if (name.endsWith("/") || !name.startsWith(dataScheme)) {
        continue;
      }
      const target = resolvePosix(prefix, name.slice(dataScheme.length));
      this.#module.FS.mkdirTree(dirname(target));
      this.#module.FS.writeFile(target, data, { canOwn: true });
    }
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
