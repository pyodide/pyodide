declare var Module: any;
declare var Tests: any;
declare var API: any;
declare var DEBUG: boolean;

import {
  IN_NODE,
  nodeFsPromisesMod,
  loadBinaryFile,
  initNodeModules,
  resolvePath,
} from "./compat.js";
import { createLock } from "./lock";
import { loadDynlibsFromPackage } from "./dynload";
import { PyProxy } from "./pyproxy.gen";
import { makeWarnOnce } from "./util";

/**
 * Initialize the packages index. This is called as early as possible in
 * loadPyodide so that fetching pyodide-lock.json can occur in parallel with other
 * operations.
 * @param lockFileURL
 * @private
 */
async function initializePackageIndex(lockFileURL: string) {
  let lockfile;
  if (IN_NODE) {
    await initNodeModules();
    const package_string = await nodeFsPromisesMod.readFile(lockFileURL);
    lockfile = JSON.parse(package_string);
  } else {
    let response = await fetch(lockFileURL);
    lockfile = await response.json();
  }
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
  API._import_name_to_package_name = new Map();
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
}

API.packageIndexReady = initializePackageIndex(API.config.lockFileURL);

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
// Regexp for validating package name and URI
const package_uri_regexp = /^.*?([^\/]*)\.whl$/;

function _uri_to_package_name(package_uri: string): string | undefined {
  let match = package_uri_regexp.exec(package_uri);
  if (match) {
    let wheel_name = match[1].toLowerCase();
    return wheel_name.split("-").slice(0, -4).join("-");
  }
}

type PackageLoadMetadata = {
  name: string;
  channel: string;
  depends: string[];
  done: ResolvablePromise;
  installPromise?: Promise<void>;
};

// Package data inside pyodide-lock.json
export type PackageData = {
  file_name: string;
  shared_library: boolean;
  depends: string[];
  imports: string[];
  install_dir: string;
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
  name = name.toLowerCase();
  if (toLoad.has(name)) {
    return;
  }
  const pkg_info: PackageData = API.lockfile_packages[name];
  if (!pkg_info) {
    throw new Error(`No known package with name '${name}'`);
  }

  toLoad.set(name, {
    name: name,
    channel: DEFAULT_CHANNEL,
    depends: pkg_info.depends,
    installPromise: undefined,
    done: createDonePromise(),
  });

  // If the package is already loaded, we don't add dependencies, but warn
  // the user later. This is especially important if the loaded package is
  // from a custom url, in which case adding dependencies is wrong.
  if (loadedPackages[name] !== undefined) {
    return;
  }

  for (let dep_name of pkg_info.depends) {
    addPackageToLoad(dep_name, toLoad);
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
    const pkgname = _uri_to_package_name(name);
    if (pkgname === undefined) {
      addPackageToLoad(name, toLoad);
      continue;
    }

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
      channel: channel, // name is url in this case
      depends: [],
      installPromise: undefined,
      done: createDonePromise(),
    });
  }
  return toLoad;
}

//
// Dependency download and install
//

/**
 * Download a package. If `channel` is `DEFAULT_CHANNEL`, look up the wheel URL
 * relative to packageCacheDir (when IN_NODE), or indexURL from `pyodide-lock.json`, otherwise use the URL specified by
 * `channel`.
 * @param name The name of the package
 * @param channel Either `DEFAULT_CHANNEL` or the absolute URL to the
 * wheel or the path to the wheel relative to packageCacheDir (when IN_NODE), or indexURL.
 * @param checkIntegrity Whether to check the integrity of the downloaded
 * package.
 * @returns The binary data for the package
 * @private
 */
async function downloadPackage(
  name: string,
  channel: string,
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

  let file_name, uri, file_sub_resource_hash;
  if (channel === DEFAULT_CHANNEL) {
    if (!(name in API.lockfile_packages)) {
      throw new Error(`Internal error: no entry for package named ${name}`);
    }
    file_name = API.lockfile_packages[name].file_name;
    uri = resolvePath(file_name, installBaseUrl);
    file_sub_resource_hash = API.package_loader.sub_resource_hash(
      API.lockfile_packages[name].sha256,
    );
  } else {
    uri = channel;
    file_sub_resource_hash = undefined;
  }

  if (!checkIntegrity) {
    file_sub_resource_hash = undefined;
  }
  try {
    return await loadBinaryFile(uri, file_sub_resource_hash);
  } catch (e) {
    if (!IN_NODE || channel !== DEFAULT_CHANNEL) {
      throw e;
    }
  }
  console.log(
    `Didn't find package ${file_name} locally, attempting to load from ${cdnURL}`,
  );
  // If we are IN_NODE, download the package from the cdn, then stash it into
  // the node_modules directory for future use.
  let binary = await loadBinaryFile(cdnURL + file_name);
  console.log(
    `Package ${file_name} loaded from ${cdnURL}, caching the wheel in node_modules for future use.`,
  );
  await nodeFsPromisesMod.writeFile(uri, binary);
  return binary;
}

/**
 * Install the package into the file system.
 * @param name The name of the package
 * @param buffer The binary data returned by downloadPackage
 * @private
 */
