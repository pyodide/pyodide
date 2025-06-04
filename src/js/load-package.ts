import "./constants";
import {
  Lockfile,
  PackageData,
  InternalPackageData,
  PackageLoadMetadata,
  PackageManagerAPI,
  PackageManagerModule,
  LoadedPackages,
} from "./types";
import { IN_NODE } from "./environments";
import type { PyProxy } from "generated/pyproxy";
import { createResolvable } from "./common/resolveable";
import { createLock } from "./common/lock";
import {
  canonicalizePackageName,
  uriToPackageData,
  base16ToBase64,
} from "./packaging-utils";
import {
  nodeFsPromisesMod,
  loadBinaryFile,
  resolvePath,
  initNodeModules,
  ensureDirNode,
} from "./compat";
import { Installer } from "./installer";
import { createContextWrapper } from "./common/contextManager";

/**
 * Initialize the packages index. This is called as early as possible in
 * loadPyodide so that fetching pyodide-lock.json can occur in parallel with other
 * operations.
 * @param lockFilePromise
 * @private
 */
export async function initializePackageIndex(
  lockFilePromise: Promise<Lockfile>,
) {
  await initNodeModules();
  const lockfile = await lockFilePromise;
  if (!lockfile.packages) {
    throw new Error(
      "Loaded pyodide lock file does not contain the expected key 'packages'.",
    );
  }

  if (lockfile.info.version !== API.version) {
    throw new Error(
      "Lock file version doesn't match Pyodide version.\n" +
        `   lockfile version: ${lockfile.info.version}\n` +
        `   pyodide  version: ${API.version}`,
    );
  }

  API.lockfile = lockfile;
  API.lockfile_info = lockfile.info;
  API.lockfile_packages = lockfile.packages;
  API.lockfile_unvendored_stdlibs_and_test = [];

  // micropip compatibility
  API.repodata_info = lockfile.info;
  API.repodata_packages = lockfile.packages;

  // compute the inverted index for imports to package names
  API._import_name_to_package_name = new Map<string, string>();
  for (let name of Object.keys(API.lockfile_packages)) {
    const pkg = API.lockfile_packages[name];

    for (let import_name of pkg.imports) {
      API._import_name_to_package_name.set(import_name, name);
    }

    if (pkg.package_type === "cpython_module") {
      API.lockfile_unvendored_stdlibs_and_test.push(name);
    }
  }

  API.lockfile_unvendored_stdlibs =
    API.lockfile_unvendored_stdlibs_and_test.filter(
      (lib: string) => lib !== "test",
    );
  let toLoad = API.config.packages;
  if (API.config.fullStdLib) {
    toLoad = [...toLoad, ...API.lockfile_unvendored_stdlibs];
  }
  await loadPackage(toLoad, { messageCallback() {} });
  // Have to wait for bootstrapFinalizedPromise before calling Python APIs
  await API.bootstrapFinalizedPromise;
  // Set up module_not_found_hook
  const importhook = API._pyodide._importhook;
  importhook.register_module_not_found_hook(
    API._import_name_to_package_name,
    API.lockfile_unvendored_stdlibs_and_test,
  );
  API.package_loader.init_loaded_packages();
}

const DEFAULT_CHANNEL = "default channel";
const INSTALLER = "pyodide.loadPackage";

/**
 * @hidden
 * The package manager is responsible for installing and managing Pyodide packages.
 */
export class PackageManager {
  #api: PackageManagerAPI;
  #module: PackageManagerModule;
  #installer: Installer;

  /**
   * Only used in Node. If we can't find a package in node_modules, we'll use this
   * to fetch the package from the cdn (and we'll store it into node_modules so
   * subsequent loads don't require a web request).
   */
  private cdnURL: string = "";

  /**
   * The set of loaded packages.
   * This is exposed as a global variable and can be modified by micropip
   *
   * TODO: Make this private and expose a setter
   */
  public loadedPackages: LoadedPackages = {};

  private _lock = createLock();

  public installBaseUrl: string;

  /**
   * The function to use for stdout and stderr, defaults to console.log and console.error
   */
  private stdout: (message: string) => void;
  private stderr: (message: string) => void;

  private defaultChannel: string = DEFAULT_CHANNEL;

