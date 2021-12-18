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

export async function _fetchBinaryFile(indexURL, path) {
  if (IN_NODE) {
    const fsPromises = await import(/* webpackIgnore: true */ "fs/promises");
    const tar_buffer = await fsPromises.readFile(`${indexURL}${path}`);
    return tar_buffer.buffer;
  } else {
    let response = await fetch(`${indexURL}${path}`);
    return await response.arrayBuffer();
  }
}

////////////////////////////////////////////////////////////
// Package loading
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
  const pathPromise = import(/* webpackIgnore: true */ "path").then(
    (M) => M.default
  );
  const fetchPromise = import("node-fetch").then((M) => M.default);
  const vmPromise = import(/* webpackIgnore: true */ "vm").then(
    (M) => M.default
  );
  loadScript = async (url) => {
    if (url.includes("://")) {
      // If it's a url, have to load it with fetch and then eval it.
      const fetch = await fetchPromise;
      const vm = await vmPromise;
      vm.runInThisContext(await (await fetch(url)).text());
    } else {
      // Otherwise, hopefully it is a relative path we can load from the file
      // system.
      const path = await pathPromise;
      await import(path.resolve(url));
    }
  };
} else {
  throw new Error("Cannot determine runtime environment");
}

function addPackageToLoad(name, toLoad) {
  name = name.toLowerCase();
  if (toLoad.has(name)) {
    return;
  }
  toLoad.set(name, DEFAULT_CHANNEL);
  // If the package is already loaded, we don't add dependencies, but warn
  // the user later. This is especially important if the loaded package is
  // from a custom url, in which case adding dependencies is wrong.
  if (loadedPackages[name] !== undefined) {
    return;
  }
  for (let dep_name of Module.packages[name].depends) {
    addPackageToLoad(dep_name, toLoad);
  }
}

function recursiveDependencies(
  names,
  _messageCallback,
  errorCallback,
  sharedLibsOnly
) {
  const toLoad = new Map();
  for (let name of names) {
    const pkgname = _uri_to_package_name(name);
    if (toLoad.has(pkgname) && toLoad.get(pkgname) !== name) {
      errorCallback(
        `Loading same package ${pkgname} from ${name} and ${toLoad.get(
          pkgname
        )}`
      );
      continue;
    }
    if (pkgname !== undefined) {
      toLoad.set(pkgname, name);
      continue;
    }
    name = name.toLowerCase();
    if (name in Module.packages) {
      addPackageToLoad(name, toLoad);
      continue;
    }
    errorCallback(`Skipping unknown package '${name}'`);
  }
  if (sharedLibsOnly) {
    let onlySharedLibs = new Map();
    for (let c of toLoad) {
      let name = c[0];
      if (Module.packages[name].shared_library) {
        onlySharedLibs.set(name, toLoad.get(name));
      }
    }
    return onlySharedLibs;
  }
  return toLoad;
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

async function _loadPackage(names, messageCallback, errorCallback) {
  // toLoad is a map pkg_name => pkg_uri
  let toLoad = recursiveDependencies(names, messageCallback, errorCallback);
  // Tell Module.locateFile about the packages we're loading
  Module.locateFile_packagesToLoad = toLoad;
  if (toLoad.size === 0) {
    return Promise.resolve("No new packages to load");
  } else {
    let packageNames = Array.from(toLoad.keys()).join(", ");
    messageCallback(`Loading ${packageNames}`);
  }

  // This is a collection of promises that resolve when the package's JS file is
  // loaded. The promises already handle error and never fail.
  let scriptPromises = [];

  for (let [pkg, uri] of toLoad) {
    let loaded = loadedPackages[pkg];
    if (loaded !== undefined) {
      // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
      // depedency, which was previously overridden.
      if (loaded === uri || uri === DEFAULT_CHANNEL) {
        messageCallback(`${pkg} already loaded from ${loaded}`);
        continue;
      } else {
        errorCallback(
          `URI mismatch, attempting to load package ${pkg} from ${uri} ` +
            `while it is already loaded from ${loaded}. To override a dependency, ` +
            `load the custom package first.`
        );
        continue;
      }
    }
    let pkgname = (Module.packages[pkg] && Module.packages[pkg].name) || pkg;
    let scriptSrc = uri === DEFAULT_CHANNEL ? `${baseURL}${pkgname}.js` : uri;
    messageCallback(`Loading ${pkg} from ${scriptSrc}`);
    scriptPromises.push(
      loadScript(scriptSrc).catch((e) => {
        errorCallback(`Couldn't load package from URL ${scriptSrc}`, e);
        toLoad.delete(pkg);
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

  let packageList = [];
  for (let [pkg, uri] of toLoad) {
    loadedPackages[pkg] = uri;
    packageList.push(pkg);
  }

  let resolveMsg;
  if (packageList.length > 0) {
    let packageNames = packageList.join(", ");
    resolveMsg = `Loaded ${packageNames}`;
  } else {
    resolveMsg = "No packages loaded";
  }

  Module.reportUndefinedSymbols();

  messageCallback(resolveMsg);

  // We have to invalidate Python's import caches, or it won't
  // see the new files.
  Module.importlib.invalidate_caches();
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
    let temp;
    try {
      temp = names.toJs();
    } finally {
      names.destroy();
    }
    names = temp;
  }

  if (!Array.isArray(names)) {
    names = [names];
  }
  // get shared library packages and load those first
  // otherwise bad things happen with linking them in firefox.
  let sharedLibraryNames = [];
  try {
    let sharedLibraryPackagesToLoad = recursiveDependencies(
      names,
      messageCallback,
      errorCallback,
      true
    );
    for (let pkg of sharedLibraryPackagesToLoad) {
      sharedLibraryNames.push(pkg[0]);
    }
  } catch (e) {
    // do nothing - let the main load throw any errors
  }

  let releaseLock = await acquirePackageLock();
  try {
    useSharedLibraryWasmPlugin();
    await _loadPackage(
      sharedLibraryNames,
      messageCallback || console.log,
      errorCallback || console.error
    );
    restoreOrigWasmPlugin();
    await _loadPackage(
      names,
      messageCallback || console.log,
      errorCallback || console.error
    );
  } finally {
    restoreOrigWasmPlugin();
    releaseLock();
  }
}
