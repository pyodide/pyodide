import "./constants";

import { IN_NODE } from "./environments";
import {
  nodeFsPromisesMod,
  loadBinaryFile,
  initNodeModules,
  resolvePath,
} from "./compat.js";
import { createLock } from "./lock";
import { loadDynlibsFromPackage } from "./dynload";
import { PyProxy } from "generated/pyproxy";
import {
  canonicalizePackageName,
  uriToPackageData,
  base16ToBase64,
} from "./packaging-utils";
import { Lockfile } from "./types";

/**
 * Initialize the packages index. This is called as early as possible in
 * loadPyodide so that fetching pyodide-lock.json can occur in parallel with other
 * operations.
 * @param lockFileURL
 * @private
 */
async function initializePackageIndex(lockFilePromise: Promise<Lockfile>) {
  await initNodeModules();
  const lockfile = await lockFilePromise;
  if (!lockfile.packages) {
    throw new Error(
      "Loaded pyodide lock file does not contain the expected key 'packages'.",
    );
  }

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
  await loadPackage(API.config.packages, { messageCallback() {} });
}

if (API.lockFilePromise) {
  API.packageIndexReady = initializePackageIndex(API.lockFilePromise);
}

/**
 * Only used in Node. If we can't find a package in node_modules, we'll use this
 * to fetch the package from the cdn (and we'll store it into node_modules so
 * subsequent loads don't require a web request).
 * @private
 */
let cdnURL: string;
API.setCdnUrl = function (url: string) {
  cdnURL = url;
};

//
// Dependency resolution
//
const DEFAULT_CHANNEL = "default channel";

export type PackageLoadMetadata = {
  name: string;
  normalizedName: string;
  channel: string;
  depends: string[];
  done: ResolvablePromise;
  installPromise?: Promise<void>;
  packageData: InternalPackageData;
};

export type PackageType =
  | "package"
  | "cpython_module"
  | "shared_library"
  | "static_library";

// Package data inside pyodide-lock.json
export type PackageData = {
  name: string;
  version: string;
  fileName: string;
  /** @experimental */
  packageType: PackageType;
};

export type InternalPackageData = {
  name: string;
  version: string;
  file_name: string;
  package_type: PackageType;
  install_dir: string;
  sha256: string;
  imports: string[];
  depends: string[];
  /** @deprecated */
  shared_library: boolean;
};

interface ResolvablePromise extends Promise<void> {
  resolve: (value?: any) => void;
  reject: (err?: Error) => void;
}

function createDonePromise(): ResolvablePromise {
  let _resolve: (value: any) => void = () => {};
  let _reject: (err: Error) => void = () => {};

  const p: any = new Promise<void>((resolve, reject) => {
    _resolve = resolve;
    _reject = reject;
  });

  p.resolve = _resolve;
  p.reject = _reject;
  return p;
}

/**
 * Recursively add a package and its dependencies to toLoad.
 * A helper function for recursiveDependencies.
 * @param name The package to add
 * @param toLoad The set of names of packages to load
 * @private
 */
function addPackageToLoad(
  name: string,
  toLoad: Map<string, PackageLoadMetadata>,
) {
  const normalizedName = canonicalizePackageName(name);
  if (toLoad.has(normalizedName)) {
    return;
  }
  const pkgInfo = API.lockfile_packages[normalizedName];
  if (!pkgInfo) {
    throw new Error(`No known package with name '${name}'`);
  }

  toLoad.set(normalizedName, {
    name: pkgInfo.name,
    normalizedName,
    channel: DEFAULT_CHANNEL,
    depends: pkgInfo.depends,
    installPromise: undefined,
    done: createDonePromise(),
    packageData: pkgInfo,
  });

  // If the package is already loaded, we don't add dependencies, but warn
  // the user later. This is especially important if the loaded package is
  // from a custom url, in which case adding dependencies is wrong.
  if (loadedPackages[pkgInfo.name] !== undefined) {
    return;
  }

  for (let depName of pkgInfo.depends) {
    addPackageToLoad(depName, toLoad);
  }
}

/**
 * Calculate the dependencies of a set of packages
 * @param names The list of names whose dependencies we need to calculate.
 * @returns The map of package names to PackageLoadMetadata
 * @private
 */
