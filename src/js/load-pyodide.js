import { Module } from "./module.js";

/** @typedef {import('./pyproxy.js').PyProxy} PyProxy */
/** @private */
let baseURL;
/**
 * @param {string} indexURL
 * @private
 */
export async function initializePackageIndex(indexURL) {
  baseURL = indexURL;
  if (typeof process !== "undefined" && process.release.name !== "undefined") {
    const fs = await import("fs");
    fs.readFile(`${indexURL}packages.json`, (err, data) => {
      if (err) throw err;
      let response = JSON.parse(data);
      Module.packages = response;
    });
  } else {
    let response = await fetch(`${indexURL}packages.json`);
    Module.packages = await response.json();
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
  loadScript = (url) => import(url);
} else if (globalThis.importScripts) {
  // webworker
  loadScript = async (url) => {
    // This is async only for consistency
    globalThis.importScripts(url);
  };
} else if (typeof process !== "undefined" && process.release.name === "node") {
  // running in Node.js
  // TODO
  loadScript = (url) => import(url);
} else {
  throw new Error("Cannot determine runtime environment");
}

function recursiveDependencies(
  names,
  _messageCallback,
  errorCallback,
  sharedLibsOnly
) {
  const packages = Module.packages.dependencies;
  const sharedLibraries = Module.packages.shared_library;
  const toLoad = new Map();

  const addPackage = (pkg) => {
    pkg = pkg.toLowerCase();
    if (toLoad.has(pkg)) {
      return;
    }
    toLoad.set(pkg, DEFAULT_CHANNEL);
    // If the package is already loaded, we don't add dependencies, but warn
    // the user later. This is especially important if the loaded package is
    // from a custom url, in which case adding dependencies is wrong.
    if (loadedPackages[pkg] !== undefined) {
      return;
    }
    for (let dep of packages[pkg]) {
      addPackage(dep);
    }
  };
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
    if (name in packages) {
      addPackage(name);
      continue;
    }
    errorCallback(`Skipping unknown package '${name}'`);
  }
  if (sharedLibsOnly) {
    let onlySharedLibs = new Map();
    for (let c of toLoad) {
      if (c[0] in sharedLibraries) {
        onlySharedLibs.set(c[0], toLoad.get(c[0]));
      }
    }
    return onlySharedLibs;
  }
  return toLoad;
}

async function _loadPackage(names, messageCallback, errorCallback) {
  // toLoad is a map pkg_name => pkg_uri
  let toLoad = recursiveDependencies(names, messageCallback, errorCallback);

  // locateFile is the function used by the .js file to locate the .data
  // file given the filename
  Module.locateFile = (path) => {
    // handle packages loaded from custom URLs
    let pkg = path.replace(/\.data$/, "");
    if (toLoad.has(pkg)) {
      let package_uri = toLoad.get(pkg);
      if (package_uri != DEFAULT_CHANNEL) {
        return package_uri.replace(/\.js$/, ".data");
      }
    }
    return baseURL + path;
  };

  if (toLoad.size === 0) {
    return Promise.resolve("No new packages to load");
  } else {
    let packageNames = Array.from(toLoad.keys()).join(", ");
    messageCallback(`Loading ${packageNames}`);
  }

  // This is a collection of promises that resolve when the package's JS file
  // is loaded. The promises already handle error and never fail.
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
    let pkgname = Module.packages.orig_case[pkg] || pkg;
    let scriptSrc = uri === DEFAULT_CHANNEL ? `${baseURL}${pkgname}.js` : uri;
    messageCallback(`Loading ${pkg} from ${scriptSrc}`);
    scriptPromises.push(
      loadScript(scriptSrc).catch((e) => {
        errorCallback(`Couldn't load package from URL ${scriptSrc}`, e);
        toLoad.delete(pkg);
      })
    );
  }

  // When the JS loads, it synchronously adds a runDependency to emscripten.
  // It then loads the data file, and removes the runDependency from
  // emscripten. This function returns a promise that resolves when there are
  // no pending runDependencies.
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
  Module.runPythonSimple(
    "import importlib\n" + "importlib.invalidate_caches()\n"
  );
}

// This is a promise that is resolved iff there are no pending package loads.
// It never fails.
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
 * @param {string | string[] | PyProxy} names Either a single package name or URL
 * or a list of them. URLs can be absolute or relative. The URLs must have
 * file name
 * ``<package-name>.js`` and there must be a file called
 * ``<package-name>.data`` in the same directory. The argument can be a
 * ``PyProxy`` of a list, in which case the list will be converted to
 * Javascript and the ``PyProxy`` will be destroyed.
 * @param {LogFn=} messageCallback A callback, called with progress messages
 *    (optional)
 * @param {LogFn=} errorCallback A callback, called with error/warning
 *    messages (optional)
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
  // override the load plugin so that it imports any dlls also
  // this only needs to be done for shared library packages because
  // we assume that if a package depends on a shared library
  // it needs to have access to it.
  // not needed for so in standard module because those are linked together
  // correctly, it is only where linking goes across modules that it needs to
  // be done. Hence we only put this extra preload plugin in during the shared
  // library load
  let oldPlugin;
  for (let p in Module.preloadPlugins) {
    if (Module.preloadPlugins[p].canHandle("test.so")) {
      oldPlugin = Module.preloadPlugins[p];
      break;
    }
  }
  let dynamicLoadHandler = {
    get: function (obj, prop) {
      if (prop === "handle") {
        return function (bytes, name) {
          obj[prop].apply(obj, arguments);
          this["asyncWasmLoadPromise"] = this["asyncWasmLoadPromise"].then(
            function () {
              Module.loadDynamicLibrary(name, {
                global: true,
                nodelete: true,
              });
            }
          );
        };
      } else {
        return obj[prop];
      }
    },
  };
  var loadPluginOverride = new Proxy(oldPlugin, dynamicLoadHandler);
  // restore the preload plugin
  Module.preloadPlugins.unshift(loadPluginOverride);

  let releaseLock = await acquirePackageLock();
  try {
    await _loadPackage(
      sharedLibraryNames,
      messageCallback || console.log,
      errorCallback || console.error
    );
    Module.preloadPlugins.shift(loadPluginOverride);
    await _loadPackage(
      names,
      messageCallback || console.log,
      errorCallback || console.error
    );
  } finally {
    releaseLock();
  }
}
