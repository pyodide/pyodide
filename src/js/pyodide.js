"use strict";
import { Module } from "./module";
import { loadScript, initializePackageIndex } from "./load_package";
import { makePublicNamespace } from "./api";

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

////////////////////////////////////////////////////////////
// Fix Python recursion limit
function fixRecursionLimit() {
  // The Javascript/Wasm call stack may be too small to handle the default
  // Python call stack limit of 1000 frames. Here, we determine the Javascript
  // call stack depth available, and then divide by 50 (determined
  // heuristically) to set the maximum Python call stack depth.

  let depth = 0;
  function recurse() {
    depth += 1;
    recurse();
  }
  try {
    recurse();
  } catch (err) {}

  let recursionLimit = depth / 50;
  if (recursionLimit > 1000) {
    recursionLimit = 1000;
  }
  Module.runPythonSimple(
    `import sys; sys.setrecursionlimit(int(${recursionLimit}))`
  );
}

let fatal_error_occurred = false;
Module.fatal_error = function (e) {
  if (fatal_error_occurred) {
    console.error("Recursive call to fatal_error. Inner error was:");
    console.error(e);
    return;
  }
  fatal_error_occurred = true;
  console.error(
    "Pyodide has suffered a fatal error. " +
      "Please report this to the Pyodide maintainers."
  );
  console.error("The cause of the fatal error was:");
  console.error(e);
  try {
    let fd_stdout = 1;
    Module.__Py_DumpTraceback(
      fd_stdout,
      Module._PyGILState_GetThisThreadState()
    );
    for (let key of Object.keys(Module.public_api)) {
      if (key === "version" || key === "_module") {
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
  } catch (e) {
    console.error("Another error occurred while handling the fatal error:");
    console.error(e);
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

let __pyodideLoading = false;

/**
 * Load the main Pyodide wasm module and initialize it. When finished stores the
 * Pyodide module as a global object called ``pyodide``.
 * @param {string} config.indexURL - The URL from which Pyodide will load
 * packages
 * @returns The Pyodide module.
 * @async
 */
export default async function loadPyodide(config = {}) {
  if (__pyodideLoading) {
    if (globalThis.languagePluginURL) {
      throw new Error(
        "Pyodide is already loading because languagePluginURL is defined."
      );
    } else {
      throw new Error("Pyodide is already loading.");
    }
  }
  let baseURL = config.indexURL || "./";
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
  Module.globals = Module.wrapNamespace(Module.globals);

  fixRecursionLimit(Module);
  let pyodide = makePublicNamespace();
  Module.registerJsModule("js", globalThis);
  Module.registerJsModule("pyodide_js", pyodide);
  globalThis.pyodide = pyodide;
  await packageIndexReady;
  return pyodide;
}

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
  });
}