function recursiveDependencies(
  names: string[],
  errorCallback: (err: string) => void,
): Map<string, PackageLoadMetadata> {
  const toLoad: Map<string, PackageLoadMetadata> = new Map();
  for (let name of names) {
    const parsedPackageData = uriToPackageData(name);
    if (parsedPackageData === undefined) {
      addPackageToLoad(name, toLoad);
      continue;
    }

    const { name: pkgname, version, fileName } = parsedPackageData;
    const channel = name;

    if (toLoad.has(pkgname) && toLoad.get(pkgname)!.channel !== channel) {
      errorCallback(
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
      done: createDonePromise(),
      packageData: {
        name: pkgname,
        version: version,
        file_name: fileName,
        install_dir: "site",
        sha256: "",
        package_type: "package",
        imports: [],
        depends: [],
        shared_library: false,
      },
    });
  }
  return toLoad;
}
API.recursiveDependencies = recursiveDependencies;

//
// Dependency download and install
//

/**
 * Download a package. If `channel` is `DEFAULT_CHANNEL`, look up the wheel URL
 * relative to packageCacheDir (when IN_NODE), or indexURL from `pyodide-lock.json`, otherwise use the URL specified by
 * `channel`.
 * @param pkg The package to download
 * @param channel Either `DEFAULT_CHANNEL` or the absolute URL to the
 * wheel or the path to the wheel relative to packageCacheDir (when IN_NODE), or indexURL.
 * @param checkIntegrity Whether to check the integrity of the downloaded
 * package.
 * @returns The binary data for the package
 * @private
 */
async function downloadPackage(
  pkg: PackageLoadMetadata,
  checkIntegrity: boolean = true,
): Promise<Uint8Array> {
  let installBaseUrl: string;
  if (IN_NODE) {
    installBaseUrl = API.config.packageCacheDir;
    // ensure that the directory exists before trying to download files into it
    await nodeFsPromisesMod.mkdir(API.config.packageCacheDir, {
      recursive: true,
    });
  } else {
    installBaseUrl = API.config.indexURL;
  }

  let fileName, uri, fileSubResourceHash;
  if (pkg.channel === DEFAULT_CHANNEL) {
    if (!(pkg.normalizedName in API.lockfile_packages)) {
      throw new Error(`Internal error: no entry for package named ${name}`);
    }
    const lockfilePackage = API.lockfile_packages[pkg.normalizedName];
    fileName = lockfilePackage.file_name;

    uri = resolvePath(fileName, installBaseUrl);
    fileSubResourceHash = "sha256-" + base16ToBase64(lockfilePackage.sha256);
  } else {
    uri = pkg.channel;
    fileSubResourceHash = undefined;
  }

  if (!checkIntegrity) {
    fileSubResourceHash = undefined;
  }
  try {
    return await loadBinaryFile(uri, fileSubResourceHash);
  } catch (e) {
    if (!IN_NODE || pkg.channel !== DEFAULT_CHANNEL) {
      throw e;
    }
  }
  console.log(
    `Didn't find package ${fileName} locally, attempting to load from ${cdnURL}`,
  );
  // If we are IN_NODE, download the package from the cdn, then stash it into
  // the node_modules directory for future use.
  let binary = await loadBinaryFile(cdnURL + fileName);
  console.log(
    `Package ${fileName} loaded from ${cdnURL}, caching the wheel in node_modules for future use.`,
  );
  await nodeFsPromisesMod.writeFile(uri, binary);
  return binary;
}

/**
 * Install the package into the file system.
 * @param normalizedName The normalized name of the package
 * @param buffer The binary data returned by downloadPackage
 * @private
 */