async function installPackage(
  name: string,
  buffer: Uint8Array,
  channel: string,
) {
  let pkg: PackageData = API.lockfile_packages[name];
  if (!pkg) {
    pkg = {
      file_name: ".whl",
      shared_library: false,
      depends: [],
      imports: [] as string[],
      install_dir: "site",
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
 * @param name The name of the package
 * @param toLoad The map of package names to PackageLoadMetadata
 * @param loaded The set of loaded package names, this will be updated by this function.
 * @param failed The map of <failed package name, error message>, this will be updated by this function.
 * @param checkIntegrity Whether to check the integrity of the downloaded
 * package.
 * @private
 */
async function downloadAndInstall(
  name: string,
  toLoad: Map<string, PackageLoadMetadata>,
  loaded: Set<string>,
  failed: Map<string, Error>,
  checkIntegrity: boolean = true,
) {
  if (loadedPackages[name] !== undefined) {
    return;
  }

  const pkg = toLoad.get(name)!;

  try {
    const buffer = await downloadPackage(pkg.name, pkg.channel, checkIntegrity);
    const installPromisDependencies = pkg.depends.map((dependency) => {
      return toLoad.has(dependency)
        ? toLoad.get(dependency)!.done
        : Promise.resolve();
    });

    // wait until all dependencies are installed
    await Promise.all(installPromisDependencies);

    await installPackage(pkg.name, buffer, pkg.channel);
    loaded.add(pkg.name);
    loadedPackages[pkg.name] = pkg.channel;
  } catch (err: any) {
    failed.set(name, err);
    // We don't throw error when loading a package fails, but just report it.
    // pkg.done.reject(err);
  } finally {
    pkg.done.resolve();
  }
}

const acquirePackageLock = createLock();

const cbDeprecationWarnOnce = makeWarnOnce(
  "Passing a messageCallback (resp. errorCallback) as the second (resp. third) argument to loadPackage " +
    "is deprecated and will be removed in v0.24. Instead use:\n" +
    "   { messageCallback : callbackFunc }",
);

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
 * either pure Python wheels, with a file name ending with `none-any.whl`
 * or Emscripten/WASM 32 wheels, with a file name ending with
 * `cp<pyversion>_emscripten_<em_version>_wasm32.whl`.
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
 * @param errorCallbackDeprecated @ignore
 * @async
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
  errorCallbackDeprecated?: (message: string) => void,
) {
  if (typeof options === "function") {
    cbDeprecationWarnOnce();
    options = {
      messageCallback: options,
      errorCallback: errorCallbackDeprecated,
    };
  }

  const messageCallback = options.messageCallback || console.log;
  const errorCallback = options.errorCallback || console.error;
  if (names instanceof PyProxy) {
    names = names.toJs();
  }
  if (!Array.isArray(names)) {
    names = [names as string];
  }

  const toLoad = recursiveDependencies(names, errorCallback);

  for (const [pkg, pkg_metadata] of toLoad) {
    const loaded = loadedPackages[pkg];
    if (loaded === undefined) {
      continue;
    }
    toLoad.delete(pkg);
    // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
    // dependency, which was previously overridden.
    if (
      loaded === pkg_metadata.channel ||
      pkg_metadata.channel === DEFAULT_CHANNEL
    ) {
      messageCallback(`${pkg} already loaded from ${loaded}`);
    } else {
      errorCallback(
        `URI mismatch, attempting to load package ${pkg} from ${pkg_metadata.channel} ` +
          `while it is already loaded from ${loaded}. To override a dependency, ` +
          `load the custom package first.`,
      );
    }
  }

  if (toLoad.size === 0) {
    messageCallback("No new packages to load");
    return;
  }

  const packageNames = [...toLoad.keys()].join(", ");
  const loaded = new Set<string>();
  const failed = new Map<string, Error>();
  const releaseLock = await acquirePackageLock();
  try {
    messageCallback(`Loading ${packageNames}`);
    for (const [name] of toLoad) {
      if (loadedPackages[name]) {
        // Handle the race condition where the package was loaded between when
        // we did dependency resolution and when we acquired the lock.
        toLoad.delete(name);
        continue;
      }

      // TODO: add support for prefetching modules by awaiting on a promise right
      // here which resolves in loadPyodide when the bootstrap is done.
      toLoad.get(name)!.installPromise = downloadAndInstall(
        name,
        toLoad,
        loaded,
        failed,
        options.checkIntegrity,
      );
    }

    await Promise.all(
      Array.from(toLoad.values()).map(({ installPromise }) => installPromise),
    );

    Module.reportUndefinedSymbols();
    if (loaded.size > 0) {
      const successNames = Array.from(loaded).join(", ");
      messageCallback(`Loaded ${successNames}`);
    }

    if (failed.size > 0) {
      const failedNames = Array.from(failed.keys()).join(", ");
      messageCallback(`Failed to load ${failedNames}`);
      for (const [name, err] of failed) {
        errorCallback(`The following error occurred while loading ${name}:`);
        errorCallback(err.message);
      }
    }

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    API.importlib.invalidate_caches();
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
