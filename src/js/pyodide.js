/**
 * The main bootstrap code for loading pyodide.
 */
import { Module } from "./module";
import {
  loadScript,
  initializePackageIndex,
  loadPackage,
} from "./load-pyodide";
import { makePublicAPI, registerJsModule } from "./api";
import "./pyproxy.gen";

import { wrapNamespace } from "./pyproxy.gen";

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
 * Dumps the Python traceback, shows a Javascript traceback, and prints a clear
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
  console.error(e);
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
Module.runPythonSimple = function (code) {
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
 * The Javascript/Wasm call stack is too small to handle the default Python call
 * stack limit of 1000 frames. Here, we determine the Javascript call stack
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

  let recursionLimit = Math.min(depth / 50, 400);
  Module.runPythonSimple(
    `import sys; sys.setrecursionlimit(int(${recursionLimit}))`
  );
}

/**
 * Load the main Pyodide wasm module and initialize it.
 *
 * Only one copy of Pyodide can be loaded in a given Javascript global scope
 * because Pyodide uses global variables to load packages. If an attempt is made
 * to load a second copy of Pyodide, :any:`loadPyodide` will throw an error.
 * (This can be fixed once `Firefox adopts support for ES6 modules in webworkers
 * <https://bugzilla.mozilla.org/show_bug.cgi?id=1247687>`_.)
 *
 * @param {{ indexURL : string, fullStdLib? : boolean = true }} config
 * @param {string} config.indexURL - The URL from which Pyodide will load
 * packages
 * @param {boolean} config.fullStdLib - Load the full Python standard library.
 * Setting this to false excludes following modules: distutils.
 * Default: true
 * @returns The :ref:`js-api-pyodide` module.
 * @memberof globalThis
 * @async
 */
export async function loadPyodide(config) {
  const default_config = { fullStdLib: true };
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
  // Note: PYODIDE_BASE_URL is an environment variable replaced in
  // in this template in the Makefile. It's recommended to always set
  // indexURL in any case.
  if (!config.indexURL) {
    throw new Error("Please provide indexURL parameter to loadPyodide");
  }
  let baseURL = config.indexURL;
  if (baseURL.endsWith(".js")) {
    baseURL = baseURL.substr(0, baseURL.lastIndexOf("/"));
  }
  if (!baseURL.endsWith("/")) {
    baseURL += "/";
  }
  let packageIndexReady = initializePackageIndex(baseURL);

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
  Module.globals = wrapNamespace(Module.globals);

  fixRecursionLimit();
  let pyodide = makePublicAPI();
  pyodide.globals = Module.globals;
  pyodide.pyodide_py = Module.pyodide_py;
  pyodide.version = Module.version;

  registerJsModule("js", globalThis);
  registerJsModule("pyodide_js", pyodide);

  await packageIndexReady;
  if (config.fullStdLib) {
    await loadPackage(["distutils"]);
  }

  return pyodide;
}
globalThis.loadPyodide = loadPyodide;

if (globalThis.languagePluginUrl) {
  console.warn(
    "languagePluginUrl is deprecated and will be removed in version 0.18.0, " +
      "instead use loadPyodide({ indexURL : <some_url>})"
  );

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
  globalThis.languagePluginLoader = loadPyodide({
    indexURL: globalThis.languagePluginUrl,
  }).then((pyodide) => (self.pyodide = pyodide));
}
