import { DynlibLoader } from "./dynload";
import {
  PackageManagerAPI,
  PackageManagerModule,
  PyodideModule,
} from "./types";
import { ZipReader, Uint8ArrayReader } from "@zip.js/zip.js";

function canonicalizePackageName(name: string): string {
  return name.replaceAll(/[-_.]+/g, "-").toLowerCase();
}

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
  #fs: PyodideModule["FS"];
  #dynlibLoader: DynlibLoader;

  constructor(api: PackageManagerAPI, pyodideModule: PackageManagerModule) {
    this.#api = api;
    this.#fs = pyodideModule.FS;
    this.#dynlibLoader = new DynlibLoader(api, pyodideModule);
  }

  async installTar(
    buffer: Uint8Array,
    filename: string,
    installDir: string,
    metadata?: [string, string][],
  ) {
    await this.#api.bootstrapFinalizedPromise;
    const dynlibs = this.#api.package_loader.unpack_buffer.callKwargs({
      buffer,
      filename,
      extract_dir: installDir,
      metadata,
      calculate_dynlibs: true,
    });
    await this.#dynlibLoader.loadDynlibsFromPackage(
      { file_name: filename },
      dynlibs,
    );
  }

  async installDataFiles(dataDir: string): Promise<void> {
    await this.#api.bootstrapFinalizedPromise;
    this.#api.package_loader.install_files(dataDir, this.#api.sys.prefix);
  }

  async unpackZip(
    buffer: Uint8Array,
    installDir: string,
  ): Promise<{
    dynlibs: string[];
    metadataDir: string | undefined;
    dataFilesDir: string | undefined;
  }> {
    const reader = new ZipReader(new Uint8ArrayReader(buffer));
    const dynlibs = [];
    let metadataDir;
    let dataFilesDir;
    for await (const entry of reader.getEntriesGenerator()) {
      const path = installDir + "/" + entry.filename;
      if (entry.directory) {
        this.#fs.mkdirTree(path);
        continue;
      }
      const dirname = Module.PATH.dirname(path);
      this.#fs.mkdirTree(dirname);
      const buf = await entry.arrayBuffer();
      this.#fs.writeFile(path, new Uint8Array(buf), { canOwn: true });
      if (entry.filename.endsWith(".so")) {
        dynlibs.push(path);
      }
      const start = entry.filename.split("/", 1)[0];
      if (start.endsWith(".dist-info")) {
        metadataDir = start;
      }
      if (start.endsWith(".data")) {
        dataFilesDir = start;
      }
    }
    return { dynlibs, dataFilesDir, metadataDir };
  }

  async install(
    buffer: Uint8Array,
    filename: string,
    installDir: string,
    metadata?: [string, string][],
    postBootstrapPromises?: Promise<void>[] | undefined,
  ) {
    async function maybeDefer(p: Promise<void>) {
      if (postBootstrapPromises) {
        postBootstrapPromises.push(p);
      } else {
        await p;
      }
    }

    if (filename.endsWith(".tar")) {
      const promise = this.installTar(buffer, filename, installDir, metadata);
      await maybeDefer(promise);
      return;
    }
    const { dynlibs, dataFilesDir, metadataDir } = await this.unpackZip(
      buffer,
      installDir,
    );

    for (const [key, value] of metadata ?? []) {
      this.#fs.writeFile(`${installDir}/${metadataDir}/${key}`, value);
    }
    if (dataFilesDir) {
      await maybeDefer(
        this.installDataFiles(`${installDir}/${dataFilesDir}/data`),
      );
    }

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
