/**
 * The main bootstrap script for loading pyodide.
 */

/**
 * The :ref:`js-api-pyodide` module object. Must be present as a global variable
 * called
 * ``pyodide`` in order for package loading to work properly.
 *
 * @type Object
 */
globalThis.pyodide = {};

/**
 * Load the main Pyodide wasm module and initialize it. When finished stores the
 * Pyodide module as a global object called ``pyodide``.
 * @param {string} config.indexURL - The URL from which Pyodide will load
 * packages
 * @returns The Pyodide module.
 * @async
 */
globalThis.loadPyodide = async function(config = {}) {
  if (globalThis.__pyodideLoading) {
    if (globalThis.languagePluginURL) {
      throw new Error(
          "Pyodide is already loading because languagePluginURL is defined.");
    } else {
      throw new Error("Pyodide is already loading.");
    }
  }
  globalThis.__pyodideLoading = true;
  let Module = {};
  // Note: PYODIDE_BASE_URL is an environment variable replaced in
  // in this template in the Makefile. It's recommended to always set
  // indexURL in any case.
  let baseURL = config.indexURL || "{{ PYODIDE_BASE_URL }}";
  if (baseURL.endsWith(".js")) {
    baseURL = baseURL.substr(0, baseURL.lastIndexOf('/'));
  }
  if (!baseURL.endsWith("/")) {
    baseURL += '/';
  }

  ////////////////////////////////////////////////////////////
  // Package loading
  const DEFAULT_CHANNEL = "default channel";

  // Regexp for validating package name and URI
  const package_uri_regexp = /^.*?([^\/]*)\.js$/;

  function _uri_to_package_name(package_uri) {
    let match = package_uri_regexp.exec(package_uri);
    if (match) {
      return match[1];
    }
  };

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
    };
  } else {
    throw new Error("Cannot determine runtime environment");
  }

  function recursiveDependencies(names, _messageCallback, errorCallback,
                                 sharedLibsOnly) {
    const packages = Module.packages.dependencies;
    const loadedPackages = Module.loadedPackages;
    const sharedLibraries = Module.packages.shared_library;
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
      if (pkgname !== undefined) {
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
        };
      };
      return baseURL + path;
    };

    if (toLoad.size === 0) {
      return Promise.resolve('No new packages to load');
    } else {
      let packageNames = Array.from(toLoad.keys()).join(', ');
      messageCallback(`Loading ${packageNames}`);
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
      let loaded = Module.loadedPackages[pkg];
      if (loaded !== undefined) {
        // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
        // depedency, which was previously overridden.
        if (loaded === uri || uri === DEFAULT_CHANNEL) {
          messageCallback(`${pkg} already loaded from ${loaded}`);
          continue;
        } else {
          errorCallback(
              `URI mismatch, attempting to load package ${pkg} from ${uri} ` +
              `while it is already loaded from ${
                  loaded}. To override a dependency, ` +
              `load the custom package first.`);
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
      Module.loadedPackages[pkg] = uri;
      packageList.push(pkg);
    }

    let resolveMsg;
    if (packageList.length > 0) {
      let packageNames = packageList.join(', ');
      resolveMsg = `Loaded ${packageNames}`;
    } else {
      resolveMsg = 'No packages loaded';
    }

    Module.reportUndefinedSymbols();

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
   *
   * The list of packages that Pyodide has loaded.
   * Use ``Object.keys(pyodide.loadedPackages)`` to get the list of names of
   * loaded packages, and ``pyodide.loadedPackages[package_name]`` to access
   * install location for a particular ``package_name``.
   *
   * @type {object}
   */
  Module.loadedPackages = {};

  /**
   * Load a package or a list of packages over the network. This installs the
   * package in the virtual filesystem. The package needs to be imported from
   * Python before it can be used.
   * @param {String | Array} names Either a single package name or URL or a list
   * of them. URLs can be absolute or relative. The URLs must have file name
   * ``<package-name>.js`` and there must be a file called
   * ``<package-name>.data`` in the same directory.
   * @param {function} messageCallback A callback, called with progress messages
   *    (optional)
   * @param {function} errorCallback A callback, called with error/warning
   *    messages (optional)
   * @async
   */
  Module.loadPackage = async function(names, messageCallback, errorCallback) {
    if (!Array.isArray(names)) {
      names = [ names ];
    }
    // get shared library packages and load those first
    // otherwise bad things happen with linking them in firefox.
    let sharedLibraryNames = [];
    try {
      let sharedLibraryPackagesToLoad =
          recursiveDependencies(names, messageCallback, errorCallback, true);
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
      get : function(obj, prop) {
        if (prop === 'handle') {
          return function(bytes, name) {
            obj[prop].apply(obj, arguments);
            this["asyncWasmLoadPromise"] =
                this["asyncWasmLoadPromise"].then(function() {
                  Module.loadDynamicLibrary(name,
                                            {global : true, nodelete : true})
                });
          }
        } else {
          return obj[prop];
        }
      }
    };
    var loadPluginOverride = new Proxy(oldPlugin, dynamicLoadHandler);
    // restore the preload plugin
    Module.preloadPlugins.unshift(loadPluginOverride);

    let promise = loadPackageChain.then(
        () => _loadPackage(sharedLibraryNames, messageCallback || console.log,
                           errorCallback || console.error));
    loadPackageChain = loadPackageChain.then(() => promise.catch(() => {}));
    await promise;
    Module.preloadPlugins.shift(loadPluginOverride);

    promise = loadPackageChain.then(
        () => _loadPackage(names, messageCallback || console.log,
                           errorCallback || console.error));
    loadPackageChain = loadPackageChain.then(() => promise.catch(() => {}));
    await promise;
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
    pyodide.runPythonSimple(
        `import sys; sys.setrecursionlimit(int(${recursionLimit}))`);
  };

  ////////////////////////////////////////////////////////////
  // Rearrange namespace for public API
  // clang-format off
  let PUBLIC_API = [
    'globals',
    'pyodide_py',
    'version',
    'loadPackage',
    'loadPackagesFromImports',
    'loadedPackages',
    'isPyProxy',
    'pyimport',
    'runPython',
    'runPythonAsync',
    'registerJsModule',
    'unregisterJsModule',
    'setInterruptBuffer',
    'toPy',
    'PythonError',
  ];
  // clang-format on

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

  Module.noImageDecoding = true;
  Module.noAudioDecoding = true;
  Module.noWasmDecoding =
      false; // we preload wasm using the built in plugin now
  Module.preloadedWasm = {};

  let fatal_error_occurred = false;
  Module.fatal_error = function(e) {
    if (fatal_error_occurred) {
      console.error("Recursive call to fatal_error. Inner error was:");
      console.error(e);
      return;
    }
    fatal_error_occurred = true;
    console.error("Pyodide has suffered a fatal error. " +
                  "Please report this to the Pyodide maintainers.");
    console.error("The cause of the fatal error was:")
    console.error(e);
    try {
      let fd_stdout = 1;
      Module.__Py_DumpTraceback(fd_stdout,
                                Module._PyGILState_GetThisThreadState());
      for (let key of PUBLIC_API) {
        if (key === "version") {
          continue;
        }
        Object.defineProperty(Module.public_api, key, {
          enumerable : true,
          configurable : true,
          get : () => {
            throw new Error(
                "Pyodide already fatally failed and can no longer be used.");
          }
        });
      }
    } catch (e) {
      console.error("Another error occurred while handling the fatal error:");
      console.error(e);
    }
    throw e;
  };

  /**
   * An alias to the Python :py:mod:`pyodide` package.
   *
   * You can use this to call functions defined in the Pyodide Python package
   * from Javascript.
   *
   * @type {PyProxy}
   */
  Module.pyodide_py = {}; // actually defined in runPythonSimple below

  /**
   *
   * An alias to the global Python namespace.
   *
   * For example, to access a variable called ``foo`` in the Python global
   * scope, use ``pyodide.globals.get("foo")``
   *
   * @type {PyProxy}
   */
  Module.globals = {}; // actually defined in runPythonSimple below

  // clang-format off
  /**
   * A Javascript error caused by a Python exception.
   *
   * In order to reduce the risk of large memory leaks, the ``PythonError``
   * contains no reference to the Python exception that caused it. You can find
   * the actual Python exception that caused this error as `sys.last_value
   * <https://docs.python.org/3/library/sys.html#sys.last_value>`_.
   *
   * See :ref:`type-translations-errors` for more information.
   *
   * .. admonition:: Avoid Stack Frames
   *    :class: warning
   *
   *    If you make a :any:`PyProxy` of ``sys.last_value``, you should be
   *    especially careful to :any:`destroy() <PyProxy.destroy>` it when you are
   *    done. You may leak a large amount of memory including the local
   *    variables of all the stack frames in the traceback if you don't. The
   *    easiest way is to only handle the exception in Python.
   *
   * @class
   */
  Module.PythonError = class PythonError {
    // actually defined in error_handling.c. TODO: would be good to move this
    // documentation and the definition of PythonError to error_handling.js
    constructor(){
      /**
       * The Python traceback.
       * @type {string}
       */
      this.message;
    }
  };
  // clang-format on

  /**
   *
   * The Pyodide version.
   *
   * It can be either the exact release version (e.g. ``0.1.0``), or
   * the latest release version followed by the number of commits since, and
   * the git hash of the current commit (e.g. ``0.1.0-1-bd84646``).
   *
   * @type {string}
   */
  Module.version = ""; // Hack to make jsdoc behave

  /**
   * Run Python code in the simplest way possible. The primary purpose of this
   * method is for bootstrapping. It is also useful for debugging: If the Python
   * interpreter is initialized successfully then it should be possible to use
   * this method to run Python code even if everything else in the Pyodide
   * `core` module fails.
   *
   * The differences are:
   *    1. `runPythonSimple` doesn't return anything (and so won't leak
   *        PyProxies)
   *    2. `runPythonSimple` doesn't require access to any state on the
   *       Javascript `pyodide` module.
   *    3. `runPython` uses `pyodide.eval_code`, whereas `runPythonSimple` uses
   *       `PyRun_String` which is the C API for `eval` / `exec`.
   *    4. `runPythonSimple` runs with `globals` a separate dict which is called
   *       `init_dict` (keeps global state private)
   *    5. `runPythonSimple` doesn't dedent the argument
   *
   * When `core` initialization is completed, the globals for `runPythonSimple`
   * is made available as `Module.init_dict`.
   *
   * @private
   */
  Module.runPythonSimple = function(code) {
    let code_c_string = Module.stringToNewUTF8(code);
    let errcode;
    try {
      errcode = Module._run_python_simple_inner(code_c_string);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module._free(code_c_string);
    }
    if (errcode === -1) {
      Module._pythonexc2js();
    }
  };

  /**
   * Runs a string of Python code from Javascript.
   *
   * The last part of the string may be an expression, in which case, its value
   * is returned.
   *
   * @param {string} code Python code to evaluate
   * @param {dict} globals An optional Python dictionary to use as the globals.
   *        Defaults to :any:`pyodide.globals`. Uses the Python API
   *        :any:`pyodide.eval_code` to evaluate the code.
   * @returns The result of the Python code translated to Javascript. See the
   *          documentation for :any:`pyodide.eval_code` for more info.
   */
  Module.runPython = function(code, globals = Module.globals) {
    return Module.pyodide_py.eval_code(code, globals);
  };

  // clang-format off
  /**
   * Inspect a Python code chunk and use :js:func:`pyodide.loadPackage` to
   * install any known packages that the code chunk imports. Uses the Python API
   * :func:`pyodide.find\_imports` to inspect the code.
   *
   * For example, given the following code as input
   *
   * .. code-block:: python
   *
   *    import numpy as np x = np.array([1, 2, 3])
   *
   * :js:func:`loadPackagesFromImports` will call
   * ``pyodide.loadPackage(['numpy'])``. See also :js:func:`runPythonAsync`.
   *
   * @param {string} code The code to inspect.
   * @param {Function} messageCallback The ``messageCallback`` argument of
   * :any:`pyodide.loadPackage` (optional).
   * @param {Function} errorCallback The ``errorCallback`` argument of
   * :any:`pyodide.loadPackage` (optional).
   * @async
   */
  Module.loadPackagesFromImports = async function(code, messageCallback, errorCallback) {
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
   *
   * @deprecated This function will be removed in version 0.18.0. Use
   *    :any:`pyodide.globals.get('key') <pyodide.globals>` instead.
   *
   * @param {string} name Python variable name
   * @returns The Python object translated to Javascript.
   */
  Module.pyimport = name => {
    console.warn(
        "Access to the Python global namespace via pyodide.pyimport is deprecated and " +
        "will be removed in version 0.18.0. Use pyodide.globals.get('key') instead.");
    return Module.globals.get(name);
  };

  /**
   * Runs Python code, possibly asynchronously loading any known packages that
   * the code imports. For example, given the following code
   *
   * .. code-block:: python
   *
   *    import numpy as np
   *    x = np.array([1, 2, 3])
   *
   * Pyodide will first call :any:`pyodide.loadPackage(['numpy'])
   * <pyodide.loadPackage>`, and then run the code using the Python API
   * :any:`pyodide.eval_code_async`, returning the result. The code is compiled
   * with `PyCF_ALLOW_TOP_LEVEL_AWAIT
   * <https://docs.python.org/3/library/ast.html?highlight=pycf_allow_top_level_await#ast.PyCF_ALLOW_TOP_LEVEL_AWAIT>`_.
   *
   * For example:
   *
   * .. code-block:: pyodide
   *
   *    let result = await pyodide.runPythonAsync(`
   *        # numpy will automatically be loaded by loadPackagesFromImports
   *        import numpy as np
   *        # we can use top level await
   *        from js import fetch
   *        response = await fetch("./packages.json")
   *        packages = await response.json()
   *        # If final statement is an expression, its value is returned to
   * Javascript len(packages.dependencies.object_keys())
   *    `);
   *    console.log(result); // 72
   *
   * @param {string} code Python code to evaluate
   * @param {Function} messageCallback The ``messageCallback`` argument of
   * :any:`pyodide.loadPackage`.
   * @param {Function} errorCallback The ``errorCallback`` argument of
   * :any:`pyodide.loadPackage`.
   * @returns The result of the Python code translated to Javascript.
   * @async
   */
  Module.runPythonAsync = async function(code, messageCallback, errorCallback) {
    await Module.loadPackagesFromImports(code, messageCallback, errorCallback);
    let coroutine = Module.pyodide_py.eval_code_async(code, Module.globals);
    try {
      let result = await coroutine;
      return result;
    } finally {
      coroutine.destroy();
    }
  };

  // clang-format off
  /**
   * Registers the Javascript object ``module`` as a Javascript module named
   * ``name``. This module can then be imported from Python using the standard
   * Python import system. If another module by the same name has already been
   * imported, this won't have much effect unless you also delete the imported
   * module from ``sys.modules``. This calls the ``pyodide_py`` API
   * :func:`pyodide.register_js_module`.
   *
   * @param {string} name Name of the Javascript module to add
   * @param {object} module Javascript object backing the module
   */
  Module.registerJsModule = function(name, module) {
    Module.pyodide_py.register_js_module(name, module);
  };

  /**
   * Unregisters a Javascript module with given name that has been previously
   * registered with :js:func:`pyodide.registerJsModule` or
   * :func:`pyodide.register_js_module`. If a Javascript module with that name
   * does not already exist, will throw an error. Note that if the module has
   * already been imported, this won't have much effect unless you also delete
   * the imported module from ``sys.modules``. This calls the ``pyodide_py`` API
   * :func:`pyodide.unregister_js_module`.
   *
   * @param {string} name Name of the Javascript module to remove
   */
  Module.unregisterJsModule = function(name) {
    Module.pyodide_py.unregister_js_module(name);
  };
  // clang-format on

  /**
   * Convert the Javascript object to a Python object as best as possible.
   *
   * This is similar to :any:`JsProxy.to_py` but for use from Javascript. If the
   * object is immutable or a :any:`PyProxy`, it will be returned unchanged. If
   * the object cannot be converted into Python, it will be returned unchanged.
   *
   * See :ref:`type-translations-jsproxy-to-py` for more information.
   *
   * @param {*} obj
   * @param {number} depth Optional argument to limit the depth of the
   * conversion.
   * @returns {PyProxy} The object converted to Python.
   */
  Module.toPy = function(obj, depth = -1) {
    // No point in converting these, it'd be dumb to proxy them so they'd just
    // get converted back by `js2python` at the end
    // clang-format off
    switch (typeof obj) {
      case "string":
      case "number":
      case "boolean":
      case "bigint":
      case "undefined":
        return obj;
    }
    // clang-format on
    if (!obj || Module.isPyProxy(obj)) {
      return obj;
    }
    let obj_id = 0;
    let py_result = 0;
    let result = 0;
    try {
      obj_id = Module.hiwire.new_value(obj);
      py_result = Module.__js2python_convert(obj_id, new Map(), depth);
      // clang-format off
      if(py_result === 0){
        // clang-format on
        Module._pythonexc2js();
      }
      if (Module._JsProxy_Check(py_result)) {
        // Oops, just created a JsProxy. Return the original object.
        return obj;
        // return Module.pyproxy_new(py_result);
      }
      result = Module._python2js(py_result);
      // clang-format off
      if (result === 0) {
        // clang-format on
        Module._pythonexc2js();
      }
    } finally {
      Module.hiwire.decref(obj_id);
      Module._Py_DecRef(py_result);
    }
    return Module.hiwire.pop_value(result);
  };
  /**
   * Is the argument a :any:`PyProxy`?
   * @param jsobj {any} Object to test.
   * @returns {bool} Is ``jsobj`` a :any:`PyProxy`?
   */
  Module.isPyProxy = function(jsobj) {
    return !!jsobj && jsobj.$$ !== undefined && jsobj.$$.type === 'PyProxy';
  };

  Module.locateFile = (path) => baseURL + path;

  let moduleLoaded = new Promise(r => Module.postRun = r);

  const scriptSrc = `${baseURL}pyodide.asm.js`;

  await loadScript(scriptSrc);

  // _createPyodideModule is specified in the Makefile by the linker flag:
  // `-s EXPORT_NAME="'_createPyodideModule'"`
  await _createPyodideModule(Module);

  // There is some work to be done between the module being "ready" and postRun
  // being called.
  await moduleLoaded;

  // Bootstrap step: `runPython` needs access to `Module.globals` and
  // `Module.pyodide_py`. Use `runPythonSimple` to add these. runPythonSimple
  // doesn't dedent the argument so the indentation matters.
  Module.runPythonSimple(`
def temp(Module):
  import pyodide
  import __main__
  import builtins

  globals = __main__.__dict__
  globals.update(builtins.__dict__)

  Module.version = pyodide.__version__
  Module.globals = globals
  Module.builtins = builtins.__dict__
  Module.pyodide_py = pyodide
`);

  Module.saveState = () => Module.pyodide_py._state.save_state();
  Module.restoreState = (state) =>
      Module.pyodide_py._state.restore_state(state);

  Module.init_dict.get("temp")(Module);
  // Module.runPython works starting from here!

  // Wrap "globals" in a special Proxy that allows `pyodide.globals.x` access.
  // TODO: Should we have this?
  Module.globals = Module.wrapNamespace(Module.globals);

  let response = await fetch(`${baseURL}packages.json`);
  Module.packages = await response.json();

  fixRecursionLimit(Module);
  let pyodide = makePublicAPI(Module, PUBLIC_API);
  Module.registerJsModule("js", globalThis);
  Module.registerJsModule("pyodide_js", pyodide);
  globalThis.pyodide = pyodide;
  return pyodide;
};

if (globalThis.languagePluginUrl) {
  console.warn(
      "languagePluginUrl is deprecated and will be removed in version 0.18.0, " +
      "instead use loadPyodide({ indexURL : <some_url>})");

  /**
   * A deprecated parameter that specifies the Pyodide ``indexURL``. If present,
   * Pyodide will automatically invoke
   * ``loadPyodide({indexURL : languagePluginUrl})``
   * and will store the resulting promise in
   * :any:`globalThis.languagePluginLoader`. Use :any:`loadPyodide`
   * directly instead of defining this.
   *
   * @type String
   * @deprecated Will be removed in version 0.18.0
   */
  globalThis.languagePluginUrl;

  /**
   * A deprecated promise that resolves to ``undefined`` when Pyodide is
   * finished loading. Only created if :any:`languagePluginUrl` is
   * defined. Instead use :any:`loadPyodide`.
   *
   * @type Promise
   * @deprecated Will be removed in version 0.18.0
   */
  globalThis.languagePluginLoader =
      loadPyodide({indexURL : globalThis.languagePluginUrl});
}