async function installPackage(
  normalizedName: string,
  buffer: Uint8Array,
  channel: string,
) {
  let pkg = API.lockfile_packages[normalizedName];
  if (!pkg) {
    pkg = {
      name: "",
      version: "",
      file_name: ".whl",
      install_dir: "site",
      sha256: "",
      package_type: "package",
      imports: [] as string[],
      depends: [],
      shared_library: false,
    };
  }
  const filename = pkg.file_name;
  // This Python helper function unpacks the buffer and lists out any .so files in it.
  const dynlibs: string[] = API.package_loader.unpack_buffer.callKwargs({
    buffer,
    filename,
    target: pkg.install_dir,
    calculate_dynlibs: true,
    installer: "pyodide.loadPackage",
    source: channel === DEFAULT_CHANNEL ? "pyodide" : channel,
  });

  if (DEBUG) {
    console.debug(
      `Found ${dynlibs.length} dynamic libraries inside ${filename}`,
    );
  }

  await loadDynlibsFromPackage(pkg, dynlibs);
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
async function downloadAndInstall(
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
    const buffer = await downloadPackage(pkg, checkIntegrity);
    const installPromiseDependencies = pkg.depends.map((dependency) => {
      return toLoad.has(dependency)
        ? toLoad.get(dependency)!.done
        : Promise.resolve();
    });
    // Can't install until bootstrap is finalized.
    await API.bootstrapFinalizedPromise;

    // wait until all dependencies are installed
    await Promise.all(installPromiseDependencies);

    await installPackage(pkg.normalizedName, buffer, pkg.channel);

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

const acquirePackageLock = createLock();

function filterPackageData({
  name,
  version,
  file_name,
  package_type,
}: InternalPackageData): PackageData {
  return { name, version, fileName: file_name, packageType: package_type };
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
 * @async
 * @returns The loaded package data.
 */
export async function loadPackage(
  names: string | PyProxy | Array<string>,
  options: {
    messageCallback?: (message: string) => void;
    errorCallback?: (message: string) => void;
    checkIntegrity?: boolean;
  } = {
    checkIntegrity: true,
  },
): Promise<Array<PackageData>> {
  const loadedPackageData = new Set<InternalPackageData>();
  const messageCallback = options.messageCallback || console.log;
  const errorCallback = options.errorCallback || console.error;
  if (names instanceof PyProxy) {
    names = names.toJs();
  }
  if (!Array.isArray(names)) {
    names = [names as string];
  }

  const toLoad = recursiveDependencies(names, errorCallback);

  for (const [_, { name, normalizedName, channel }] of toLoad) {
    const loaded = loadedPackages[name];
    if (loaded === undefined) {
      continue;
    }

    toLoad.delete(normalizedName);
    // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
    // dependency, which was previously overridden.
    if (loaded === channel || channel === DEFAULT_CHANNEL) {
      messageCallback(`${name} already loaded from ${loaded}`);
    } else {
      errorCallback(
        `URI mismatch, attempting to load package ${name} from ${channel} ` +
          `while it is already loaded from ${loaded}. To override a dependency, ` +
          `load the custom package first.`,
      );
    }
  }

  if (toLoad.size === 0) {
    messageCallback("No new packages to load");
    return [];
  }

  const packageNames = Array.from(toLoad.values(), ({ name }) => name)
    .sort()
    .join(", ");
  const failed = new Map<string, Error>();
  const releaseLock = await acquirePackageLock();
  try {
    messageCallback(`Loading ${packageNames}`);
    for (const [_, pkg] of toLoad) {
      if (loadedPackages[pkg.name]) {
        // Handle the race condition where the package was loaded between when
        // we did dependency resolution and when we acquired the lock.
        toLoad.delete(pkg.normalizedName);
        continue;
      }

      // TODO: add support for prefetching modules by awaiting on a promise right
      // here which resolves in loadPyodide when the bootstrap is done.

      pkg.installPromise = downloadAndInstall(
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

    Module.reportUndefinedSymbols();
    if (loadedPackageData.size > 0) {
      const successNames = Array.from(loadedPackageData, (pkg) => pkg.name)
        .sort()
        .join(", ");
      messageCallback(`Loaded ${successNames}`);
    }

    if (failed.size > 0) {
      const failedNames = Array.from(failed.keys()).sort().join(", ");
      messageCallback(`Failed to load ${failedNames}`);
      for (const [name, err] of failed) {
        errorCallback(`The following error occurred while loading ${name}:`);
        errorCallback(err.message);
      }
    }

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    API.importlib.invalidate_caches();
    return Array.from(loadedPackageData, filterPackageData);
  } finally {
    releaseLock();
  }
}

/**
 * The list of packages that Pyodide has loaded.
 * Use ``Object.keys(pyodide.loadedPackages)`` to get the list of names of
 * loaded packages, and ``pyodide.loadedPackages[package_name]`` to access
 * install location for a particular ``package_name``.
 */
export let loadedPackages: { [key: string]: string } = {};
