import { Module } from "./module.js";

//
// Initialization code and node/browser shims
//

// Detect if we're in node
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

/**
 * If we're in node, it's most convenient to import various node modules on
 * initialization. Otherwise, this does nothing.
 * @private
 */
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
 * Initialize the packages index. This is called as early as possible in
 * loadPyodide so that fetching packages.json can occur in parallel with other
 * operations.
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

/**
 * Load a binary file, only for use in Node. If the path explicitly is a URL,
 * then fetch from a URL, else load from the file system.
 * @param {str} indexURL base path to resolve relative paths
 * @param {str} path the path to load
 * @returns An ArrayBuffer containing the binary data
 * @private
 */
async function node_loadBinaryFile(indexURL, path) {
  if (path.includes("://")) {
    let response = await nodeFetch(path);
    if (!response.ok) {
      throw new Error(`Failed to load '${path}': request failed.`);
    }
    return await response.arrayBuffer();
  } else {
    const data = await nodeFsPromisesMod.readFile(`${indexURL}${path}`);
    return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
  }
}

/**
 * Load a binary file, only for use in browser. Resolves relative paths against
 * indexURL.
 *
 * @param {str} indexURL base path to resolve relative paths
 * @param {str} path the path to load
 * @returns An ArrayBuffer containing the binary data
 * @private
 */
async function browser_loadBinaryFile(indexURL, path) {
  const base = new URL(indexURL, location);
  const url = new URL(path, base);
  let response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load '${url}': request failed.`);
  }
  return new Uint8Array(await response.arrayBuffer());
}

export let _loadBinaryFile;
if (IN_NODE) {
  _loadBinaryFile = node_loadBinaryFile;
} else {
  _loadBinaryFile = browser_loadBinaryFile;
}

/**
 * Load a text file and executes it as Javascript
 * @param {str} url The path to load. May be a url or a relative file system path.
 * @private
 */
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
 * Currently loadScript is only used once to load `pyodide.asm.js`.
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

//
// Dependency resolution
//
const DEFAULT_CHANNEL = "default channel";
const package_uri_regexp = /^.*?([^\/]*)\.whl$/;

function _uri_to_package_name(package_uri) {
  let match = package_uri_regexp.exec(package_uri);
  if (match) {
    let wheel_name = match[1].toLowerCase();
    return wheel_name.split("-").slice(0, -4).join("-");
  }
}

/**
 * Recursively add a package and its dependencies to toLoad and toLoadShared.
 * A helper function for recursiveDependencies.
 * @param {str} name The package to add
 * @param {Set} toLoad The set of names of packages to load
 * @param {Set} toLoadShared The set of names of shared libraries to load
 * @private
 */
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
    toLoadShared.set(name, DEFAULT_CHANNEL);
  } else {
    toLoad.set(name, DEFAULT_CHANNEL);
  }
  for (let dep_name of pkg_info.depends) {
    addPackageToLoad(dep_name, toLoad, toLoadShared);
  }
}

/**
 * Calculate the dependencies of a set of packages
 * @param names The list of names whose dependencies we need to calculate.
 * @returns Two sets, the set of normal dependencies and the set of shared
 * dependencies
 * @private
 */
function recursiveDependencies(names) {
  const toLoad = new Map();
  const toLoadShared = new Map();
  for (let name of names) {
    const pkgname = _uri_to_package_name(name);
    if(pkgname === undefined){
      addPackageToLoad(name, toLoad, toLoadShared);
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
  return [toLoad, toLoadShared];
}

//
// Dependency download and install
//

/**
 * Download a package.
 * @param {str} name The name of the package
 * @returns {ArrayBuffer} The binary data for the package
 * @private
 */
async function downloadPackage(name) {
  let file_name;
  if(name in Module.packages){
    file_name = Module.packages[name].file_name;
  } else {
    file_name = name;
  }
  let result = await _loadBinaryFile(baseURL, file_name);
  return result;
}

/**
 * Install the package into the file system.
 * @param {str} name The name of the package
 * @param {str} buffer The binary data returned by downloadPkgBuffer
 * @private
 */
async function installPackage(name, buffer) {
  const pkg = Module.packages[name];
  const file_name = pkg.file_name;
  // This Python helper function unpacks the buffer and lists out any so files therein.
  const dynlibs = Module.package_loader.unpack_buffer(
    file_name,
    buffer,
    pkg.install_dir
  );
  for (let dynlib of dynlibs) {
    await loadDynlib(dynlib, pkg.shared_library);
  }
  loadedPackages[name] = pkg;
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
    let old_lock = _lock;
    let releaseLock;
    _lock = new Promise((resolve) => (releaseLock = resolve));
    await old_lock;
    return releaseLock;
  }
  return acquireLock;
}

// Emscripten has a lock in the corresponding code in library_browser.js. I
// don't know why we need it, but quite possibly bad stuff will happen without
// it.
const acquireDynlibLock = createLock();

/**
 * Load a dynamic library. This is an async operation and Python imports are
 * synchronous so we have to do it ahead of time. When we add more support for
 * synchronous I/O, we could consider doing this later as a part of a Python
 * import hook.
 *
 * @param {str} lib The file system path to the library.
 * @param {bool} shared Is this a shared library or not?
 * @private
 */
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

const acquirePackageLock = createLock();

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
    for (const name of toLoadShared.keys()) {
      if (loadedPackages[name]) {
        // Handle the race condition where the package was loaded between when
        // we did dependency resolution and when we acquired the lock.
        toLoadShared.delete(name);
        continue;
      }
      sharedLibraryPromises[name] = downloadPackage(name);
    }
    for (const name of toLoad.keys()) {
      if (loadedPackages[name]) {
        // Handle the race condition where the package was loaded between when
        // we did dependency resolution and when we acquired the lock.
        toLoad.delete(name);
        continue;
      }
      packagePromises[name] = downloadPackage(name);
    }

    const loaded = [];
    const failed = {};
    // TODO: add support for prefetching modules by awaiting on a promise right
    // here which resolves in loadPyodide when the bootstrap is done.
    for (const name of toLoadShared.keys()) {
      sharedLibraryPromises[name] = sharedLibraryPromises[name]
        .then(async (buffer) => {
          await installPackage(name, buffer);
          loaded.push(name);
          loadedPackages[name] = DEFAULT_CHANNEL;
        })
        .catch((err) => {
          failed[name] = err;
        });
    }

    await Promise.all(Object.values(sharedLibraryPromises));
    for (const name of toLoad.keys()) {
      packagePromises[name] = packagePromises[name]
        .then(async (buffer) => {
          await installPackage(name, buffer);
          loaded.push(name);
          loadedPackages[name] = DEFAULT_CHANNEL;
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
        console.error(err.toString());
      }
    }

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    Module.importlib.invalidate_caches();
  } finally {
    releaseLock();
  }
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
