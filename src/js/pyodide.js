/**
 * The main bootstrap code for loading pyodide.
 */
import { Module, setStandardStreams, setHomeDirectory } from "./module.js";
import {
  loadScript,
  initializePackageIndex,
  _fetchBinaryFile,
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
  const fd_stdout = 1;
  Module.__Py_DumpTraceback(fd_stdout, Module._PyGILState_GetThisThreadState());
};

let fatal_error_occurred = false;
/**
 * Signal a fatal error.
 *
 * Dumps the Python traceback, shows a JavaScript traceback, and prints a clear
 * message indicating a fatal error. It then dummies out the public API so that
 * further attempts to use Pyodide will clearly indicate that Pyodide has failed
 * and can no longer be used. pyodide._module is left accessible, and it is
 * possible to continue using Pyodide for debugging purposes if desired.
 *
 * @argument e {Error} The cause of the fatal error.
 * @private
 */
Module.fatal_error = function (e) {
  if (e.pyodide_fatal_error) {
    return;
  }
  if (fatal_error_occurred) {
    console.error("Recursive call to fatal_error. Inner error was:");
    console.error(e);
    return;
  }
  // Mark e so we know not to handle it later in EM_JS wrappers
  e.pyodide_fatal_error = true;
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

let runPythonInternal_dict; // Initialized in finalizeBootstrap
/**
 * Just like `runPython` except uses a different globals dict and gets
 * `eval_code` from `_pyodide` so that it can work before `pyodide` is imported.
 * @private
 */
Module.runPythonInternal = function (code) {
  return Module._pyodide._base.eval_code(code, runPythonInternal_dict);
};

/**
 * A proxy around globals that falls back to checking for a builtin if has or
 * get fails to find a global with the given key. Note that this proxy is
 * transparent to js2python: it won't notice that this wrapper exists at all and
 * will translate this proxy to the globals dictionary.
 * @private
 */
function wrapPythonGlobals(globals_dict, builtins_dict) {
  return new Proxy(globals_dict, {
    get(target, symbol) {
      if (symbol === "get") {
        return (key) => {
          let result = target.get(key);
          if (result === undefined) {
            result = builtins_dict.get(key);
          }
          return result;
        };
      }
      if (symbol === "has") {
        return (key) => target.has(key) || builtins_dict.has(key);
      }
      return Reflect.get(target, symbol);
    },
  });
}

function unpackPyodidePy(pyodide_py_tar) {
  const fileName = "/pyodide_py.tar";
  let stream = Module.FS.open(fileName, "w");
  Module.FS.write(
    stream,
    new Uint8Array(pyodide_py_tar),
    0,
    pyodide_py_tar.byteLength,
    undefined,
    true
  );
  Module.FS.close(stream);
  const code_ptr = Module.stringToNewUTF8(`
import shutil
shutil.unpack_archive("/pyodide_py.tar", "/lib/python3.9/site-packages/")
del shutil
import importlib
importlib.invalidate_caches()
del importlib
    `);
  let errcode = Module._PyRun_SimpleString(code_ptr);
  if (errcode) {
    throw new Error("OOPS!");
  }
  Module._free(code_ptr);
  Module.FS.unlink(fileName);
}

/**
 * This function is called after the emscripten module is finished initializing,
 * so eval_code is newly available.
 * It finishes the bootstrap so that once it is complete, it is possible to use
 * the core `pyodide` apis. (But package loading is not ready quite yet.)
 * @private
 */
function finalizeBootstrap(config) {
  // First make internal dict so that we can use runPythonInternal.
  // runPythonInternal uses a separate namespace, so we don't pollute the main
  // environment with variables from our setup.
  runPythonInternal_dict = Module._pyodide._base.eval_code("{}");
  Module.importlib = Module.runPythonInternal("import importlib; importlib");
  let import_module = Module.importlib.import_module;

  Module.sys = import_module("sys");
  Module.sys.path.insert(0, config.homedir);

  // Set up globals
  let globals = Module.runPythonInternal("import __main__; __main__.__dict__");
  let builtins = Module.runPythonInternal("import builtins; builtins.__dict__");
  Module.globals = wrapPythonGlobals(globals, builtins);

  // Set up key Javascript modules.
  let importhook = Module._pyodide._importhook;
  importhook.register_js_finder();
  importhook.register_js_module("js", config.jsglobals);

  let pyodide = makePublicAPI();
  importhook.register_js_module("pyodide_js", pyodide);

  // import pyodide_py. We want to ensure that as much stuff as possible is
  // already set up before importing pyodide_py to simplify development of
  // pyodide_py code (Otherwise it's very hard to keep track of which things
  // aren't set up yet.)
  Module.pyodide_py = import_module("pyodide");
  Module.version = Module.pyodide_py.__version__;

  // copy some last constants onto public API.
  pyodide.pyodide_py = Module.pyodide_py;
  pyodide.version = Module.version;
  pyodide.globals = Module.globals;
  return pyodide;
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
 * @param {string} config.homedir - The home directory which Pyodide will use inside virtual file system
 * Default: /home/pyodide
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
  if (globalThis.__pyodide_module) {
    throw new Error("Pyodide is already loading.");
  }
  if (!config.indexURL) {
    throw new Error("Please provide indexURL parameter to loadPyodide");
  }

  loadPyodide.inProgress = true;
  // A global "mount point" for the package loaders to talk to pyodide
  // See "--export-name=__pyodide_module" in buildpkg.py
  globalThis.__pyodide_module = Module;

  const default_config = {
    fullStdLib: true,
    jsglobals: globalThis,
    stdin: globalThis.prompt ? globalThis.prompt : undefined,
    homedir: "/home/pyodide",
  };
  config = Object.assign(default_config, config);

  if (!config.indexURL.endsWith("/")) {
    config.indexURL += "/";
  }
  Module.indexURL = config.indexURL;
  let packageIndexReady = initializePackageIndex(config.indexURL);
  let pyodide_py_tar_promise = _fetchBinaryFile(
    config.indexURL,
    "pyodide_py.tar"
  );

  setStandardStreams(config.stdin, config.stdout, config.stderr);
  setHomeDirectory(config.homedir);

  let moduleLoaded = new Promise((r) => (Module.postRun = r));

  const scriptSrc = `${config.indexURL}pyodide.asm.js`;
  await loadScript(scriptSrc);

  // _createPyodideModule is specified in the Makefile by the linker flag:
  // `-s EXPORT_NAME="'_createPyodideModule'"`
  await _createPyodideModule(Module);

  // There is some work to be done between the module being "ready" and postRun
  // being called.
  await moduleLoaded;

  const pyodide_py_tar = await pyodide_py_tar_promise;
  unpackPyodidePy(pyodide_py_tar);
  Module._pyodide_init();

  let pyodide = finalizeBootstrap(config);
  // Module.runPython works starting here.

  await packageIndexReady;
  if (config.fullStdLib) {
    await loadPackage(["distutils"]);
  }
  pyodide.runPython("print('Python initialization complete')");
  return pyodide;
}
globalThis.loadPyodide = loadPyodide;
