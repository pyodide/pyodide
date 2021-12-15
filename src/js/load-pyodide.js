import { Module } from "./module.js";

const IN_NODE =
  typeof process !== "undefined" &&
  process.release &&
  process.release.name === "node" &&
  typeof process.browser ===
    "undefined"; /* This last condition checks if we run the browser shim of process */

let nodePathMod;
let nodeFetch;
let nodeFsPromisesMod;
let nodeVmMod;

export async function initNodeModules() {
  if (!IN_NODE) {
    return;
  }
  nodePathMod = (await import(/* webpackIgnore: true */ "path")).default;
  nodeFsPromisesMod = await import(/* webpackIgnore: true */ "fs/promises");
  nodeFetch = (await import(/* webpackIgnore: true */ "node-fetch")).default;
  nodeVmMod = (await import(/* webpackIgnore: true */ "vm")).default;
}

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
  Module.packages = package_json.packages;

  // compute the inverted index for imports to package names
  Module._import_name_to_package_name = new Map();
  for (let name of Object.keys(Module.packages)) {
    for (let import_name of Module.packages[name].imports) {
      Module._import_name_to_package_name.set(import_name, name);
    }
  }
}

Module.locateFile = function (path) {
  return baseURL + path;
};

async function node_loadBinaryFile(indexURL, path) {
  if (path.includes("://")) {
    let response = await nodeFetch(path);
    if (!response.ok) {
      throw new Error(`Failed to load '${path}': request failed.`);
    }
    return await response.arrayBuffer();
  } else {
    const data = await nodeFsPromisesMod.readFile(`${indexURL}${path}`);
    return data.buffer;
  }
}

function getFetch() {
  if (IN_NODE) {
    return nodeFetch;
  } else {
    return fetch;
  }
}

async function _fetchBinaryFile(indexURL, path) {
  let fetch = getFetch();
  let response = await fetch(`${indexURL}${path}`);
  if (!response.ok) {
    throw new Error(`Failed to load '${indexURL}${path}': request failed.`);
  }
  return await response.arrayBuffer();
}

export let _loadBinaryFile;
if (IN_NODE) {
  _loadBinaryFile = node_loadBinaryFile;
} else {
  _loadBinaryFile = _fetchBinaryFile;
}

async function nodeLoadScript(url) {
  if (url.includes("://")) {
    // If it's a url, load it with fetch and then eval it.
    nodeVmMod.runInThisContext(await (await nodeFetch(url)).text());
  } else {
    // Otherwise, hopefully it is a relative path we can load from the file
    // system.
    await import(nodePathMod.resolve(url));
  }
}

/**
 * @param {string) url
 * @async
 * @private
 */
export let loadScript;
if (globalThis.document) {
  // browser
  loadScript = async (url) => await import(/* webpackIgnore: true */ url);
} else if (globalThis.importScripts) {
  // webworker
  loadScript = async (url) => {
    // This is async only for consistency
    globalThis.importScripts(url);
  };
} else if (IN_NODE) {
  loadScript = nodeLoadScript;
} else {
  throw new Error("Cannot determine runtime environment");
}

function addPackageToLoad(name, toLoad, toLoadShared) {
  name = name.toLowerCase();
  if (name in loadedPackages) {
    return;
  }
  if (toLoad.has(name)) {
    return;
  }
  let pkg_info = Module.packages[name];
  if (!pkg_info) {
    throw new Error(`No known package with name ${name}`);
  }
  if (pkg_info.shared_library) {
    toLoadShared.add(name);
  } else {
    toLoad.add(name);
  }
  for (let dep_name of pkg_info.depends) {
    addPackageToLoad(dep_name, toLoad, toLoadShared);
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

async function downloadPkgBuffer(name) {
  const pkg = Module.packages[name];
  return await _loadBinaryFile(baseURL, pkg.file_name);
}

async function unpackBuffer(name, buffer) {
  const pkg = Module.packages[name];
  const file_name = pkg.file_name;
  const dynlibs = Module.package_loader.unpack_buffer(file_name, buffer);
  for (let dynlib of dynlibs) {
    await loadDynlib(dynlib, pkg.shared_library);
  }
  loadedPackages[name] = pkg;
}

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

async function loadDynlib(lib, shared) {
  const byteArray = Module.FS.lookupPath(lib).node.contents;
  const releaseDynlibLock = await acquireDynlibLock();
  try {
    const module = await Module.loadWebAssemblyModule(byteArray, {
      loadAsync: true,
      nodelete: true,
    });
    Module.preloadedWasm[lib] = module;
    if (shared) {
      Module.loadDynamicLibrary(lib, {
        global: true,
        nodelete: true,
      });
    }
  } finally {
    releaseDynlibLock();
  }
}

/**
 * @callback LogFn
 * @param {string} msg
 * @returns {void}
 * @private
 */

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
  messageCallback = messageCallback || console.log;
  errorCallback = errorCallback || console.error;
  if (Module.isPyProxy(names)) {
    names = names.toJs();
  }
  if (!Array.isArray(names)) {
    names = [names];
  }

  const [toLoad, toLoadShared] = recursiveDependencies(
    names,
    messageCallback,
    errorCallback
  );
  if (toLoad.size === 0 && toLoadShared.size == 0) {
    messageCallback("No new packages to load");
    return;
  }

  const packageNames = [...toLoad.keys(), ...toLoadShared.keys()].join(", ");
  const releaseLock = await acquirePackageLock();
  try {
    messageCallback(`Loading ${packageNames}`);
    const sharedLibraryPromises = {};
    const packagePromises = {};
    for (const name of toLoadShared) {
      sharedLibraryPromises[name] = downloadPkgBuffer(name);
    }
    for (const name of toLoad) {
      packagePromises[name] = downloadPkgBuffer(name);
    }

    const loaded = [];
    const failed = {};
    // TODO: At some point add support for prefetching modules by awaiting on a
    // promise right here which resolves in loadPyodide when the bootstrap is done.
    for (const name of toLoadShared) {
      sharedLibraryPromises[name] = sharedLibraryPromises[name]
        .then(async (buffer) => {
          await unpackBuffer(name, buffer);
          loaded.push(name);
          loadedPackages[name] = "pyodide";
        })
        .catch((err) => {
          failed[name] = err;
        });
    }

    await Promise.all(Object.values(sharedLibraryPromises));

    for (const name of toLoad) {
      packagePromises[name] = packagePromises[name]
        .then(async (buffer) => {
          await unpackBuffer(name, buffer);
          loaded.push(name);
          loadedPackages[name] = "pyodide";
        })
        .catch((err) => {
          failed[name] = err;
        });
    }
    await Promise.all(Object.values(packagePromises));

    Module.reportUndefinedSymbols();
    if (loaded.length > 0) {
      const successNames = loaded.join(", ");
      messageCallback(`Loaded ${successNames}`);
    }
    if (Object.keys(failed).length > 0) {
      const failedNames = Object.keys(failed).join(", ");
      messageCallback(`Failed to load ${failedNames}`);
      for (let [name, err] of Object.entries(failed)) {
        console.warn(`The following error occurred while loading ${name}:`);
        console.error(err);
        throw err;
      }
    }

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    Module.importlib.invalidate_caches();
  } finally {
    releaseLock();
  }
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