  constructor(api: PackageManagerAPI, pyodideModule: PackageManagerModule) {
    this.#api = api;
    this.#module = pyodideModule;
    this.#installer = new Installer(api, pyodideModule);

    // use lockFileURL as the base URL for the packages
    // if lockFileURL is relative, use location as the base URL
    const lockfileBase =
      this.#api.config.lockFileURL.substring(
        0,
        this.#api.config.lockFileURL.lastIndexOf("/") + 1,
      ) || globalThis.location?.toString();

    if (IN_NODE) {
      this.installBaseUrl = this.#api.config.packageCacheDir ?? lockfileBase;
    } else {
      this.installBaseUrl = lockfileBase;
    }

    this.stdout = (msg: string) => {
      const sp = this.#module.stackSave();
      try {
        const msgPtr = this.#module.stringToUTF8OnStack(msg);
        this.#module._print_stdout(msgPtr);
      } finally {
        this.#module.stackRestore(sp);
      }
    };

    this.stderr = (msg: string) => {
      const sp = this.#module.stackSave();
      try {
        const msgPtr = this.#module.stringToUTF8OnStack(msg);
        this.#module._print_stderr(msgPtr);
      } finally {
        this.#module.stackRestore(sp);
      }
    };
  }

  /**
   * Load packages from the Pyodide distribution or Python wheels by URL.
   *
   * This installs packages in the virtual filesystem. Packages
   * needs to be imported from Python before it can be used.
   *
   * This function can only install packages included in the Pyodide distribution,
   * or Python wheels by URL, without dependency resolution. It is significantly
   * more limited in terms of functionality as compared to :mod:`micropip`,
   * however it has less overhead and can be faster.
   *
   * When installing binary wheels by URLs it is user's responsibility to check
   * that the installed binary wheel is compatible in terms of Python and
   * Emscripten versions. Compatibility is not checked during installation time
   * (unlike with micropip). If a wheel for the wrong Python/Emscripten version
   * is installed it would fail at import time.
   *
   *
   * @param names Either a single package name or URL or a list of them. URLs can
   * be absolute or relative. The URLs must correspond to Python wheels:
   * either pure Python wheels, with a file name ending with ``none-any.whl``
   * or Emscripten/WASM 32 wheels, with a file name ending with
   * ``cp<pyversion>_emscripten_<em_version>_wasm32.whl``.
   * The argument can be a :js:class:`~pyodide.ffi.PyProxy` of a list, in
   * which case the list will be converted to JavaScript and the
   * :js:class:`~pyodide.ffi.PyProxy` will be destroyed.
   * @param options
   * @param options.messageCallback A callback, called with progress messages
   *    (optional)
   * @param options.errorCallback A callback, called with error/warning messages
   *    (optional)
   * @param options.checkIntegrity If true, check the integrity of the downloaded
   *    packages (default: true)
   * @returns The loaded package data.
   */
  public async loadPackage(
    names: string | PyProxy | Array<string>,
    options: {
      messageCallback?: (message: string) => void;
      errorCallback?: (message: string) => void;
      checkIntegrity?: boolean;
    } = {
      checkIntegrity: true,
    },
  ): Promise<PackageData[]> {
    const wrappedLoadPackage = this.setCallbacks(
      options.messageCallback,
      options.errorCallback,
    )(this.loadPackageInner);

    return wrappedLoadPackage.call(this, names, options);
  }

  public async loadPackageInner(
    names: string | PyProxy | string[],
    options: {
      messageCallback?: (message: string) => void;
      errorCallback?: (message: string) => void;
      checkIntegrity?: boolean;
    } = {
      checkIntegrity: true,
    },
  ): Promise<Array<PackageData>> {
    const loadedPackageData = new Set<InternalPackageData>();
    const pkgNames = toStringArray(names);

    const toLoad = this.recursiveDependencies(pkgNames);

    for (const [_, { name, normalizedName, channel }] of toLoad) {
      const loadedChannel = this.getLoadedPackageChannel(name);
      if (!loadedChannel) continue;

      toLoad.delete(normalizedName);
      // If uri is from the default channel, we assume it was added as a
      // dependency, which was previously overridden.
      if (loadedChannel === channel || channel === this.defaultChannel) {
        this.logStdout(`${name} already loaded from ${loadedChannel}`);
      } else {
        this.logStderr(
          `URI mismatch, attempting to load package ${name} from ${channel} ` +
            `while it is already loaded from ${loadedChannel}. To override a dependency, ` +
            `load the custom package first.`,
        );
      }
    }

    if (toLoad.size === 0) {
      this.logStdout("No new packages to load");
      return [];
    }

    const packageNames = Array.from(toLoad.values(), ({ name }) => name)
      .sort()
      .join(", ");
    const failed = new Map<string, Error>();
    const releaseLock = await this._lock();
    try {
      this.logStdout(`Loading ${packageNames}`);
      for (const [_, pkg] of toLoad) {
        if (this.getLoadedPackageChannel(pkg.name)) {
          // Handle the race condition where the package was loaded between when
          // we did dependency resolution and when we acquired the lock.
          toLoad.delete(pkg.normalizedName);
          continue;
        }

        pkg.installPromise = this.downloadAndInstall(
          pkg,
          toLoad,
          loadedPackageData,
          failed,
          options.checkIntegrity,
        );
      }

      await Promise.all(
        Array.from(toLoad.values()).map(({ installPromise }) => installPromise),
      );

      // Warning: this sounds like it might not do anything important, but it
      // fills in the GOT. There can be segfaults if we leave it out.
      // See https://github.com/emscripten-core/emscripten/issues/22052
      // TODO: Fix Emscripten so this isn't needed
      this.#module.reportUndefinedSymbols();
      if (loadedPackageData.size > 0) {
        const successNames = Array.from(loadedPackageData, (pkg) => pkg.name)
          .sort()
          .join(", ");
        this.logStdout(`Loaded ${successNames}`);
      }

      if (failed.size > 0) {
        const failedNames = Array.from(failed.keys()).sort().join(", ");
        this.logStdout(`Failed to load ${failedNames}`);
        for (const [name, err] of failed) {
          this.logStderr(`The following error occurred while loading ${name}:`);
          this.logStderr(err.message);
        }
      }

      // We have to invalidate Python's import caches, or it won't
      // see the new files.
      this.#api.importlib.invalidate_caches();
      return Array.from(loadedPackageData, filterPackageData);
    } finally {
      releaseLock();
    }
  }

  /**
   * Recursively add a package and its dependencies to toLoad.
   * A helper function for recursiveDependencies.
   * @param name The package to add
   * @param toLoad The set of names of packages to load
   * @private
   */
  private addPackageToLoad(
    name: string,
    toLoad: Map<string, PackageLoadMetadata>,
  ) {
    const normalizedName = canonicalizePackageName(name);
    if (toLoad.has(normalizedName)) {
      return;
    }
    const pkgInfo = this.#api.lockfile_packages[normalizedName];
    if (!pkgInfo) {
      throw new Error(`No known package with name '${name}'`);
    }

    toLoad.set(normalizedName, {
      name: pkgInfo.name,
      normalizedName,
      channel: this.defaultChannel,
      depends: pkgInfo.depends,
      installPromise: undefined,
      done: createResolvable(),
      packageData: pkgInfo,
    });

    // If the package is already loaded, we don't add dependencies, but warn
    // the user later. This is especially important if the loaded package is
    // from a custom url, in which case adding dependencies is wrong.
    if (this.getLoadedPackageChannel(pkgInfo.name)) {
      return;
    }

    for (let depName of pkgInfo.depends) {
      this.addPackageToLoad(depName, toLoad);
    }
  }

  /**
   * Calculate the dependencies of a set of packages
   * @param names The list of names whose dependencies we need to calculate.
   * @returns The map of package names to PackageLoadMetadata
   * @private
   */
  private recursiveDependencies(
    names: string[],
  ): Map<string, PackageLoadMetadata> {
    const toLoad: Map<string, PackageLoadMetadata> = new Map();
    for (let name of names) {
      const parsedPackageData = uriToPackageData(name);
      if (parsedPackageData === undefined) {
        this.addPackageToLoad(name, toLoad);
        continue;
      }

      const { name: pkgname, version, fileName } = parsedPackageData;
      const channel = name;

      if (toLoad.has(pkgname) && toLoad.get(pkgname)!.channel !== channel) {
        this.logStderr(
          `Loading same package ${pkgname} from ${channel} and ${
            toLoad.get(pkgname)!.channel
          }`,
        );
        continue;
      }
      toLoad.set(pkgname, {
        name: pkgname,
        normalizedName: pkgname,
        channel: channel, // name is url in this case
        depends: [],
        installPromise: undefined,
        done: createResolvable(),
        packageData: {
          name: pkgname,
          version: version,
          file_name: fileName,
          install_dir: "site",
          sha256: "",
          package_type: "package",
          imports: [],
          depends: [],
        },
      });
    }
    return toLoad;
  }

  /**
   * Download a package. If `channel` is `DEFAULT_CHANNEL`, look up the wheel URL
   * relative to packageCacheDir (when IN_NODE), or to lockfileURL, otherwise use the URL specified by
   * `channel`.
   * @param pkg The package to download
   * @param channel Either `DEFAULT_CHANNEL` or the absolute URL to the
   * wheel or the path to the wheel relative to packageCacheDir (when IN_NODE), or lockfileURL.
   * @param checkIntegrity Whether to check the integrity of the downloaded
   * package.
   * @returns The binary data for the package
   * @private
   */
  private async downloadPackage(
    pkg: PackageLoadMetadata,
    checkIntegrity: boolean = true,
  ): Promise<Uint8Array> {
    await ensureDirNode(this.installBaseUrl);

    let fileName, uri, fileSubResourceHash;
    if (pkg.channel === this.defaultChannel) {
      if (!(pkg.normalizedName in this.#api.lockfile_packages)) {
        throw new Error(`Internal error: no entry for package named ${name}`);
      }
      const lockfilePackage = this.#api.lockfile_packages[pkg.normalizedName];
      fileName = lockfilePackage.file_name;

      uri = resolvePath(fileName, this.installBaseUrl);
      fileSubResourceHash = "sha256-" + base16ToBase64(lockfilePackage.sha256);
    } else {
      uri = pkg.channel;
      fileSubResourceHash = undefined;
    }

    if (!checkIntegrity) {
      fileSubResourceHash = undefined;
    }
    try {
      DEBUG && console.debug(`Downloading package ${pkg.name} from ${uri}`);
      return await loadBinaryFile(uri, fileSubResourceHash);
    } catch (e) {
      if (!IN_NODE || pkg.channel !== this.defaultChannel) {
        throw e;
      }
    }
    this.logStdout(
      `Didn't find package ${fileName} locally, attempting to load from ${this.cdnURL}`,
    );
    // If we are IN_NODE, download the package from the cdn, then stash it into
    // the node_modules directory for future use.
    let binary = await loadBinaryFile(this.cdnURL + fileName);
    this.logStdout(
      `Package ${fileName} loaded from ${this.cdnURL}, caching the wheel in node_modules for future use.`,
    );
    await nodeFsPromisesMod.writeFile(uri, binary);
    return binary;
  }

  /**
   * Install the package into the file system.
   * @param metadata The package metadata
   * @param buffer The binary data returned by downloadPackage
   * @private
   */
  private async installPackage(
    metadata: PackageLoadMetadata,
    buffer: Uint8Array,
  ) {
    let pkg = this.#api.lockfile_packages[metadata.normalizedName];
    if (!pkg) {
      pkg = metadata.packageData;
    }

    const filename = pkg.file_name;

    // This Python helper function unpacks the buffer and lists out any .so files in it.
    const installDir: string = this.#api.package_loader.get_install_dir(
      pkg.install_dir,
    );

    DEBUG &&
      console.debug(
        `Installing package ${metadata.name} from ${metadata.channel} to ${installDir}`,
      );

    await this.#installer.install(
      buffer,
      filename,
      installDir,
      new Map([
        ["INSTALLER", INSTALLER],
        [
          "PYODIDE_SOURCE",
          metadata.channel === this.defaultChannel
            ? "pyodide"
            : metadata.channel,
        ],
      ]),
    );
  }

  /**
   * Download and install the package.
   * Downloads can be done in parallel, but installs must be done for dependencies first.
   * @param pkg The package to load
   * @param toLoad The map of package names to PackageLoadMetadata
   * @param loaded The set of loaded package metadata, this will be updated by this function.
   * @param failed The map of <failed package name, error message>, this will be updated by this function.
   * @param checkIntegrity Whether to check the integrity of the downloaded
   * package.
   * @private
   */
  private async downloadAndInstall(
    pkg: PackageLoadMetadata,
    toLoad: Map<string, PackageLoadMetadata>,
    loaded: Set<InternalPackageData>,
    failed: Map<string, Error>,
    checkIntegrity: boolean = true,
  ) {
    if (loadedPackages[pkg.name] !== undefined) {
      return;
    }

    try {
      const buffer = await this.downloadPackage(pkg, checkIntegrity);
      const installPromiseDependencies = pkg.depends.map((dependency) => {
        return toLoad.has(dependency)
          ? toLoad.get(dependency)!.done
          : Promise.resolve();
      });
      // Can't install until bootstrap is finalized.
      await this.#api.bootstrapFinalizedPromise;

      // wait until all dependencies are installed
      await Promise.all(installPromiseDependencies);

      await this.installPackage(pkg, buffer);

      loaded.add(pkg.packageData);
      loadedPackages[pkg.name] = pkg.channel;
    } catch (err: any) {
      failed.set(pkg.name, err);
      // We don't throw error when loading a package fails, but just report it.
      // pkg.done.reject(err);
    } finally {
      pkg.done.resolve();
    }
  }

  public setCdnUrl(url: string) {
    this.cdnURL = url;
  }

  /**
   * getLoadedPackageChannel returns the channel from which a package was loaded.
   * if the package is not loaded, it returns null.
   * @param pkg package name
   */
  public getLoadedPackageChannel(pkg: string): string | null {
    const channel = this.loadedPackages[pkg];
    if (channel === undefined) {
      return null;
    }

    return channel;
  }

  public setCallbacks(
    stdout?: (message: string) => void,
    stderr?: (message: string) => void,
  ) {
    const originalStdout = this.stdout;
    const originalStderr = this.stderr;

    return createContextWrapper(
      () => {
        this.stdout = stdout || originalStdout;
        this.stderr = stderr || originalStderr;
      },
      () => {
        this.stdout = originalStdout;
        this.stderr = originalStderr;
      },
    );
  }

  public logStdout(message: string) {
    this.stdout(message);
  }

  public logStderr(message: string) {
    this.stderr(message);
  }
}

