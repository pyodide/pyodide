/**
 * The main bootstrap code for loading pyodide.
 */
import { Module, setStandardStreams } from "./module.js";
import {
  loadScript,
  initializePackageIndex,
  loadPackage,
} from "./load-pyodide.js";
import { makePublicAPI, registerJsModule } from "./api.js";
import "./pyproxy.gen.js";

/**
 * @typedef {import('./pyproxy.gen').PyProxy} PyProxy
 * @typedef {import('./pyproxy.gen').PyProxyWithLength} PyProxyWithLength
 * @typedef {import('./pyproxy.gen').PyProxyWithGet} PyProxyWithGet
 * @typedef {import('./pyproxy.gen').PyProxyWithSet} PyProxyWithSet
 * @typedef {import('./pyproxy.gen').PyProxyWithHas} PyProxyWithHas
 * @typedef {import('./pyproxy.gen').PyProxyIterable} PyProxyIterable
 * @typedef {import('./pyproxy.gen').PyProxyIterator} PyProxyIterator
 * @typedef {import('./pyproxy.gen').PyProxyAwaitable} PyProxyAwaitable
 * @typedef {import('./pyproxy.gen').PyProxyBuffer} PyProxyBuffer
 * @typedef {import('./pyproxy.gen').PyProxyCallable} PyProxyCallable
 *
 * @typedef {import('./pyproxy.gen').Py2JsResult} Py2JsResult
 *
 * @typedef {import('./pyproxy.gen').TypedArray} TypedArray
 * @typedef {import('./pyproxy.gen').PyBuffer} PyBuffer
 */

/**
 * Dump the Python traceback to the browser console.
 *
 * @private
 */
Module.dump_traceback = function () {
  let fd_stdout = 1;
  Module.__Py_DumpTraceback(fd_stdout, Module._PyGILState_GetThisThreadState());
};

let fatal_error_occurred = false;
/**
 * Signal a fatal error.
 *
 * Dumps the Python traceback, shows a JavaScript traceback, and prints a clear
 * message indicating a fatal error. It then dummies out the public API so that
 * further attempts to use Pyodide will clearly indicate that Pyodide has failed
 * and can no longer be used. pyodide._module is left accessible and it is
 * possible to continue using Pyodide for debugging purposes if desired.
 *
 * @argument e {Error} The cause of the fatal error.
 * @private
 */
Module.fatal_error = function (e) {
  if (fatal_error_occurred) {
    console.error("Recursive call to fatal_error. Inner error was:");
    console.error(e);
    return;
  }
  fatal_error_occurred = true;
  console.error(
    "Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers."
  );
  console.error("The cause of the fatal error was:");
  if (Module.inTestHoist) {
    // Test hoist won't print the error object in a useful way so convert it to
    // string.
    console.error(e.toString());
    console.error(e.stack);
  } else {
    console.error(e);
  }
  try {
    Module.dump_traceback();
    for (let key of Object.keys(Module.public_api)) {
      if (key.startsWith("_") || key === "version") {
        continue;
      }
      Object.defineProperty(Module.public_api, key, {
        enumerable: true,
        configurable: true,
        get: () => {
          throw new Error(
            "Pyodide already fatally failed and can no longer be used."
          );
        },
      });
    }
    if (Module.on_fatal) {
      Module.on_fatal(e);
    }
  } catch (err2) {
    console.error("Another error occurred while handling the fatal error:");
    console.error(err2);
  }
  throw e;
};

Module.runPythonInternal = function (code) {
  return Module._pyodide._base.eval_code(code, Module.runPythonInternal_dict);
};

/**
 * The JavaScript/Wasm call stack is too small to handle the default Python call
 * stack limit of 1000 frames. Here, we determine the JavaScript call stack
 * depth available, and then divide by 50 (determined heuristically) to set the
 * maximum Python call stack depth.
 *
 * @private
 */
