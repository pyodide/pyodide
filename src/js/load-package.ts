import { Module, API, Tests } from "./module.js";
import { IN_NODE, nodeFsPromisesMod, _loadBinaryFile } from "./compat.js";
import { PyProxy, isPyProxy } from "./pyproxy.gen";

/** @private */
let baseURL: string;
/**
 * Initialize the packages index. This is called as early as possible in
 * loadPyodide so that fetching packages.json can occur in parallel with other
 * operations.
 * @param indexURL
 * @private
 */
export async function initializePackageIndex(indexURL: string) {
  baseURL = indexURL;
  let package_json;
  if (IN_NODE) {
    const package_string = await nodeFsPromisesMod.readFile(
      `${indexURL}packages.json`
    );
    package_json = JSON.parse(package_string);
  } else {
    let response = await fetch(`${indexURL}packages.json`);
    package_json = await response.json();
  }
  if (!package_json.packages) {
    throw new Error(
      "Loaded packages.json does not contain the expected key 'packages'."
    );
  }
  API.packages = package_json.packages;

  // compute the inverted index for imports to package names
  API._import_name_to_package_name = new Map();
  for (let name of Object.keys(API.packages)) {
    for (let import_name of API.packages[name].imports) {
      API._import_name_to_package_name.set(import_name, name);
    }
  }
}

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

/**
 * Recursively add a package and its dependencies to toLoad and toLoadShared.
 * A helper function for recursiveDependencies.
 * @param name The package to add
 * @param toLoad The set of names of packages to load
 * @private
 */