function filterPackageData({
  name,
  version,
  file_name,
  package_type,
}: InternalPackageData): PackageData {
  return { name, version, fileName: file_name, packageType: package_type };
}

/**
 * Converts a string or PyProxy to an array of strings.
 * @private
 */
export function toStringArray(str: string | PyProxy | string[]): string[] {
  // originally, this condition was "names instanceof PyProxy",
  // but it is changed to check names.toJs so that we can use type-only import for PyProxy and remove side effects.
  // this change is required to run unit tests against this file, when global API or Module is not available.
  // TODO: remove side effects from pyproxy.ts so that we can directly import PyProxy
  // @ts-ignore
  if (typeof str.toJs === "function") {
    // @ts-ignore
    str = str.toJs();
  }
  if (!Array.isArray(str)) {
    str = [str as string];
  }

  return str;
}

export let loadPackage: typeof PackageManager.prototype.loadPackage;
/**
 * An object whose keys are the names of the loaded packages and whose values
 * are the install sources of the packages. Use
 * `Object.keys(pyodide.loadedPackages)` to get the list of names of loaded
 * packages, and `pyodide.loadedPackages[package_name]` to access the install
 * source for a particular `package_name`.
 */
export let loadedPackages: LoadedPackages;

if (typeof API !== "undefined" && typeof Module !== "undefined") {
  const singletonPackageManager = new PackageManager(API, Module);

  loadPackage = singletonPackageManager.loadPackage.bind(
    singletonPackageManager,
  );

  /**
   * The list of packages that Pyodide has loaded.
   * Use ``Object.keys(pyodide.loadedPackages)`` to get the list of names of
   * loaded packages, and ``pyodide.loadedPackages[package_name]`` to access
   * install location for a particular ``package_name``.
   */
  loadedPackages = singletonPackageManager.loadedPackages;

  // TODO: Find a better way to register these functions
  API.setCdnUrl = singletonPackageManager.setCdnUrl.bind(
    singletonPackageManager,
  );

  API.lockfileBaseUrl = singletonPackageManager.installBaseUrl;

  if (API.lockFilePromise) {
    API.packageIndexReady = initializePackageIndex(API.lockFilePromise);
  }
}