function fixRecursionLimit() {
  let depth = 0;
  function recurse() {
    depth += 1;
    recurse();
  }
  try {
    recurse();
  } catch (err) {}

  let recursionLimit = Math.min(depth / 25, 500);
  Module.runPythonInternal(
    `import sys; sys.setrecursionlimit(int(${recursionLimit}))`
  );
}
/**
 * Load the main Pyodide wasm module and initialize it.
 *
 * Only one copy of Pyodide can be loaded in a given JavaScript global scope
 * because Pyodide uses global variables to load packages. If an attempt is made
 * to load a second copy of Pyodide, :any:`loadPyodide` will throw an error.
 * (This can be fixed once `Firefox adopts support for ES6 modules in webworkers
 * <https://bugzilla.mozilla.org/show_bug.cgi?id=1247687>`_.)
 *
 * @param {string} config.indexURL - The URL from which Pyodide will load
 * packages
 * @param {boolean} config.fullStdLib - Load the full Python standard library.
 * Setting this to false excludes following modules: distutils.
 * Default: true
 * @param {undefined | function(): string} config.stdin - Override the standard input callback. Should ask the user for one line of input.
 * Default: undefined
 * @param {undefined | function(string)} config.stdout - Override the standard output callback.
 * Default: undefined
 * @param {undefined | function(string)} config.stderr - Override the standard error output callback.
 * Default: undefined
 * @returns The :ref:`js-api-pyodide` module.
 * @memberof globalThis
 * @async
 */
export async function loadPyodide(config) {
  const default_config = {
    fullStdLib: true,
    jsglobals: globalThis,
    stdin: globalThis.prompt ? globalThis.prompt : undefined,
  };
  config = Object.assign(default_config, config);
  if (globalThis.__pyodide_module) {
    if (globalThis.languagePluginURL) {
      throw new Error(
        "Pyodide is already loading because languagePluginURL is defined."
      );
    } else {
      throw new Error("Pyodide is already loading.");
    }
  }
  // A global "mount point" for the package loaders to talk to pyodide
  // See "--export-name=__pyodide_module" in buildpkg.py
  globalThis.__pyodide_module = Module;
  loadPyodide.inProgress = true;
  if (!config.indexURL) {
    throw new Error("Please provide indexURL parameter to loadPyodide");
  }
  let baseURL = config.indexURL;
  if (!baseURL.endsWith("/")) {
    baseURL += "/";
  }
  Module.indexURL = baseURL;
  let packageIndexReady = initializePackageIndex(baseURL);

  setStandardStreams(config.stdin, config.stdout, config.stderr);

  Module.locateFile = (path) => baseURL + path;
  let moduleLoaded = new Promise((r) => (Module.postRun = r));

  const scriptSrc = `${baseURL}pyodide.asm.js`;
  await loadScript(scriptSrc);

  // _createPyodideModule is specified in the Makefile by the linker flag:
  // `-s EXPORT_NAME="'_createPyodideModule'"`
  await _createPyodideModule(Module);

  // There is some work to be done between the module being "ready" and postRun
  // being called.
  await moduleLoaded;

  // Bootstrap steps:
  //
  //   1. We want to use runPythonInternal_dict to keep
  //   2. _pyodide_core is ready now so we can call _pyodide._importhook.register_js_finder
  //   3. Use the jsfinder to register the js and pyodide_js packages
  //   4. Import pyodide, this requires _pyodide_core, js and pyodide_js to be
  //      ready.
  //   5. Add the pyodide_py and Python __main__.__dict__ objects to pyodide_js

  Module.runPythonInternal_dict = Module._pyodide._base.eval_code("{}");

  fixRecursionLimit();

  Module._pyodide._importhook.register_js_finder();
  Module._pyodide._importhook.register_js_module("js", config.jsglobals);

  let pyodide = makePublicAPI();
  Module._pyodide._importhook.register_js_module("pyodide_js", pyodide);

  Module.pyodide_py = Module.runPythonInternal("import pyodide; pyodide");
  Module.version = Module.pyodide_py.__version__;
  Module.globals = Module.runPythonInternal(
    "import __main__; __main__.__dict__"
  );
  Module.builtins = Module.runPythonInternal(
    "import builtins; builtins.__dict__"
  );

  // Module.runPython works starting from here!

  pyodide.globals = new Proxy(Module.globals, {
    get(target, symbol) {
      if (symbol === "get") {
        return (key) => {
          let result = target.get(key);
          if (result === undefined) {
            result = Module.builtins.get(key);
          }
          return result;
        };
      }
      if (symbol === "has") {
        return (key) => target.has(key) || Module.builtins.has(key);
      }
      return Reflect.get(target, symbol);
    },
  });
  pyodide.pyodide_py = Module.pyodide_py;
  pyodide.version = Module.version;

  await packageIndexReady;
  if (config.fullStdLib) {
    await loadPackage(["distutils"]);
  }

  return pyodide;
}
globalThis.loadPyodide = loadPyodide;
