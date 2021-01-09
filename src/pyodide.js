/**
 * The main bootstrap script for loading pyodide.
 */

var languagePluginLoader = new Promise((resolve, reject) => {
  // Note: PYODIDE_BASE_URL is an environement variable replaced in
  // in this template in the Makefile. It's recommended to always set
  // languagePluginUrl in any case.
  var baseURL = self.languagePluginUrl || '{{ PYODIDE_BASE_URL }}';
  baseURL = baseURL.substr(0, baseURL.lastIndexOf('/')) + '/';

  ////////////////////////////////////////////////////////////
  // Package loading
  const DEFAULT_CHANNEL = "default channel";

  // Regexp for validating package name and URI
  const package_uri_regexp =
      new RegExp('^https?://.*?([a-z0-9_][a-z0-9_\-]*).js$', 'i');

  let _uri_to_package_name = (package_uri) => {
    if (package_uri_regexp.test(package_uri)) {
      let match = package_uri_regexp.exec(package_uri);
      // Get the regexp group corresponding to the package name
      return match[1];
    } else {
      return null;
    }
  };

  // clang-format off
  let preloadWasm = () => {
    // On Chrome, we have to instantiate wasm asynchronously. Since that
    // can't be done synchronously within the call to dlopen, we instantiate
    // every .so that comes our way up front, caching it in the
    // `preloadedWasm` dictionary.

    let promise = new Promise((resolve) => resolve());
    let FS = pyodide._module.FS;

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
          if (Module['preloadedWasm'][path] === undefined) {
            promise = promise
              .then(() => Module['loadWebAssemblyModule'](
                FS.readFile(path), {loadAsync: true}))
              .then((module) => {
                Module['preloadedWasm'][path] = module;
              });
          }
        } else if (FS.isDir(FS.lookupPath(path).node.mode)) {
          recurseDir(path + '/');
        }
      }
    }

    recurseDir('/');

    return promise;
  }
  // clang-format on

  let loadScript = () => {};
  if (self.document) { // browser
    loadScript = (url) => new Promise((res, rej) => {
      const script = self.document.createElement('script');
      script.src = url;
      script.onload = res;
      script.onerror = rej;
      self.document.head.appendChild(script);
    });
  } else if (self.importScripts) { // webworker
    loadScript = async (url) => {  // This is async only for consistency
      self.importScripts(url);
    }
  } else {
    throw new Error("Cannot determine runtime environment");
  }

  function recursiveDependencies(names) {
    const packages = self.pyodide._module.packages.dependencies;
    const loadedPackages = self.pyodide.loadedPackages;
    const toLoad = new Map();

    const addPackage = (pkg) => {
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
      if (pkgname !== null) {
        if (toLoad.has(pkgname) && toLoad.get(pkgname) !== name) {
          console.error(`Loading same package ${pkgname} from ${name} and ${
              toLoad.get(pkgname)}`);
          continue;
        }
        toLoad.set(pkgname, name);
      } else if (name in packages) {
        addPackage(name);
      } else {
        console.error(`Skipping unknown package '${name}'`);
      }
    }
    return toLoad;
  }

  async function _loadPackage(names) {
    // toLoad is a map pkg_name => pkg_uri
    let toLoad = recursiveDependencies(names);

    // locateFile is the function used by the .js file to locate the .data
    // file given the filename
    self.pyodide._module.locateFile = (path) => {
      // handle packages loaded from custom URLs
      let pkg = path.replace(/\.data$/, "");
      if (toLoad.has(pkg)) {
        let package_uri = toLoad.get(pkg);
        if (package_uri != DEFAULT_CHANNEL) {
          return package_uri.replace(/\.js$/, ".data");
        };
      };
      return baseURL + path;
    };

    if (toLoad.size === 0) {
      return Promise.resolve('No new packages to load');
    } else {
      console.log(`Loading ${[...toLoad.keys()].join(', ')}`)
    }

    // When we load a package, we first load a JS file, and then the JS file
    // loads the data file. The status of the first step is tracked by the
    // loadScript function above. The status of the second step is tracked by
    // emscripten's runDependency system.
    //
    // When the JS file is loaded, it *synchronously* adds a runDependency to
    // emscripten. When it finishes loading, it removes the runDependency.
    // Whenever the number of runDependencies changes, monitorRunDependency is
    // called with the number of pending dependencies.
    //
    // Under this system, packages have completed loading if all javascript
    // files are loaded, and then the number of runDependencies becomes zero.
    // The number of runDependencies may happen to equal zero in between
    // package files loading if we are loading multiple packages. We must avoid
    // accidentally returning early if this happens.

    // runDepPromise is a promise such that at any point in time, it is
    // resolved if and only if the number of pending run dependencies is 0.
    // We assume that at this point in time, there are no pending run
    // dependencies.
    //
    // The promise it refers to may be replaced when a runDependency is added,
    // so we must be careful to only await for this after we know all
    // runDependencies have been added.
    let runDepPromise = Promise.resolve();
    // runDepResolve is the resolve function of runDepPromise if it is
    // unresolved, undefined otherwise.
    let runDepResolve = undefined;

    // We must start monitoring before we load any script, as this function is
    // triggered by the script loading.
    self.pyodide._module.monitorRunDependencies = (n) => {
      if (n === 0) {
        if (runDepResolve !== undefined) {
          runDepResolve();
          runDepResolve = undefined;
        }
      } else {
        if (runDepResolve === undefined) {
          runDepPromise = new Promise(r => runDepResolve = r);
        }
      }
    };

    // Try to catch errors thrown when running a script. Since the script is
    // added via a script tag, there is no good way to capture errors from
    // the script only, so try to capture all errors them.
    //
    // windowErrorPromise rejects when any exceptions is thrown in the process
    // of loading a script. The promise never resolves, and we combine it
    // with other promises via Promise.race.
    let windowErrorHandler;
    let windowErrorPromise = new Promise((_res, rej) => {
      windowErrorHandler = e => {
        console.error(
            "Unhandled error. We don't know what it is or whether it is related to 'loadPackage' but out of an abundance of caution we will assume that loading failed.");
        console.error(e);
        rej(e.message);
      };
      self.addEventListener('error', windowErrorHandler);
    });

    // Promises for each script load. The promises already handle error and
    // never fail.
    let scriptPromises = [];

    for (let [pkg, uri] of toLoad) {
      let loaded = self.pyodide.loadedPackages[pkg];
      if (loaded !== undefined) {
        // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
        // depedency, which was previously overridden.
        if (loaded === uri || uri === DEFAULT_CHANNEL) {
          console.log(`${pkg} already loaded from ${loaded}`);
          continue;
        } else {
          console.error(`URI mismatch, attempting to load package ${pkg} from ${
              uri} while it is already loaded from ${
              loaded}. To override a dependency, load the custom package first.`);
          continue;
        }
      }
      let scriptSrc = uri === DEFAULT_CHANNEL ? `${baseURL}${pkg}.js` : uri;
      console.log(`Loading ${pkg} from ${scriptSrc}`);
      scriptPromises.push(loadScript(scriptSrc).catch(() => {
        console.error(`Couldn't load package from URL ${scriptSrc}`);
        toLoad.delete(pkg);
      }));
    }

    // Wait for all scripts to be loaded first. Then all the run dependencies
    // have been added. Then wait for the dependencies to be removed.
    let successPromise = Promise.all(scriptPromises).then(() => runDepPromise);
    try {
      await Promise.race([ successPromise, windowErrorPromise ]);
    } finally {
      delete self.pyodide._module.monitorRunDependencies;
      self.removeEventListener('error', windowErrorHandler);
    }

    let packageList = [];
    for (let [pkg, uri] of toLoad) {
      self.pyodide.loadedPackages[pkg] = uri;
      packageList.push(pkg);
    }

    let resolveMsg;
    if (packageList.length > 0) {
      let package_names = packageList.join(', ');
      resolveMsg = `Loaded ${packageList}`;
    } else {
      resolveMsg = 'No packages loaded';
    }

    if (!isFirefox) {
      await preloadWasm();
    }
    console.log(resolveMsg);

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    self.pyodide.runPython('import importlib as _importlib\n' +
                           '_importlib.invalidate_caches()\n');
  };

  // This is a promise that is resolved iff there are no pending package loads.
  // It never fails.
  let loadPackageChain = Promise.resolve();

  async function loadPackage(names) {
    if (!Array.isArray(names)) {
      names = [ names ];
    }
    let promise = loadPackageChain.then(() => _loadPackage(names));
    loadPackageChain = loadPackageChain.then(() => promise.catch(() => {}));
    await promise;
  }

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

  ////////////////////////////////////////////////////////////
  // Rearrange namespace for public API
  let PUBLIC_API = [
    'globals',
    'loadPackage',
    'loadPackagesFromImports',
    'loadedPackages',
    'pyimport',
    'runPython',
    'runPythonAsync',
    'version',
  ];

  function makePublicAPI(module, public_api) {
    var namespace = {_module : module};
    for (let name of public_api) {
      namespace[name] = module[name];
    }
    return namespace;
  }

  ////////////////////////////////////////////////////////////
  // Loading Pyodide
  let Module = {};
  self.Module = Module;

  Module.noImageDecoding = true;
  Module.noAudioDecoding = true;
  Module.noWasmDecoding = true;
  Module.preloadedWasm = {};
  let isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;

  Module.runPython = code => Module.pyodide_py.eval_code(code, Module.globals);

  // clang-format off
  Module.loadPackagesFromImports  = async function(code) {
    let imports = Module.pyodide_py.find_imports(code);
    if (imports.length === 0) {
      return;
    }
    let packageNames =
        self.pyodide._module.packages.import_name_to_package_name;
    let packages = new Set();
    for (let name of imports) {
      if (name in packageNames) {
        packages.add(name);
      }
    }
    if (packages.size) {
      await loadPackage(
        Array.from(packages.keys())
      );
    }
  };
  // clang-format on

  Module.pyimport = name => Module.globals[name];

  Module.runPythonAsync = async function(code) {
    await Module.loadPackagesFromImports(code);
    return Module.runPython(code);
  };

  Module.locateFile = (path) => baseURL + path;
  Module.postRun = async () => {
    delete self.Module;
    let response = await fetch(`${baseURL}packages.json`);
    let json = await response.json();
    fixRecursionLimit(self.pyodide);
    self.pyodide = makePublicAPI(self.pyodide, PUBLIC_API);
    self.pyodide._module.packages = json;
    resolve();
  };

  const scriptSrc = `${baseURL}pyodide.asm.js`;
  loadScript(scriptSrc).then(() => {
    // The emscripten module needs to be at this location for the core
    // filesystem to install itself. Once that's complete, it will be replaced
    // by the call to `makePublicAPI` with a more limited public API.
    self.pyodide = pyodide(Module);
    self.pyodide.loadedPackages = {};
    self.pyodide.loadPackage = loadPackage;
  });
});
languagePluginLoader
