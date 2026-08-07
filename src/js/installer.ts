import { DynlibLoader } from "./dynload";
import type { PyProxy } from "generated/pyproxy";
import { PackageManagerAPI, PackageManagerModule } from "./types";
import { unpackZip } from "./package-loading/archive";
import { extractArchiveToFS } from "./package-loading/fs-extract";
import {
  computePythonPaths,
  type PythonPaths,
} from "./package-loading/python-paths";
import { dirname, resolvePosix } from "./package-loading/posix-path";

// Created lazily on first use: TextEncoder is not available at module-init time
// in some engines (e.g. d8), which never install packages.
let textEncoder: TextEncoder | undefined;

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
    metadata?: Record<string, string> | PyProxy,
  ) {
    const { prefix, extensionTags } = this.#getPythonPaths();
    const entries = unpackZip(buffer);
    const { dynlibs, distInfoDir, dataDir } = extractArchiveToFS(
      this.#module.FS,
      entries,
      installDir,
      extensionTags,
    );

    const metadataMap = toMetadata(metadata);
    if (metadataMap && distInfoDir) {
      this.#writeWheelMetadata(installDir, distInfoDir, metadataMap);
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
    metadata: Record<string, string>,
  ) {
    for (const [key, value] of Object.entries(metadata)) {
      this.#module.FS.writeFile(
        `${installDir}/${distInfoDir}/${key}`,
        (textEncoder ??= new TextEncoder()).encode(value),
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

// downstream Python packages such as micropip would pass the metadata
// as Python dict (PyProxy). So we type-cast it to Record<string, string>
// to make it compatible with the installer
function toMetadata(
  metadata?: Record<string, string> | PyProxy,
): Record<string, string> | undefined {
  if (!metadata) {
    return undefined;
  }
  return metadata as Record<string, string>;
}

/** @hidden */
export let install: typeof Installer.prototype.install;

if (typeof API !== "undefined" && typeof Module !== "undefined") {
  const singletonInstaller = new Installer(API, Module);

  install = singletonInstaller.install.bind(singletonInstaller);

  // TODO: Find a better way to register these functions
  API.install = install;
}
