/**
 * The main bootstrap code for loading pyodide.
 */
import { Module, setStandardStreams, setHomeDirectory, API } from "./module.js";
import { loadScript, _loadBinaryFile, initNodeModules } from "./compat.js";
import { initializePackageIndex, loadPackage } from "./load-package.js";
import { makePublicAPI, PyodideInterface } from "./api.js";
import "./error_handling.gen.js";

import { PyProxy, PyProxyDict, Py2JsResult } from "./pyproxy.gen";

export {
  PyProxy,
  PyProxyWithLength,
  PyProxyDict,
  PyProxyWithGet,
  PyProxyWithSet,
  PyProxyWithHas,
  PyProxyIterable,
  PyProxyIterator,
  PyProxyAwaitable,
  PyProxyBuffer,
  PyProxyCallable,
  Py2JsResult,
  TypedArray,
  PyBuffer,
} from "./pyproxy.gen";

let runPythonInternal_dict: PyProxy; // Initialized in finalizeBootstrap
/**
 * Just like `runPython` except uses a different globals dict and gets
 * `eval_code` from `_pyodide` so that it can work before `pyodide` is imported.
 * @private
 */
API.runPythonInternal = function (code: string): Py2JsResult {
  return API._pyodide._base.eval_code(code, runPythonInternal_dict);
};

/**
 * A proxy around globals that falls back to checking for a builtin if has or
 * get fails to find a global with the given key. Note that this proxy is
 * transparent to js2python: it won't notice that this wrapper exists at all and
 * will translate this proxy to the globals dictionary.
 * @private
 */
function wrapPythonGlobals(
  globals_dict: PyProxyDict,
  builtins_dict: PyProxyDict
) {
  return new Proxy(globals_dict, {
    get(target, symbol) {
      if (symbol === "get") {
        return (key: any) => {
          let result = target.get(key);
          if (result === undefined) {
            result = builtins_dict.get(key);
          }
          return result;
        };
      }
      if (symbol === "has") {
        return (key: any) => target.has(key) || builtins_dict.has(key);
      }
      return Reflect.get(target, symbol);
    },
  });
}

function unpackPyodidePy(pyodide_py_tar: Uint8Array) {
  const fileName = "/pyodide_py.tar";
  let stream = Module.FS.open(fileName, "w");
  Module.FS.write(
    stream,
    pyodide_py_tar,
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
function finalizeBootstrap(config: ConfigType) {
  // First make internal dict so that we can use runPythonInternal.
  // runPythonInternal uses a separate namespace, so we don't pollute the main
  // environment with variables from our setup.
  runPythonInternal_dict = API._pyodide._base.eval_code("{}") as PyProxy;
  API.importlib = API.runPythonInternal("import importlib; importlib");
  let import_module = API.importlib.import_module;

  API.sys = import_module("sys");
  API.sys.path.insert(0, config.homedir);

  // Set up globals
  let globals = API.runPythonInternal(
    "import __main__; __main__.__dict__"
  ) as PyProxyDict;
  let builtins = API.runPythonInternal(
    "import builtins; builtins.__dict__"
  ) as PyProxyDict;
  API.globals = wrapPythonGlobals(globals, builtins);

  // Set up key Javascript modules.
  let importhook = API._pyodide._importhook;
  importhook.register_js_finder();
  importhook.register_js_module("js", config.jsglobals);

  let pyodide = makePublicAPI();
  importhook.register_js_module("pyodide_js", pyodide);

  // import pyodide_py. We want to ensure that as much stuff as possible is
  // already set up before importing pyodide_py to simplify development of
  // pyodide_py code (Otherwise it's very hard to keep track of which things
  // aren't set up yet.)
  API.pyodide_py = import_module("pyodide");
  API.package_loader = import_module("pyodide._package_loader");
  API.version = API.pyodide_py.__version__;

  // copy some last constants onto public API.
  pyodide.pyodide_py = API.pyodide_py;
  pyodide.version = API.version;
  pyodide.globals = API.globals;
  return pyodide;
}

declare function _createPyodideModule(Module: any): Promise<void>;

/**
 * See documentation for loadPyodide.
 * @private
 */
type ConfigType = {
  indexURL: string;
  homedir?: string;
  fullStdLib?: boolean;
  stdin?: () => string;
  stdout?: (msg: string) => void;
  stderr?: (msg: string) => void;
  jsglobals?: object;
};

/**
 * Load the main Pyodide wasm module and initialize it.
 *
 * Only one copy of Pyodide can be loaded in a given JavaScript global scope
 * because Pyodide uses global variables to load packages. If an attempt is made
 * to load a second copy of Pyodide, :any:`loadPyodide` will throw an error.
 * (This can be fixed once `Firefox adopts support for ES6 modules in webworkers
 * <https://bugzilla.mozilla.org/show_bug.cgi?id=1247687>`_.)
 *
 * @returns The :ref:`js-api-pyodide` module.
 * @memberof globalThis
 * @async
 */
export async function loadPyodide(config: {
  /**
   * The URL from which Pyodide will load packages
   */
  indexURL: string;

  /**
   * The home directory which Pyodide will use inside virtual file system. Default: "/home/pyodide"
   */
  homedir?: string;

  /** Load the full Python standard library.
   * Setting this to false excludes following modules: distutils.
   * Default: true
   */
  fullStdLib?: boolean;
  /**
   * Override the standard input callback. Should ask the user for one line of input.
   */
  stdin?: () => string;
  /**
   * Override the standard output callback.
   * Default: undefined
   */
  stdout?: (msg: string) => void;
  /**
   * Override the standard error output callback.
   * Default: undefined
   */
  stderr?: (msg: string) => void;
  jsglobals?: object;
}): Promise<PyodideInterface> {
  if ((loadPyodide as any).inProgress) {
    throw new Error("Pyodide is already loading.");
  }
  if (!config.indexURL) {
    throw new Error("Please provide indexURL parameter to loadPyodide");
  }
  (loadPyodide as any).inProgress = true;

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
  await initNodeModules();
  let packageIndexReady = initializePackageIndex(config.indexURL);
  let pyodide_py_tar_promise = _loadBinaryFile(
    config.indexURL,
    "pyodide_py.tar"
  );

  setStandardStreams(config.stdin, config.stdout, config.stderr);
  setHomeDirectory(config.homedir);

  let moduleLoaded = new Promise((r) => (Module.postRun = r));

  // locateFile tells Emscripten where to find the data files that initialize
  // the file system.
  Module.locateFile = (path: string) => config.indexURL + path;
  const scriptSrc = `${config.indexURL}pyodide.asm.js`;
  await loadScript(scriptSrc);

  // _createPyodideModule is specified in the Makefile by the linker flag:
  // `-s EXPORT_NAME="'_createPyodideModule'"`
  await _createPyodideModule(Module);

  // There is some work to be done between the module being "ready" and postRun
  // being called.
  await moduleLoaded;

  // Disable futher loading of Emscripten file_packager stuff.
  Module.locateFile = (path: string) => {
    throw new Error("Didn't expect to load any more file_packager files!");
  };

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
(globalThis as any).loadPyodide = loadPyodide;