function addPackageToLoad(name: string, toLoad: Map<string, string>) {
  name = name.toLowerCase();
  if (toLoad.has(name)) {
    return;
  }
  const pkg_info = API.packages[name];
  if (!pkg_info) {
    throw new Error(`No known package with name '${name}'`);
  }
  toLoad.set(name, DEFAULT_CHANNEL);
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
 * @returns Two sets, the set of normal dependencies and the set of shared
 * dependencies
 * @private
 */
function recursiveDependencies(
  names: string[],
  errorCallback: (err: string) => void
) {
  const toLoad = new Map();
  for (let name of names) {
    const pkgname = _uri_to_package_name(name);
    if (pkgname === undefined) {
      addPackageToLoad(name, toLoad);
      continue;
    }
    if (toLoad.has(pkgname) && toLoad.get(pkgname) !== name) {
      errorCallback(
        `Loading same package ${pkgname} from ${name} and ${toLoad.get(
          pkgname
        )}`
      );
      continue;
    }
    toLoad.set(pkgname, name);
  }
  return toLoad;
}

//
// Dependency download and install
//

/**
 * Download a package. If `channel` is `DEFAULT_CHANNEL`, look up the wheel URL
 * relative to baseURL from `packages.json`, otherwise use the URL specified by
 * `channel`.
 * @param name The name of the package
 * @param channel Either `DEFAULT_CHANNEL` or the absolute URL to the
 * wheel or the path to the wheel relative to baseURL.
 * @returns The binary data for the package
 * @private
 */
async function downloadPackage(
  name: string,
  channel: string
): Promise<Uint8Array> {
  let file_name;
  if (channel === DEFAULT_CHANNEL) {
    if (!(name in API.packages)) {
      throw new Error(`Internal error: no entry for package named ${name}`);
    }
    file_name = API.packages[name].file_name;
  } else {
    file_name = channel;
  }
  return await _loadBinaryFile(baseURL, file_name);
}

type PromisePair = { promise: Promise<void>; resolve: () => void };

function mkPromise(): PromisePair {
  let resolve;
  let promise: Promise<void> = new Promise((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

/**
 * Install the package into the file system.
 * @param name The name of the package
 * @param buffer The binary data returned by downloadPkgBuffer
 * @private
 */
async function installPackage(
  name: string,
  buffer: Uint8Array,
  pkg_promises: { [name: string]: Promise<void> }
) {
  let pkg = API.packages[name];
  if (!pkg) {
    pkg = {
      file_name: ".whl",
      install_dir: "site",
      shared_library: false,
      depends: [],
      imports: [] as string[],
    };
  }
  const filename = pkg.file_name;
  const dep_pkg_promises: { [dep: string]: Promise<void> } = {};
  for (let dep of pkg.depends) {
    dep_pkg_promises[dep] = pkg_promises[dep];
  }
  // This Python helper function unpacks the buffer and lists out any so files therein.
  const dynlibs: string[] = API.package_loader.unpack_buffer.callKwargs({
    buffer,
    filename,
    target: pkg.install_dir,
    calculate_dynlibs: true,
  });
  let dynlib_promises: { [lib: string]: PromisePair } = {};
  for (let dynlib of dynlibs) {
    dynlib_promises[dynlib.split("/").pop()] = mkPromise();
  }
  await Promise.all(
    dynlibs.map((lib) =>
      installDynlib(lib, pkg.shared, dep_pkg_promises, dynlib_promises)
    )
  );
}

async function installDynlib(
  lib: string,
  shared: boolean,
  pkg_promises: { [dep: string]: Promise<void> },
  dynlib_promises: { [lib: string]: PromisePair }
) {
  const binary = getLibBinary(lib);
  const metadata = Module.getDylinkMetadata(binary);
  for (let dep of metadata.neededDynlibs) {
    // If we have it, can proceed
    if (dep in Module.preloadedWasm) {
      continue;
    }
    // Maybe it's part of this package?
    if (dep in dynlib_promises) {
      await dynlib_promises[dep].promise;
      continue;
    }
    // Else, hope they come from dependencies?
    for (const [dep, dep_promise] of Object.entries(pkg_promises)) {
      await dep_promise;
      if (dep in Module.preloadedWasm) {
        break;
      }
    }
    // If we've finished loading all dependency packages and still don't have it
    // we have to give up.
    if (!(dep in Module.preloadedWasm)) {
      throw new Error(`Library ${lib} is missing dependency ${dep}!`);
    }
  }
  const releaseDynlibLock = await acquireDynlibLock();
  try {
    const module = await Module.loadWebAssemblyModule(binary, {
      loadAsync: true,
      nodelete: true,
      allowUndefined: true,
    });
    Module.preloadedWasm[lib] = module;
    const libname = lib.split("/").pop()!;
    Module.preloadedWasm[libname] = module;
    if (shared) {
      Module.loadDynamicLibrary(lib, {
        global: true,
        nodelete: true,
      });
    }
    dynlib_promises[libname].resolve();
  } catch (e) {
    if (e.message.includes("need to see wasm magic number")) {
      console.warn(
        `Failed to load dynlib ${lib}. We probably just tried to load a linux .so file or something.`
      );
      return;
    }
    throw e;
  } finally {
    releaseDynlibLock();
  }
}

/**
 * @returns A new asynchronous lock
 * @private
 */
function createLock() {
  // This is a promise that is resolved when the lock is open, not resolved when lock is held.
  let _lock = Promise.resolve();

  /**
   * Acquire the async lock
   * @returns A zero argument function that releases the lock.
   * @private
   */
  async function acquireLock() {
    const old_lock = _lock;
    let releaseLock: () => void;
    _lock = new Promise((resolve) => (releaseLock = resolve));
    await old_lock;
    // @ts-ignore
    return releaseLock;
  }
  return acquireLock;
}

// Emscripten has a lock in the corresponding code in library_browser.js. I
// don't know why we need it, but quite possibly bad stuff will happen without
// it.
const acquireDynlibLock = createLock();

function getLibBinary(lib: string): Uint8Array {
  const node = Module.FS.lookupPath(lib).node;
  let byteArray;
  if (node.mount.type == Module.FS.filesystems.MEMFS) {
    byteArray = Module.FS.filesystems.MEMFS.getFileDataAsTypedArray(
      Module.FS.lookupPath(lib).node
    );
  } else {
    byteArray = Module.FS.readFile(lib);
  }
  return byteArray;
}

const acquirePackageLock = createLock();

/**
 * Load a package or a list of packages over the network. This installs the
 * package in the virtual filesystem. The package needs to be imported from
 * Python before it can be used.
 *
 * @param names Either a single package name or
 * URL or a list of them. URLs can be absolute or relative. The URLs must have
 * file name ``<package-name>.js`` and there must be a file called
 * ``<package-name>.data`` in the same directory. The argument can be a
 * ``PyProxy`` of a list, in which case the list will be converted to JavaScript
 * and the ``PyProxy`` will be destroyed.
 * @param messageCallback A callback, called with progress messages
 *    (optional)
 * @param errorCallback A callback, called with error/warning messages
 *    (optional)
 * @async
 */
export async function loadPackage(
  names: string | PyProxy | Array<string>,
  messageCallback?: (msg: string) => void,
  errorCallback?: (msg: string) => void
) {
  messageCallback = messageCallback || console.log;
  errorCallback = errorCallback || console.error;
  if (isPyProxy(names)) {
    names = names.toJs();
  }
  if (!Array.isArray(names)) {
    names = [names as string];
  }

  const toLoad = recursiveDependencies(names, errorCallback);

  for (const [pkg, uri] of toLoad) {
    const loaded = loadedPackages[pkg];
    if (loaded === undefined) {
      continue;
    }
    toLoad.delete(pkg);
    // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
    // dependency, which was previously overridden.
    if (loaded === uri || uri === DEFAULT_CHANNEL) {
      messageCallback(`${pkg} already loaded from ${loaded}`);
    } else {
      errorCallback(
        `URI mismatch, attempting to load package ${pkg} from ${uri} ` +
          `while it is already loaded from ${loaded}. To override a dependency, ` +
          `load the custom package first.`
      );
    }
  }

  if (toLoad.size === 0) {
    messageCallback("No new packages to load");
    return;
  }

  const packageNames = Array.from(toLoad.keys()).sort().join(", ");
  const releaseLock = await acquirePackageLock();
  try {
    messageCallback(`Loading ${packageNames}`);
    const packageLoadPromises: { [name: string]: Promise<Uint8Array> } = {};
    for (const [name, channel] of toLoad) {
      if (loadedPackages[name]) {
        // Handle the race condition where the package was loaded between when
        // we did dependency resolution and when we acquired the lock.
        toLoad.delete(name);
        continue;
      }
      packageLoadPromises[name] = downloadPackage(name, channel);
    }

    const loaded: string[] = [];
    const failed: { [name: string]: any } = {};
    // TODO: add support for prefetching modules by awaiting on a promise right
    // here which resolves in loadPyodide when the bootstrap is done.
    const packageInstallPromises: { [name: string]: Promise<void> } = {};
    const packageInstallResolves: { [name: string]: () => void } = {};
    for (const name of toLoad.keys()) {
      const { promise, resolve } = mkPromise();
      packageInstallPromises[name] = promise;
      packageInstallResolves[name] = resolve;
    }
    for (const [name, channel] of toLoad) {
      packageLoadPromises[name].then(async (buffer) => {
        try {
          await installPackage(name, buffer, packageInstallPromises);
        } catch (err) {
          failed[name] = err;
          return;
        } finally {
          packageInstallResolves[name]();
        }
        loaded.push(name);
        loadedPackages[name] = channel;
      });
    }
    await Promise.all(Object.values(packageInstallPromises));

    Module.reportUndefinedSymbols();
    if (loaded.length > 0) {
      const successNames = loaded.sort().join(", ");
      messageCallback(`Loaded ${successNames}`);
    }
    if (Object.keys(failed).length > 0) {
      const failedNames = Object.keys(failed).sort().join(", ");
      messageCallback(`Failed to load ${failedNames}`);
      for (const [name, err] of Object.entries(failed)) {
        console.warn(`The following error occurred while loading ${name}:`);
        console.error(err);
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
