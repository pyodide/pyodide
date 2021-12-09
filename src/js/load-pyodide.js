import { Module } from "./module.js";

const IN_NODE =
  typeof process !== "undefined" &&
  process.release &&
  process.release.name === "node" &&
  typeof process.browser ===
    "undefined"; /* This last condition checks if we run the browser shim of process */

/** @typedef {import('./pyproxy.js').PyProxy} PyProxy */
/** @private */
let baseURL;
/**
 * @param {string} indexURL
 * @private
 */
export async function initializePackageIndex(indexURL) {
  baseURL = indexURL;
  let package_json;
  if (IN_NODE) {
    const fsPromises = await import(/* webpackIgnore: true */ "fs/promises");
    const package_string = await fsPromises.readFile(
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
  Module.packages = package_json.packages;

  // compute the inverted index for imports to package names
  Module._import_name_to_package_name = new Map();
  for (let name of Object.keys(Module.packages)) {
    for (let import_name of Module.packages[name].imports) {
      Module._import_name_to_package_name.set(import_name, name);
    }
  }
}

function addPackageToLoad(name, toLoad, toLoadShared) {
  name = name.toLowerCase();
  if (toLoad.has(name)) {
    return;
  }
  let pkg_info = Module.packages[name];
  if (!pkg_info) {
    throw new Error("Oops?");
  }
  if (pkg.shared_library) {
    toLoadShared.add(name);
  } else {
    toLoad.add(name);
  }
  for (let dep_name of pkg_info.depends) {
    addPackageToLoad(dep_name, toLoad);
  }
}

function recursiveDependencies(names) {
  const toLoad = new Set();
  const toLoadShared = new Set();
  for (let name of names) {
    addPackageToLoad(name, toLoad, toLoadShared);
  }
  return [toLoad, toLoadShared];
}

async function _loadPackage(pkg) {
  const coroutine = Module.package_loader.load_package(
    `${baseURL}${pkg.file_name}`,
    pkg.name,
    pkg.shared_library
  );
  try {
    await coroutine;
  } finally {
    coroutine.destroy();
  }
}

/**
 * Load a package or a list of packages over the network. This installs the
 * package in the virtual filesystem. The package needs to be imported from
 * Python before it can be used.
 *
 * @param {string | string[] | PyProxy} names Either a single package name or
 * URL or a list of them. URLs can be absolute or relative. The URLs must have
 * file name ``<package-name>.js`` and there must be a file called
 * ``<package-name>.data`` in the same directory. The argument can be a
 * ``PyProxy`` of a list, in which case the list will be converted to JavaScript
 * and the ``PyProxy`` will be destroyed.
 * @param {LogFn=} messageCallback A callback, called with progress messages
 *    (optional)
 * @param {LogFn=} errorCallback A callback, called with error/warning messages
 *    (optional)
 * @async
 */
export async function loadPackage(names, messageCallback, errorCallback) {
  if (Module.isPyProxy(names)) {
    names = names.toJs();
  }
  if (!Array.isArray(names)) {
    names = [names];
  }

  let [toLoad, toLoadShared] = recursiveDependencies(
    names,
    messageCallback,
    errorCallback
  );
  if (toLoad.size === 0 && toLoadShared.size == 0) {
    messageCallback("No new packages to load");
    return;
  }

  let packageNames = [...toLoad.keys(), ...toLoadShared.keys()].join(", ");
  let releaseLock = await acquirePackageLock();
  try {
    messageCallback(`Loading ${packageNames}`);
    let sharedLibraryPromises = [];
    for (let name of toLoadShared) {
      sharedLibraryPromises.push(_loadPackage(Module.packages[name]));
    }

    await Promise.all(sharedLibraryPromises);

    let packagePromises = [];
    for (let name of toLoad) {
      packagePromises.push(_loadPackage(Module.packages[name]));
    }
    await Promise.all(packagePromises);

    Module.reportUndefinedSymbols();
    messageCallback(`Loaded ${packageNames}`);

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    Module.importlib.invalidate_caches();
  } finally {
    restoreOrigWasmPlugin();
    releaseLock();
  }
}

Module.loadDynlib = async function (lib, shared) {
  let releaseDynlibLock = await acquireDynlibLock();
  try {
    const module = await loadWebAssemblyModule(byteArray, {
      loadAsync: true,
      nodelete: true,
    });
    if (shared) {
      // await
    }
    Module.preloadedWasm[lib] = module;
  } finally {
    releaseDynlibLock();
  }
};

// This is a promise that is resolved iff there are no pending package loads. It
// never fails.
let _dynlibLock = Promise.resolve();

/**
 * An async lock for package loading. Prevents race conditions in loadPackage.
 * @returns A zero argument function that releases the lock.
 * @private
 */
async function acquireDynlibLock() {
  let old_lock = _dynlibLock;
  let releaseLock;
  _dynlibLock = new Promise((resolve) => (releaseLock = resolve));
  await old_lock;
  return releaseLock;
}

// This is a promise that is resolved iff there are no pending package loads. It
// never fails.
let _package_lock = Promise.resolve();

/**
 * An async lock for package loading. Prevents race conditions in loadPackage.
 * @returns A zero argument function that releases the lock.
 * @private
 */
async function acquirePackageLock() {
  let old_lock = _package_lock;
  let releaseLock;
  _package_lock = new Promise((resolve) => (releaseLock = resolve));
  await old_lock;
  return releaseLock;
}

/**
 *
 * The list of packages that Pyodide has loaded.
 * Use ``Object.keys(pyodide.loadedPackages)`` to get the list of names of
 * loaded packages, and ``pyodide.loadedPackages[package_name]`` to access
 * install location for a particular ``package_name``.
 *
 * @type {object}
 */
export let loadedPackages = {};
