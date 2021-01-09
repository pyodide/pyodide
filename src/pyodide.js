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
  let loadedPackages = {};
  // Regexp for validating package name and URI
  var package_name_regexp = '[a-z0-9_][a-z0-9_\-]*'
  var package_uri_regexp =
      new RegExp('^https?://.*?(' + package_name_regexp + ').js$', 'i');
  var package_name_regexp = new RegExp('^' + package_name_regexp + '$', 'i');

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
  }

  function recursiveDependencies(names) {
    let err = (err_msg) => {
      console.error(err_msg);
      throw new Error(err_msg);
    };

    let packages = self.pyodide._module.packages.dependencies;
    let loadedPackages = self.pyodide.loadedPackages;
    let queue = [].concat(names || []);
    let toLoad = {};
    while (queue.length) {
      let package_uri = queue.pop();

      const pkg = _uri_to_package_name(package_uri);

      if (pkg == null) {
        err(`Invalid package name or URI '${package_uri}'`);
      } else if (pkg == package_uri) {
        package_uri = 'default channel';
      }

      if (pkg in loadedPackages) {
        if (package_uri != loadedPackages[pkg]) {
          err(`URI mismatch, attempting to load package ` +
              `${pkg} from ${package_uri} while it is already ` +
              `loaded from ${loadedPackages[pkg]}!`);
        } else {
          console.log(`${pkg} already loaded from ${loadedPackages[pkg]}`)
        }
      } else if (pkg in toLoad) {
        if (package_uri != toLoad[pkg]) {
          err(`URI mismatch, attempting to load package ` +
              `${pkg} from ${package_uri} while it is already ` +
              `being loaded from ${toLoad[pkg]}!`);
          return;
        }
      } else {
        console.log(
            `${pkg} to be loaded from ${package_uri}`); // debug level info.

        toLoad[pkg] = package_uri;
        if (packages.hasOwnProperty(pkg)) {
          packages[pkg].forEach((subpackage) => {
            if (!(subpackage in loadedPackages) && !(subpackage in toLoad)) {
              queue.push(subpackage);
            }
          });
        } else {
          console.error(`Unknown package '${pkg}'`);
        }
      }
    }
    return toLoad;
  }

  async function _loadPackage(names) {
    // toLoad is a dictionary pkg_name => pkg_uri
    let toLoad = recursiveDependencies(names);

    self.pyodide._module.locateFile = (path) => {
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

    if (Object.keys(toLoad).length === 0) {
      return Promise.resolve('No new packages to load');
    } else {
      console.log(`Loading ${Object.keys(toLoad).join(', ')}`)
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

    // Add a promise that rejects when any exceptions is thrown in the process
    // of loading a script. The promise never resolves, and we combine it
    // with other promises via Promise.race.
    let windowErrorHandler;
    let windowErrorPromise = new Promise((_res, rej) => {
      windowErrorHandler = e => rej(e.message);
      self.addEventListener('error', windowErrorHandler);
    });

    // Promises for each script load. The promises already handle error and
    // never fail.
    let scriptPromises = [];

    for (let pkg in toLoad) {
      let scriptSrc;
      let package_uri = toLoad[pkg];
      if (package_uri == 'default channel') {
        scriptSrc = `${baseURL}${pkg}.js`;
      } else {
        scriptSrc = `${package_uri}`;
      }
      console.log(`Loading ${pkg} from ${scriptSrc}`)
      scriptPromises.push(loadScript(scriptSrc).catch(() => {
        console.error(`Couldn't load package from URL ${scriptSrc}`);
        delete toLoad[pkg];
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
    for (let pkg in toLoad) {
      self.pyodide.loadedPackages[pkg] = toLoad[pkg];
      packageList.push(pkg);
    }

    let resolveMsg;
    if (packageList.length > 0) {
      let package_names = packageList.join(', ');
      resolveMsg =  `Loaded ${packageList}`;
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
