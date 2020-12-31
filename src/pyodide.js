(() => {
  /**
   * The main bootstrap script for loading pyodide.
   */

  ////////////////////////////////////////////////////////////
  // Loading Pyodide
  self.Module = {
    noImageDecoding : true,
    noAudioDecoding : true,
    noWasmDecoding : true,
    preloadedWasm : {},
    monitorRunDependencies,
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
  let postRunPromise = new Promise(resolve => Module.postRun = resolve);

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

  async function loadScript(url) {
    if (self.document) { // browser
      const script = self.document.createElement('script');
      script.src = url;
      let result = new Promise((resolve, reject) => {
        script.onload = resolve;
        script.onerror = reject;
      })
      self.document.head.appendChild(script);
      return result;
    } else if (self.importScripts) { // webworker
      self.importScripts(url);
    }
  }

  // Load multiple scripts, in order (not simultaneously).
  async function loadScripts(scripts) {
    if (!(scripts instanceof Array)) {
      scripts = [ scripts ];
    }
    for (let s of scripts) {
      await loadScript(s);
    }
  }

  let dependencyIndex = 0;
  let resolvedDependencies = 0;
  let dependencyCallbacks = new Map();
  // Wait for num_dependencies many wasm dependencies to be loaded
  // monitorRunDependencies is called twice per package load
  // That will have happened when monitorRunDependencies has been called
  // 2*num_dependencies many times.
  function getRunDependencyPromise(num_dependencies = 1) {
    return new Promise((resolve, reject) => {
      dependencyIndex += 2 * num_dependencies;
      dependencyCallbacks.set(dependencyIndex, {resolve, reject});
    });
  }

  function runDependencyLoadFailed() {
    // If the package_uri fails to load, call monitorRunDependencies twice
    // (so packageCounter will still hit 0 and finish loading), and remove
    // the package from toLoad so we don't mark it as loaded, and remove
    // the package from packageList so we don't say that it was loaded.
    monitorRunDependencies();
    monitorRunDependencies();
  }

  function clearRunDependencyCallbacks(err) {
    for (let promise_handles of dependencyCallbacks.values()) {
      promise_handles.reject(err);
    }
    dependencyCallbacks = new Map();
  }

  // This is the value we will use for the Emscripten Module global callback
  // Module.monitorRunDependencies.
  // Module.monitorRunDependencies is called by emscripten at the beginning and
  // the end of each package being loaded.
  function monitorRunDependencies() {
    resolvedDependencies++;
    if (resolvedDependencies % 2 === 0) {
      let promise_handles = dependencyCallbacks.get(resolvedDependencies);
      if (promise_handles) {
        promise_handles.resolve();
      }
    }
  }

  ////////////////////////////////////////////////////////////
  // Package loading

  // names : A list of package names.
  // Do a DFS to find all dependencies of the requested packages
  function chaseDependencies(names) {
    let packages = self.pyodide._module.packages.dependencies;
    let loadedPackages = self.pyodide.loadedPackages;
    // Copy names into queue.
    let queue = [].concat(names);
    let toLoad = {};
    while (queue.length) {
      let package_uri = queue.pop();

      const pkg = _uri_to_package_name(package_uri);

      if (pkg === null) {
        _errorCallback(`Invalid package name or URI '${package_uri}'`);
        return;
      } else if (pkg === package_uri) {
        package_uri = 'default channel';
      }

      // Already loaded?
      if (pkg in loadedPackages) {
        if (package_uri !== loadedPackages[pkg]) {
          _errorCallback(`URI mismatch, attempting to load package ` +
                         `${pkg} from ${package_uri} while it is already ` +
                         `loaded from ${loadedPackages[pkg]}!`);
          return;
        }
        _messageCallback(`${pkg} already loaded from ${loadedPackages[pkg]}`);
        continue;
      }

      // Already enqueued?
      if (pkg in toLoad) {
        if (package_uri !== toLoad[pkg]) {
          _errorCallback(`URI mismatch, attempting to load package ` +
                         `${pkg} from ${package_uri} while it is already ` +
                         `being loaded from ${toLoad[pkg]}!`);
          return;
        }
        continue;
      }

      _messageCallback(
          `${pkg} to be loaded from ${package_uri}`); // debug level info.
      toLoad[pkg] = package_uri;
      if (!packages.hasOwnProperty(pkg)) {
        _errorCallback(`Unknown package '${pkg}'`);
        continue;
      }

      for (let subpkg of packages[pkg]) {
        if (!(subpkg in loadedPackages) && !(subpkg in toLoad)) {
          queue.push(subpkg);
        }
      }
    }
    return toLoad;
  }

  let baseURL = self.languagePluginUrl || '{{ PYODIDE_BASE_URL }}';
  baseURL = baseURL.substr(0, baseURL.lastIndexOf('/')) + '/';
  // This is used for the Module level variable Module.locateFile.
  function getFileLocator(toLoad = {}) {
    return (path) => {
      // handle packages loaded from custom URLs
      let pkg = path.replace(/\.data$/, "");
      if (pkg in toLoad) {
        let package_uri = toLoad[pkg];
        if (package_uri != 'default channel') {
          return package_uri.replace(/\.js$/, ".data");
        };
      };
      return baseURL + path;
    };
  }

  Module.locateFile = getFileLocator();

  let loadedPackages = {};
  let loadPackagePromise = Promise.resolve();

  async function loadPackage(names, messageCallback, errorCallback) {
    /* We want to make sure that only one loadPackage invocation runs at any
     * given time, so this creates a "chain" of promises. */
    await loadPackagePromise;
    loadPackagePromise = _loadPackage(names, messageCallback, errorCallback);
    return loadPackagePromise;
  };

  // A handler for any exceptions that are thrown in the process of
  // loading a package
  // TODO: attaching a global error handler for this seems like a really bad
  // idea. What are we trying to catch? Can't we be a bit more specific?
  function windowErrorHandler(err) {
    clearRunDependencyCallbacks(err);
    self.removeEventListener('error', windowErrorHandler);
    // Set up a new Promise chain, since this one failed
    loadPackagePromise = Promise.resolve();
    throw err;
  };

  // Note: this modifies the argument in place if it fails to fetch any of them.
  async function fetchPackages(toLoad) {
    let promises = [];
    let loaded = {};
    async function fetchPackageHelper(pkg, package_uri) {
      try {
        let scriptSrc;
        if (package_uri == 'default channel') {
          scriptSrc = `${baseURL}${pkg}.js`;
        } else {
          scriptSrc = `${package_uri}`;
        }
        _messageCallback(`Loading ${pkg} from ${scriptSrc}`);
        await loadScript(scriptSrc);
        loaded[pkg] = package_uri;
      } catch {
        _errorCallback(`Couldn't load package from URL ${scriptSrc}`);
        let packageListIndex = packageList.indexOf(pkg);
        if (packageListIndex !== -1) {
          packageList.splice(packageListIndex, 1);
        }
        runDependencyLoadFailed();
      }
    }

    for (let [pkg, package_uri] of Object.entries(toLoad)) {
      promises.push(fetchPackageHelper(pkg, package_uri));
    }
    await Promise.all(promises);
    return loaded;
  }

  async function installPackages(toLoad) {
    for (let [pkg, package_uri] of Object.entries(toLoad)) {
      self.pyodide.loadedPackages[pkg] = package_uri;
    }
    let resolveMsg;
    if (packageList.length > 0) {
      let name_list = packageList.join(', ');
      resolveMsg = `Loaded ${name_list}`
    } else {
      resolveMsg = 'Loaded no packages'
    }

    let isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;
    if (isFirefox) {
      return resolveMsg;
    } else {
      await preloadWasm();
      return resolveMsg;
    }
  }

  async function _loadPackage(names, messageCallback, errorCallback) {
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

    let toLoad = chaseDependencies(names);
    self.pyodide._module.locateFile = getFileLocator(toLoad);

    if (Object.keys(toLoad).length === 0) {
      return 'No new packages to load';
    }

    let packageList = Array.from(Object.keys(toLoad));
    _messageCallback(`Loading ${packageList.join(', ')}`)

    // monitorRunDependencies is called at the beginning and the end of each
    // package being loaded. We know we are done when it has been called
    // exactly "toLoad * 2" times.
    let runDependencyPromise =
        getRunDependencyPromise(Object.keys(toLoad).length);
    // Set global window handler so we can cancel package loading if an error
    // occurs
    // TODO: be more specific about which errors are related to pyodide.
    self.addEventListener('error', windowErrorHandler);
    let fetchPackagePromise = fetchPackages(toLoad);

    // We have to invalidate Python's import caches, or it won't
    // see the new files. This is done here so it happens in parallel
    // with the fetching over the network.
    self.pyodide.runPython('import importlib as _importlib\n' +
                           '_importlib.invalidate_caches()\n');

    let loaded = await fetchPackagePromise;

    await runDependencyPromise;
    self.removeEventListener('error', windowErrorHandler);
    let packagesLoadedMessage = await installPackages(loaded);
    return packagesLoadedMessage;
  };

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
    pyodide.runPython(
        `import sys; sys.setrecursionlimit(int(${recursionLimit}))`);
  };

  // clang-format off
  async function preloadWasm() {
    // On Chrome, we have to instantiate wasm asynchronously. Since that
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

  async function main() {
    // Note: PYODIDE_BASE_URL is an environment variable replaced in
    // in this template in the Makefile. It's recommended to always set
    // languagePluginUrl in any case.
    async function postRun() {
      await postRunPromise;
      delete self.Module;
      let response = await fetch(`${baseURL}packages.json`);
      let json = await response.json();
      fixRecursionLimit(self.pyodide);
      self.pyodide.globals =
          self.pyodide.runPython('import sys\nsys.modules["__main__"]');
      self.pyodide = makePublicAPI(self.pyodide, PUBLIC_API);
      self.pyodide._module.packages = json;
    }

    const dataScriptSrc = `${baseURL}pyodide.asm.data.js`;
    const scriptSrc = `${baseURL}pyodide.asm.js`;
    let runDependencyPromise = getRunDependencyPromise();
    loadScripts([ dataScriptSrc, scriptSrc ]).then(() => {
      // The emscripten module needs to be at this location for the core
      // filesystem to install itself. Once that's complete, it will be replaced
      // by the call to `makePublicAPI` with a more limited public API.
      self.pyodide = pyodide(Module);
      self.pyodide.loadedPackages = {};
      self.pyodide.loadPackage = loadPackage;
    });

    await Promise.all([ postRun(), runDependencyPromise ]);
  };

  globalThis.languagePluginLoader = main();
})();
