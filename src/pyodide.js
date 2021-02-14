/**
 * The main bootstrap script for loading pyodide.
 */

globalThis.languagePluginLoader = (async () => {
  let Module = {};
  // Note: PYODIDE_BASE_URL is an environement variable replaced in
  // in this template in the Makefile. It's recommended to always set
  // languagePluginUrl in any case.
  let baseURL = self.languagePluginUrl || '{{ PYODIDE_BASE_URL }}';
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
                FS.readFile(path), {loadAsync: true,allowUndefined: true}))
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

  let loadScript;
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

  function recursiveDependencies(names, _messageCallback, errorCallback) {
    const packages = Module.packages.dependencies;
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
          errorCallback(`Loading same package ${pkgname} from ${name} and ${
              toLoad.get(pkgname)}`);
          continue;
        }
        toLoad.set(pkgname, name);
      } else if (name in packages) {
        addPackage(name);
      } else {
        errorCallback(`Skipping unknown package '${name}'`);
      }
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
        };
      };
      return baseURL + path;
    };

    if (toLoad.size === 0) {
      return Promise.resolve('No new packages to load');
    } else {
      messageCallback(`Loading ${[...toLoad.keys()].join(', ')}`)
    }

    // If running in main browser thread, try to catch errors thrown when
    // running a script. Since the script is added via a script tag, there is
    // no good way to capture errors from the script only, so try to capture
    // all errors them.
    //
    // windowErrorPromise rejects when any exceptions is thrown in the process
    // of loading a script. The promise never resolves, and we combine it
    // with other promises via Promise.race.
    let windowErrorHandler;
    let windowErrorPromise;
    if (self.document) {
      windowErrorPromise = new Promise((_res, rej) => {
        windowErrorHandler = e => {
          errorCallback(
              "Unhandled error. We don't know what it is or whether it is related to 'loadPackage' but out of an abundance of caution we will assume that loading failed.");
          errorCallback(e);
          rej(e.message);
        };
        self.addEventListener('error', windowErrorHandler);
      });
    } else {
      // This should be a promise that never resolves
      windowErrorPromise = new Promise(() => {});
    }

    // This is a collection of promises that resolve when the package's JS file
    // is loaded. The promises already handle error and never fail.
    let scriptPromises = [];

    for (let [pkg, uri] of toLoad) {
      let loaded = self.pyodide.loadedPackages[pkg];
      if (loaded !== undefined) {
        // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
        // depedency, which was previously overridden.
        if (loaded === uri || uri === DEFAULT_CHANNEL) {
          messageCallback(`${pkg} already loaded from ${loaded}`);
          continue;
        } else {
          errorCallback(`URI mismatch, attempting to load package ${pkg} from ${
              uri} while it is already loaded from ${
              loaded}. To override a dependency, load the custom package first.`);
          continue;
        }
      }
      let scriptSrc = uri === DEFAULT_CHANNEL ? `${baseURL}${pkg}.js` : uri;
      messageCallback(`Loading ${pkg} from ${scriptSrc}`);
      scriptPromises.push(loadScript(scriptSrc).catch(() => {
        errorCallback(`Couldn't load package from URL ${scriptSrc}`);
        toLoad.delete(pkg);
      }));
    }

    // When the JS loads, it synchronously adds a runDependency to emscripten.
    // It then loads the data file, and removes the runDependency from
    // emscripten. This function returns a promise that resolves when there are
    // no pending runDependencies.
    function waitRunDependency() {
      const promise = new Promise(r => {
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
    let successPromise = Promise.all(scriptPromises).then(waitRunDependency);
    try {
      await Promise.race([ successPromise, windowErrorPromise ]);
    } finally {
      delete Module.monitorRunDependencies;
      if (windowErrorHandler) {
        self.removeEventListener('error', windowErrorHandler);
      }
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
      Module.reportUndefinedSymbols();
    }
    messageCallback(resolveMsg);

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    Module.runPythonSimple('import importlib\n' +
                           'importlib.invalidate_caches()\n');
  };

  // This is a promise that is resolved iff there are no pending package loads.
  // It never fails.
  let loadPackageChain = Promise.resolve();

  /**
   * @type {object}
   *
   * Use ``Object.keys(pyodide.loadedPackages)`` to get the list of names of
   * loaded packages, and ``pyodide.loadedPackages[package_name]`` to access
   * install location for a particular ``package_name``.
   */
  Module.loadedPackages = {};

  /**
   * Load a package or a list of packages over the network.
   * This makes the files for the package available in the virtual filesystem.
   * The package needs to be imported from Python before it can be used.
   * @param {String | Array} names package name, or URL. Can be either a single
   * element, or an array
   * @param {function} messageCallback A callback, called with progress messages
   * (optional)
   * @param {function} errorCallback A callback, called with error/warning
   * messages (optional)
   * @returns {Promise} Resolves to ``undefined`` when loading is complete
   */
  Module.loadPackage =
      async function(names, messageCallback, errorCallback) {
    if (!Array.isArray(names)) {
      names = [ names ];
    }
    let promise = loadPackageChain.then(
        () => _loadPackage(names, messageCallback || console.log,
                           errorCallback || console.error));
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
    pyodide.runPythonSimple(
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
    'registerJsModule',
    'unregisterJsModule',
    'setInterruptBuffer',
  ];

  function makePublicAPI(module, public_api) {
    let namespace = {_module : module};
    module.public_api = namespace;
    for (let name of public_api) {
      namespace[name] = module[name];
    }
    return namespace;
  }

  ////////////////////////////////////////////////////////////
  // Loading Pyodide
  self.Module = Module;

  Module.noImageDecoding = true;
  Module.noAudioDecoding = true;
  Module.noWasmDecoding = true;
  Module.preloadedWasm = {};
  let isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;

  Module.fatal_error = function(e) {
    for (let [key, value] of Object.entries(Module.public_api)) {
      if (key.startsWith("_")) {
        // delete Module.public_api[key];
        continue;
      }
      // Have to do this case first because typeof(some_pyproxy) === "function".
      if (Module.PyProxy.isPyProxy(value)) {
        value.destroy();
        continue;
      }
      if (typeof (value) === "function") {
        Module.public_api[key] = function() {
          throw Error("Pyodide has suffered a fatal error, refresh the page. " +
                      "Please report this to the Pyodide maintainers.");
        }
      }
    }
    throw e;
  };

  /**
   * @member {PyProxy} pyodide_py
   * An alias to the Python pyodide package.
   */

  /**
   * @member {PyProxy} globals
   * An alias to the global Python namespace.
   *
   * An object whose attributes are members of the Python global namespace. This
   * is an alternative to :meth:`pyimport`. For example, to access the ``foo``
   * Python object from Javascript use
   * ``pyodide.globals.get("foo")``
   */

  /**
   * @member {string} version
   * The pyodide version.
   *
   * It can be either the exact release version (e.g. `0.1.0`), or
   * the latest release version followed by the number of commits since, and
   * the git hash of the current commit (e.g. `0.1.0-1-bd84646`).
   */

  /**
   * Runs a string of Python code from Javascript.
   *
   * The last part of the string may be an expression, in which case, its value
   * is returned.
   *
   * @param {string} code Python code to evaluate
   * @returns The result of the python code converted to Javascript
   */
  Module.runPython = code => Module.pyodide_py.eval_code(code, Module.globals);

  // clang-format off
  /**
   * Inspect a Python code chunk and use ``pyodide.loadPackage` to load any known 
   * packages that the code chunk imports. Uses 
   * :func:`pyodide_py.find_imports <pyodide.find\_imports>` to inspect the code.

   * For example, given the following code chunk as input
   * 
   * .. code-block:: python
   * 
   *    import numpy as np
   *    x = np.array([1, 2, 3])
   * 
   * :js:func:`loadPackagesFromImports` will call ``pyodide.loadPackage(['numpy'])``.
   * See also :js:func:`runPythonAsync`.
   *
   * @param {*} code 
   * @param {*} messageCallback 
   * @param {*} errorCallback 
   */
  Module.loadPackagesFromImports  = async function(code, messageCallback, errorCallback) {
    let imports = Module.pyodide_py.find_imports(code).toJs();
    if (imports.length === 0) {
      return;
    }
    let packageNames = Module.packages.import_name_to_package_name;
    let packages = new Set();
    for (let name of imports) {
      if (name in packageNames) {
        packages.add(packageNames[name]);
      }
    }
    if (packages.size) {
      await Module.loadPackage(
        Array.from(packages.keys()), messageCallback, errorCallback
      );
    }
  };
  // clang-format on

  /**
   * Access a Python object in the global namespace from Javascript.
   * @param {string} name Python variable name
   * @returns If the Python object is an immutable type (string, number,
   * boolean), it is converted to Javascript and returned.  For other types, a
   * `PyProxy` object is returned.
   */
  Module.pyimport = name => Module.globals[name];

  /**
   * Runs Python code, possibly asynchronously loading any known packages that
   * the code chunk imports. For example, given the following code chunk
   *
   * .. code-block:: python
   *
   *    import numpy as np
   *    x = np.array([1, 2, 3])
   *
   * pyodide will first call `pyodide.loadPackage(['numpy'])`, and then run the
   * code chunk, returning the result. Since package fetching must happen
   * asynchronously, this function returns a `Promise` which resolves to the
   * output. For example:
   *
   * .. code-block:: javascript
   *
   *    pyodide.runPythonAsync(code, messageCallback)
   *           .then((output) => handleOutput(output))
   *
   * @param {string} code Python code to evaluate
   * @param {Function} messageCallback A callback, called with progress
   * messages. (optional)
   * @param {Function} errorCallback A callback, called with error/warning
   * messages. (optional)
   */
  Module.runPythonAsync = async function(code, messageCallback, errorCallback) {
    await Module.loadPackagesFromImports(code, messageCallback, errorCallback);
    return Module.runPython(code);
  };

  // clang-format off
  /**
   * Registers the Js object ``module`` as a Js module with ``name``.
   * This module can then be imported from Python using the standard Python
   * import system. If another module by the same name has already been
   * imported, this won't have much effect unless you also delete the imported
   * module from
   * ``sys.modules``. This calls the ``pyodide_py`` api
   * :func:`pyodide.register_js_module`.
   *
   * @param {string} name Name of js module to add
   * @param {object} module Javascript object backing the module
   */
  Module.registerJsModule = function(name, module) {
    Module.pyodide_py.register_js_module(name, module);
  };

  /**
   * Unregisters a Js module with given name that has been previously registered
   * with :js:func:`registerJsModule` or :func:`pyodide.register_js_module`. If
   * a Js module with that name does not already exist, will throw an error.
   * Note that if the module has already been imported, this won't have much
   * effect unless you also delete the imported module from ``sys.modules``.
   * This calls the
   * ``pyodide_py`` api :func:`pyodide.unregister_js_module`.
   *
   * @param {string} name Name of js module to remove
   */
  Module.unregisterJsModule = function(name) {
    Module.pyodide_py.unregister_js_module(name);
  };
  // clang-format on

  Module.function_supports_kwargs = function(funcstr) {
    // This is basically a finite state machine (except for paren counting)
    // Start at beginning of argspec
    let idx = funcstr.indexOf("(") + 1;
    // States:
    // START_ARG -- Start of an argument. We leave this state when we see a non
    // whitespace character.
    //    If the first nonwhitespace character we see is `{` this is an object
    //    destructuring argument. Else it's not. When we see non whitespace goto
    //    state ARG and set `arg_is_obj_dest` true if it's "{", else false.
    // ARG -- we're in the middle of an argument. Count parens. On comma, if
    // parens_depth === 0 goto state START_ARG, on quote set
    //      set quote_start and goto state QUOTE.
    // QUOTE -- We're in a quote. Record quote_start in quote_start and look for
    // a matching end quote.
    //    On end quote, goto state ARGS. If we see "\\" goto state QUOTE_ESCAPE.
    // QUOTE_ESCAPE -- unconditionally goto state QUOTE.
    // If we see a ) when parens_depth === 0, return arg_is_obj_dest.
    let START_ARG = 1;
    let ARG = 2;
    let QUOTE = 3;
    let QUOTE_ESCAPE = 4;
    let paren_depth = 0;
    let arg_start = 0;
    let arg_is_obj_dest = false;
    let quote_start = undefined;
    let state = START_ARG;
    // clang-format off
    for (i = idx; i < funcstr.length; i++) {
      let x = funcstr[i];
      if(state === QUOTE){
        switch(x){
          case quote_start:
            // found match, go back to ARG
            state = ARG;
            continue;
          case "\\":
            state = QUOTE_ESCAPE;
            continue;
          default:
            continue;
        }
      }
      if(state === QUOTE_ESCAPE){
        state = QUOTE;
        continue;
      }
      // Skip whitespace.
      if(x === " " || x === "\n" || x === "\t"){
        continue;
      }
      if(paren_depth === 0){
        if(x === ")" && state !== QUOTE && state !== QUOTE_ESCAPE){
          // We hit closing brace which ends argspec.
          // We have to handle this up here in case argspec ends in a trailing comma
          // (if we're in state START_ARG, the next check would clobber arg_is_obj_dest).
          return arg_is_obj_dest;
        }
        if(x === ","){
          state = START_ARG;
          continue;
        }
        // otherwise fall through
      }
      if(state === START_ARG){
        // Nonwhitespace character in START_ARG so now we're in state arg.
        state = ARG;
        arg_is_obj_dest = x === "{";
        // don't continue, fall through to next switch
      }
      switch(x){
        case "[": case "{": case "(":
          paren_depth ++;
          continue;
        case "]": case "}": case ")":
          paren_depth--;
          continue;
        case "'": case '"': case '\`':
          state = QUOTE;
          quote_start = x;
          continue;
      }
    }
    // Correct exit is paren_depth === 0 && x === ")" test above.
    throw new Error("Assertion failure: this is a logic error in \
                     hiwire_function_supports_kwargs");
    // clang-format on
  };

  Module.locateFile = (path) => baseURL + path;

  let moduleLoaded = new Promise(r => Module.postRun = r);

  const scriptSrc = `${baseURL}pyodide.asm.js`;

  await loadScript(scriptSrc);

  // The emscripten module needs to be at this location for the core
  // filesystem to install itself. Once that's complete, it will be replaced
  // by the call to `makePublicAPI` with a more limited public API.
  self.pyodide = await pyodide(Module);

  // There is some work to be done between the module being "ready" and postRun
  // being called.
  await moduleLoaded;

  // Unfortunately the indentation here matters.
  Module.runPythonSimple(`
def temp(Module):
  import pyodide
  import __main__
  import builtins

  globals = __main__.__dict__
  globals.update(builtins.__dict__)

  Module.version = pyodide.__version__
  Module.globals = globals
  Module.pyodide_py = pyodide
`);
  Module.init_dict["temp"](Module);

  delete self.Module;
  let response = await fetch(`${baseURL}packages.json`);
  Module.packages = await response.json();

  fixRecursionLimit(self.pyodide);
  self.pyodide = makePublicAPI(self.pyodide, PUBLIC_API);
  self.pyodide.registerJsModule("js", globalThis);
  self.pyodide.registerJsModule("pyodide_js", self.pyodide);
})();
languagePluginLoader
