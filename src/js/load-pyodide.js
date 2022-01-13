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
    // If it's a url, load it with fetch then eval it.
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

//
// Dependency resolution
//
const DEFAULT_CHANNEL = "default channel";

// Regexp for validating package name and URI
const package_uri_regexp = /^.*?([^\/]*)\.js$/;

function _uri_to_package_name(package_uri) {
  let match = package_uri_regexp.exec(package_uri);
  if (match) {
    return match[1].toLowerCase();
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
  if (toLoad.has(name)) {
    return;
  }
  const pkg_info = Module.packages[name];
  if (!pkg_info) {
    throw new Error(`No known package with name '${name}'`);
  }
  if (pkg_info.shared_library) {
    toLoadShared.set(name, DEFAULT_CHANNEL);
  } else {
    toLoad.set(name, DEFAULT_CHANNEL);
  }
  // If the package is already loaded, we don't add dependencies, but warn
  // the user later. This is especially important if the loaded package is
  // from a custom url, in which case adding dependencies is wrong.
  if (loadedPackages[name] !== undefined) {
    return;
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
function recursiveDependencies(names, errorCallback) {
  const toLoad = new Map();
  const toLoadShared = new Map();
  for (let name of names) {
    const pkgname = _uri_to_package_name(name);
    if (pkgname === undefined) {
      addPackageToLoad(name.toLowerCase(), toLoad, toLoadShared);
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

// locateFile is the function used by the .js file to locate the .data file
// given the filename
Module.locateFile = function (path) {
  // handle packages loaded from custom URLs
  let pkg = path.replace(/\.data$/, "");
  const toLoad = Module.locateFile_packagesToLoad;
  if (toLoad && toLoad.has(pkg)) {
    let package_uri = toLoad.get(pkg);
    if (package_uri != DEFAULT_CHANNEL) {
      return package_uri.replace(/\.js$/, ".data");
    }
  }
  return baseURL + path;
};

// When the JS loads, it synchronously adds a runDependency to emscripten. It
// then loads the data file, and removes the runDependency from emscripten.
// This function returns a promise that resolves when there are no pending
// runDependencies.
function waitRunDependency() {
  const promise = new Promise((r) => {
    Module.monitorRunDependencies = (n) => {
      if (n === 0) {
        r();
      }
    };
  });
  // If there are no pending dependencies left, monitorRunDependencies will
  // never be called. Since we can't check the number of dependencies,
  // manually trigger a call.
  Module.addRunDependency("dummy");
  Module.removeRunDependency("dummy");
  return promise;
}

let sharedLibraryWasmPlugin;
let origWasmPlugin;
let wasmPluginIndex;
function initSharedLibraryWasmPlugin() {
  for (let p in Module.preloadPlugins) {
    if (Module.preloadPlugins[p].canHandle("test.so")) {
      origWasmPlugin = Module.preloadPlugins[p];
      wasmPluginIndex = p;
      break;
    }
  }
  sharedLibraryWasmPlugin = {
    canHandle: origWasmPlugin.canHandle,
    handle(byteArray, name, onload, onerror) {
      origWasmPlugin.handle(byteArray, name, onload, onerror);
      origWasmPlugin.asyncWasmLoadPromise = (async () => {
        await origWasmPlugin.asyncWasmLoadPromise;
        Module.loadDynamicLibrary(name, {
          global: true,
          nodelete: true,
        });
      })();
    },
  };
}

// override the load plugin so that it calls "Module.loadDynamicLibrary" on any
// .so files.
// this only needs to be done for shared library packages because we assume that
// if a package depends on a shared library it needs to have access to it. not
// needed for .so in standard module because those are linked together
// correctly, it is only where linking goes across modules that it needs to be
// done. Hence, we only put this extra preload plugin in during the shared
// library load
function useSharedLibraryWasmPlugin() {
  if (!sharedLibraryWasmPlugin) {
    initSharedLibraryWasmPlugin();
  }
  Module.preloadPlugins[wasmPluginIndex] = sharedLibraryWasmPlugin;
}

function restoreOrigWasmPlugin() {
  Module.preloadPlugins[wasmPluginIndex] = origWasmPlugin;
}

/**
 * @callback LogFn
 * @param {string} msg
 * @returns {void}
 * @private
 */

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

  const [toLoad, toLoadShared] = recursiveDependencies(names, errorCallback);
  if (toLoad.size === 0 && toLoadShared.size === 0) {
    messageCallback("No new packages to load");
    return;
  }

  for (let [pkg, uri] of [...toLoad, ...toLoadShared]) {
    let loaded = loadedPackages[pkg];
    if (loaded === undefined) {
      continue;
    }
    toLoad.delete(pkg);
    toLoadShared.delete(pkg);
    // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
    // depedency, which was previously overridden.
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

  const packageNames = [...toLoad.keys(), ...toLoadShared.keys()].join(", ");
  let releaseLock = await acquirePackageLock();
  try {
    messageCallback(`Loading ${packageNames}`);
    let scriptPromises = [];
    const loaded = [];
    const failed = {};

    useSharedLibraryWasmPlugin();
    for (const [pkg, uri] of toLoadShared) {
      const pkgname =
        (Module.packages[pkg] && Module.packages[pkg].name) || pkg;
      const scriptSrc =
        uri === DEFAULT_CHANNEL ? `${baseURL}${pkgname}.js` : uri;
      messageCallback(`Loading ${pkg} from ${scriptSrc}`);
      scriptPromises.push(
        loadScript(scriptSrc)
          .then((name) => {
            loaded.push(name);
            loadedPackages[name] = uri;
          })
          .catch((e) => {
            failed[pkg] = e;
          })
      );
    }

    // We must start waiting for runDependencies *after* all the JS files are
    // loaded, since the number of runDependencies may happen to equal zero
    // between package files loading.
    try {
      await Promise.all(scriptPromises).then(waitRunDependency);
    } finally {
      delete Module.monitorRunDependencies;
    }
    restoreOrigWasmPlugin();

    scriptPromises = [];
    for (const [pkg, uri] of toLoad) {
      const pkgname =
        (Module.packages[pkg] && Module.packages[pkg].name) || pkg;
      const scriptSrc =
        uri === DEFAULT_CHANNEL ? `${baseURL}${pkgname}.js` : uri;
      messageCallback(`Loading ${pkg} from ${scriptSrc}`);
      scriptPromises.push(
        loadScript(scriptSrc)
          .then((name) => {
            loaded.push(name);
            loadedPackages[name] = uri;
          })
          .catch((e) => {
            failed[pkg] = e;
          })
      );
    }

    try {
      await Promise.all(scriptPromises).then(waitRunDependency);
    } finally {
      delete Module.monitorRunDependencies;
    }

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
      }
    }

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    Module.importlib.invalidate_caches();
  } finally {
    restoreOrigWasmPlugin();
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
