(() => {
  /**
   * The main bootstrap script for loading pyodide.
   *
   * Emscripten exposes two Module-global callbacks that we have to handle
   * carefully:
   *  Module.locateFile :
   *     We set this once at the start to load pyodide core, and once each time
   *     loadPackage is called. In loadPackage we use the toFetch package
   *     metadata to decide where to grab the package from, so we use a closure
   * for this. That closure is provided by the function "getFileLocator"
   *
   *  Module.dependencyCallbacks :
   *     gets called at both start and end of package loading
   *     (why didn't emscripten give us two distict callbacks for these two
   *     distinct things?) We handle this by setting it always to the same value
   * and counting up the number of times it is called. When it hits certain
   *     interesting points, we resolve a promise.
   *
   * Both of these global variables mean we cannot load multiple groups of
   * files at once or else we won't be able to control where they come from or
   * what to do when they are done loading. `loadPackage` uses a "promise chain"
   * to make sure that only one instance can run at a time.
   */

  // Note: PYODIDE_BASE_URL is an environment variable replaced in
  // in this template in the Makefile. It's recommended to always set
  // languagePluginUrl in any case.
  let baseURL = globalThis.languagePluginUrl || '{{ PYODIDE_BASE_URL }}';
  baseURL = baseURL.substr(0, baseURL.lastIndexOf('/')) + '/';

  ////////////////////////////////////////////////////////////
  // Loading Pyodide
  let Module = {
    noImageDecoding : true,
    noAudioDecoding : true,
    noWasmDecoding : true,
    preloadedWasm : {},
    checkABI : function(ABI_number) {
      if (ABI_number !== parseInt('{{ PYODIDE_PACKAGE_ABI }}')) {
        var ABI_mismatch_exception =
            `ABI numbers differ. Expected {{ PYODIDE_PACKAGE_ABI }}, got ${
                ABI_number}`;
        console.error(ABI_mismatch_exception);
        throw ABI_mismatch_exception;
      }
      return true;
    },
    autocomplete : function(path) {
      var pyodide_module = Module.pyimport("pyodide");
      return pyodide_module.get_completions(path);
    },
  };

  ////////////////////////////////////////////////////////////
  // Rearrange namespace for public API
  let PUBLIC_API = [
    'globals',
    'loadPackage',
    'loadedPackages',
    'pyimport',
    'repr',
    'runPython',
    'runPythonAsync',
    'checkABI',
    'version',
    'autocomplete',
  ];

  function makePublicAPI(module, public_api) {
    var namespace = {_module : module};
    for (let name of public_api) {
      namespace[name] = module[name];
    }
    return namespace;
  }

  async function loadScript(url) {
    if (globalThis.document) { // browser
      const script = globalThis.document.createElement('script');
      script.src = url;
      let result = new Promise((resolve, reject) => {
        script.onload = resolve;
        script.onerror = reject;
      })
      globalThis.document.head.appendChild(script);
      return result;
    } else if (globalThis.importScripts) { // webworker
      globalThis.importScripts(url);
    }
  }

  function sleep(time) {
    return new Promise(resolve => setTimeout(resolve, time));
  }

  ////////////////////////////////////////////////////////////
  // Managing module-global emscripten callbacks:
  //   * Module.locateFile.
  //   * Module.monitorRunDependencies
  //

  //   First Module.locateFile.
  //   getFileLocator creates closures for the Module level callback
  //   Module.locateFile. When inside loadPackage, locateFile needs the toFetch
  //   metadata to decide where to fetch the package from. Thus we need to
  //   update Module.locateFile from getFileLocator every time we run
  //   loadPackage.

  function getFileLocator(toFetch = {}) {
    return (path) => {
      // handle packages loaded from custom URLs
      let pkg = path.replace(/\.data$/, "");
      if (pkg in toFetch) {
        let package_uri = toFetch[pkg];
        if (package_uri !== 'default channel') {
          return package_uri.replace(/\.js$/, ".data");
        };
      };
      return baseURL + path;
    };
  }
  Module.locateFile = getFileLocator();

  //  Now Module.monitorRunDependencies. Module.monitorRunDependencies is called
  //  twice per script included, once at start and once at finish. Each time
  //  it's called we increment a counter. getRunDependencyPromise returns
  //  promises that we resolve when this counter hits various even integers.

  class _ScriptLoadPromiseManager {
    constructor() {
      this.expectedDependencies = 0;
      this.resolvedDependencies = 0;
      this.dependencyCallbacks = new Map();
      Module.monitorRunDependencies = this.monitorRunDependencies.bind(this);
    }

    // This is the value we will use for the Emscripten Module global callback
    // Module.monitorRunDependencies.
    // Module.monitorRunDependencies is called by emscripten at the beginning
    // and the end of each package being loaded.
    monitorRunDependencies() {
      this.resolvedDependencies++;
      let promise_handles =
          this.dependencyCallbacks.get(this.resolvedDependencies);
      if (promise_handles) {
        promise_handles.resolve();
        this.dependencyCallbacks.delete(this.resolvedDependencies);
      }
    }

    // Returns a promise that resolves when num_dependencies many wasm
    // dependencies are finished. monitorRunDependencies is called twice per
    // package load, so we resolve when monitorRunDependencies has been called
    // 2*num_dependencies many times.
    getPromise(num_dependencies = 1) {
      return new Promise((resolve, reject) => {
        this.expectedDependencies += 2 * num_dependencies;
        this.dependencyCallbacks.set(this.expectedDependencies,
                                     {resolve, reject});
      });
    }

    // If a single script fails to load, call monitorRunDependencies twice
    // (so resolvedDependencies will equal dependencyIndex at the end and
    // we can finish loading)
    scriptLoadFailed() {
      this.monitorRunDependencies();
      // Make sure we don't have a parity error
      if (this.resolvedDependencies % 2 === 1) {
        this.monitorRunDependencies();
      }
    }

    // Reject any remaining dependency callbacks with error "err"
    // and resets the dependency ScriptLoadPromiseManager state.
    clearRunDependencyCallbacks(err) {
      for (let promise_handles of this.dependencyCallbacks.values()) {
        promise_handles.reject(err);
      }
      this.dependencyCallbacks = new Map();
      this.expectedDependencies = 0;
      this.resolvedDependencies = 0;
    }
  }
  let ScriptLoadPromiseManager = new _ScriptLoadPromiseManager();

  ////////////////////////////////////////////////////////////
  // Package loading
  let loadedPackages = {};
  let loadPackagePromise = Promise.resolve();

  async function loadPackage(names, messageCallback, errorCallback) {
    /* We want to make sure that only one loadPackage invocation runs at any
     * given time, so this creates a "chain" of promises. */
    await loadPackagePromise;
    loadPackagePromise = _loadPackage(names, messageCallback, errorCallback);
    return loadPackagePromise;
  };

  async function _loadPackage(names, messageCallback, errorCallback) {
    let result;
    try {
      result = await __loadPackage(names, messageCallback, errorCallback);
    } catch (e) {
      ScriptLoadPromiseManager.clearCallbacks(e);
      throw e;
    }
    let err = new Error(
        "Internal loadPackage error: unexpected unresolved runDependency callbacks.");
    ScriptLoadPromiseManager.clearCallbacks(err);
    return result;
  }

  async function __loadPackage(names, messageCallback, errorCallback) {
    // clang-format off
    messageCallback ||= () => {};
    errorCallback ||= () => {};
    // clang-format on
    let _messageCallback = (msg) => {
      console.log(msg);
      messageCallback(msg);
    };
    let _errorCallback = (errMsg) => {
      console.error(errMsg);
      errorCallback(errMsg);
    };
    let toFetch = chaseDependencies(names, _messageCallback, _errorCallback);
    let numDependenciesToFetch = Object.keys(toFetch).length;
    Module.locateFile = getFileLocator(toFetch);

    if (numDependenciesToFetch === 0) {
      return 'No new packages to load';
    }

    // Set global window handler so we can cancel package loading if an error
    // occurs
    // TODO: be more specific about which errors are related to pyodide.
    globalThis.addEventListener('error', windowErrorHandler);
    let packageList = Array.from(Object.keys(toFetch));
    messageCallback(`Fetching ${packageList.join(', ')}`)
    let fetchPackagePromise =
        fetchPackages(toFetch, _messageCallback, _errorCallback);

    let loadPromise =
        ScriptLoadPromiseManager.getPromise(numDependenciesToFetch);
    // Async breakpoint so that the script loading jobs started up by
    // fetchPackagePromise get a chance to make their requests.
    await sleep(0);
    // We have to invalidate Python's import caches, or it won't
    // see the new files. This is done here so it happens in parallel
    // with the fetching over the network.
    Module.runPython('import importlib as _importlib\n' +
                     '_importlib.invalidate_caches()\n');

    let fetched = await fetchPackagePromise;

    await loadPromise;
    globalThis.removeEventListener('error', windowErrorHandler);
    let packagesLoadedMessage = await installPackages(fetched);
    return packagesLoadedMessage;
  };

  // Regexp for validating package name and URI
  const package_name_regexp_inner = '[a-z0-9_][a-z0-9_\-]*'
  const package_uri_regexp =
      new RegExp(`^https?://.*?(${package_name_regexp_inner}).js$`, 'i');
  const package_name_regexp = new RegExp(`^${package_name_regexp_inner}$`, 'i');

  let _uri_to_package_name = (package_uri) => {
    // Generate a unique package name from URI
    if (package_name_regexp.test(package_uri)) {
      return package_uri;
    } else if (package_uri_regexp.test(package_uri)) {
      let match = package_uri_regexp.exec(package_uri);
      // Get the regexp group corresponding to the package name
      return match[1];
    } else {
      return null;
    }
  };

  // names : A list of package names.
  // Do a DFS to find all dependencies of the requested packages
  // Returns: an object "toFetch" which is a map pkgname ==> package_uri
  function chaseDependencies(names, messageCallback, errorCallback) {
    let packages = Module.packages.dependencies;
    let loadedPackages = Module.loadedPackages;
    // Copy names into queue.
    let queue = [].concat(names);
    let toFetch = {};
    while (queue.length) {
      let package_uri = queue.pop();

      const pkg = _uri_to_package_name(package_uri);

      if (pkg === null) {
        errorCallback(`Invalid package name or URI '${package_uri}'`);
        return;
      } else if (pkg === package_uri) {
        package_uri = 'default channel';
      }

      // Already loaded?
      if (pkg in loadedPackages) {
        if (package_uri !== loadedPackages[pkg]) {
          errorCallback(`URI mismatch, attempting to load package ` +
                        `${pkg} from ${package_uri} while it is already ` +
                        `loaded from ${loadedPackages[pkg]}!`);
          return;
        }
        messageCallback(`${pkg} already loaded from ${loadedPackages[pkg]}`);
        continue;
      }

      // Already enqueued?
      if (pkg in toFetch) {
        if (package_uri !== toFetch[pkg]) {
          errorCallback(`URI mismatch, attempting to load package ` +
                        `${pkg} from ${package_uri} while it is already ` +
                        `being loaded from ${toFetch[pkg]}!`);
          return;
        }
        continue;
      }

      messageCallback(
          `${pkg} to be loaded from ${package_uri}`); // debug level info.
      toFetch[pkg] = package_uri;
      if (!packages.hasOwnProperty(pkg)) {
        errorCallback(`Unknown package '${pkg}'`);
        continue;
      }

      for (let subpkg of packages[pkg]) {
        if (!(subpkg in loadedPackages) && !(subpkg in toFetch)) {
          queue.push(subpkg);
        }
      }
    }
    return toFetch;
  }

  // A handler for any exceptions that are thrown in the process of
  // loading a package
  // TODO: attaching a global error handler for this seems like a really bad
  // idea. What are we trying to catch? Can't we be a bit more specific?
  function windowErrorHandler(err) {
    ScriptLoadPromiseManager.clearCallbacks(err);
    globalThis.removeEventListener('error', windowErrorHandler);
    // Set up a new Promise chain, since this one failed
    loadPackagePromise = Promise.resolve();
    throw err;
  };

  // toFetch : the object map packageName ==> package_uri created by
  // chaseDependencies. Returns : an object map packageName ==> package_uri
  // consisting of the entries in toFetch that we successfully fetched.
  async function fetchPackages(toFetch, messageCallback, errorCallback) {
    let promises = [];
    let fetched = {};
    async function fetchPackageHelper(pkg, package_uri) {
      let scriptSrc;
      try {
        if (package_uri === 'default channel') {
          scriptSrc = `${baseURL}${pkg}.js`;
        } else {
          scriptSrc = `${package_uri}`;
        }
        messageCallback(`Loading ${pkg} from ${scriptSrc}`);
        await loadScript(scriptSrc);
        fetched[pkg] = package_uri;
      } catch {
        errorCallback(`Couldn't load package from URL ${scriptSrc}`);
        ScriptLoadPromiseManager.scriptLoadFailed();
      }
    }

    for (let [pkg, package_uri] of Object.entries(toFetch)) {
      promises.push(fetchPackageHelper(pkg, package_uri));
    }
    await Promise.all(promises);
    return fetched;
  }

  // Put the package uri into Module.loadedPackages and call preloadWasm().
  async function installPackages(fetched) {
    for (let [pkg, package_uri] of Object.entries(fetched)) {
      Module.loadedPackages[pkg] = package_uri;
    }
    let resolveMsg;
    let packageList = Array.from(Object.keys(fetched));
    if (packageList.length > 0) {
      let name_list = packageList.join(', ');
      resolveMsg = `Loaded ${name_list}`
    } else {
      resolveMsg = 'Loaded no packages'
    }

    await preloadWasm();
    return resolveMsg;
  }

  // clang-format off
  async function preloadWasm() {
    let isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;
    if(isFirefox){
      return;
    }
    // In Chrome, we have to instantiate wasm asynchronously. Since that
    // can't be done synchronously within the call to dlopen, we instantiate
    // every .so that comes our way up front, caching it in the
    // `preloadedWasm` dictionary.
    let FS = pyodide._module.FS;
    let promise = Promise.resolve();
    async function scheduleLoadWasm(promise, path){
      if (Module['preloadedWasm'][path] !== undefined) {
        return;
      }
      await promise;
      await Module['loadWebAssemblyModule'](FS.readFile(path), {loadAsync: true});
      Module['preloadedWasm'][path] = module;
    }

    function recurseDir(rootpath) {
      let dirs;
      try {
        dirs = FS.readdir(rootpath);
      } catch {
        return;
      }
      for (let entry of dirs) {
        if (entry.startsWith('.')) {
          continue;
        }
        const path = rootpath + entry;
        if (entry.endsWith('.so')) {
          promise = scheduleLoadWasm(promise, path);
        } else if (FS.isDir(FS.lookupPath(path).node.mode)) {
          recurseDir(path + '/');
        }
      }
    }
    recurseDir('/');
    return promise;
  }
  // clang-format on

  ////////////////////////////////////////////////////////////
  // Fix Python recursion limit
  function fixRecursionLimit(pyodide) {
    // The Javascript/Wasm call stack may be too small to handle the default
    // Python call stack limit of 1000 frames. This is generally the case on
    // Chrom(ium), but not on Firefox. Here, we determine the Javascript call
    // stack depth available, and then divide by 50 (determined heuristically)
    // to set the maximum Python call stack depth.

    let depth = 0;
    function recurse() {
      depth += 1;
      recurse();
    }
    try {
      recurse();
    } catch (err) {
      ;
    }

    let recursionLimit = depth / 50;
    if (recursionLimit > 1000) {
      recursionLimit = 1000;
    }
    pyodide.runPython(`
      import sys
      sys.setrecursionlimit(int(${recursionLimit}))
    `);
  };

  async function main() {
    let postRunPromise = new Promise(resolve => Module.postRun = resolve);
    async function postRun() {
      await postRunPromise;
      let response = await fetch(`${baseURL}packages.json`);
      let json = await response.json();
      fixRecursionLimit(globalThis.pyodide);
      globalThis.pyodide.globals = globalThis.pyodide.runPython(`
            import sys;
            sys.modules["__main__"]
          `);
      globalThis.pyodide = makePublicAPI(globalThis.pyodide, PUBLIC_API);
      globalThis.pyodide._module.packages = json;
    }

    async function loadPyodideCore() {
      let numScriptsToLoad = 2;
      let runDependencyPromise =
          ScriptLoadPromiseManager.getPromise(numScriptsToLoad);
      const dataScriptSrc = `${baseURL}pyodide.asm.data.js`;
      const scriptSrc = `${baseURL}pyodide.asm.js`;
      // The emscripten module needs to be at globalThis.Module for the core
      // filesystem to install itself. Once that's complete, it will be replaced
      // by the call to `makePublicAPI` with a more limited public API.
      globalThis.Module = Module;
      // dataScriptSrc must be loaded before scriptSrc.
      await loadScript(dataScriptSrc);
      await loadScript(scriptSrc);
      globalThis.pyodide = pyodide(Module);
      Module.loadedPackages = {};
      Module.loadPackage = loadPackage;
      return runDependencyPromise;
    }

    await Promise.all([ postRun(), loadPyodideCore() ]);
    let err = new Error(
        "Internal loadPackage error: unexpected unresolved runDependency callbacks.");
    ScriptLoadPromiseManager.clearCallbacks(err);
    delete globalThis.Module;
  };

  globalThis.languagePluginLoader = main();
})();
