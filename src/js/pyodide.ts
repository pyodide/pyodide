/**
 * The main bootstrap code for loading pyodide.
 */
import ErrorStackParser from "error-stack-parser";
import { loadScript, loadBinaryFile, initNodeModules } from "./compat";

import { createModule, setStandardStreams, setHomeDirectory } from "./module";

import type { PyodideInterface } from "./api.js";
import type { PyProxy, PyProxyDict } from "./pyproxy.gen";
export type { PyodideInterface };

export type {
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
  TypedArray,
  PyBuffer,
} from "./pyproxy.gen";

export type Py2JsResult = any;

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

function unpackPyodidePy(Module: any, pyodide_py_tar: Uint8Array) {
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
from sys import version_info
pyversion = f"python{version_info.major}.{version_info.minor}"
import shutil
shutil.unpack_archive("/pyodide_py.tar", f"/lib/{pyversion}/site-packages/")
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
function finalizeBootstrap(API: any, config: ConfigType) {
  // First make internal dict so that we can use runPythonInternal.
  // runPythonInternal uses a separate namespace, so we don't pollute the main
  // environment with variables from our setup.
  API.runPythonInternal_dict = API._pyodide._base.eval_code("{}") as PyProxy;
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

  let pyodide = API.makePublicAPI();
  importhook.register_js_module("pyodide_js", pyodide);

  // import pyodide_py. We want to ensure that as much stuff as possible is
  // already set up before importing pyodide_py to simplify development of
  // pyodide_py code (Otherwise it's very hard to keep track of which things
  // aren't set up yet.)
  API.pyodide_py = import_module("pyodide");
  API.pyodide_code = import_module("pyodide.code");
  API.pyodide_ffi = import_module("pyodide.ffi");
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
 *  If indexURL isn't provided, throw an error and catch it and then parse our
 *  file name out from the stack trace.
 *
 *  Question: But getting the URL from error stack trace is well... really
 *  hacky. Can't we use
 *  [`document.currentScript`](https://developer.mozilla.org/en-US/docs/Web/API/Document/currentScript)
 *  or
 *  [`import.meta.url`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/import.meta)
 *  instead?
 *
 *  Answer: `document.currentScript` works for the browser main thread.
 *  `import.meta` works for es6 modules. In a classic webworker, I think there
 *  is no approach that works. Also we would need some third approach for node
 *  when loading a commonjs module using `require`. On the other hand, this
 *  stack trace approach works for every case without any feature detection
 *  code.
 */
function calculateIndexURL(): string {
  let err: Error;
  try {
    throw new Error();
  } catch (e) {
    err = e as Error;
  }
  let fileName = ErrorStackParser.parse(err)[0].fileName!;
  const indexOfLastSlash = fileName.includes("/")
    ? fileName.lastIndexOf("/")
    : fileName.lastIndexOf("\\");
  if (indexOfLastSlash === -1) {
    throw new Error(
      "Could not extract indexURL path from pyodide module location"
    );
  }
  return fileName.slice(0, indexOfLastSlash);
}

/**
 * See documentation for loadPyodide.
 * @private
 */
export type ConfigType = {
  indexURL: string;
  lockFileURL: string;
  homedir: string;
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
export async function loadPyodide(
  options: {
    /**
     * The URL from which Pyodide will load the main Pyodide runtime and
     * packages. Defaults to the url that pyodide is loaded from with the file
     * name (pyodide.js or pyodide.mjs) removed. It is recommended that you
     * leave this undefined, providing an incorrect value can cause broken
     * behavior.
     */
    indexURL?: string;

    /**
     * The URL from which Pyodide will load the Pyodide "repodata.json" lock
     * file. Defaults to ``${indexURL}/repodata.json``. You can produce custom
     * lock files with :any:`micropip.freze`
     */
    lockFileURL?: string;

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
  } = {}
): Promise<PyodideInterface> {
  if (!options.indexURL) {
    options.indexURL = calculateIndexURL();
  }
  if (!options.indexURL.endsWith("/")) {
    options.indexURL += "/";
  }

  const default_config = {
    fullStdLib: true,
    jsglobals: globalThis,
    stdin: globalThis.prompt ? globalThis.prompt : undefined,
    homedir: "/home/pyodide",
    lockFileURL: options.indexURL! + "repodata.json",
  };
  const config = Object.assign(default_config, options) as ConfigType;
  await initNodeModules();
  const pyodide_py_tar_promise = loadBinaryFile(
    config.indexURL,
    "pyodide_py.tar"
  );

  const Module = createModule();
  const API: any = { config };
  Module.API = API;

  setStandardStreams(Module, config.stdin, config.stdout, config.stderr);
  setHomeDirectory(Module, config.homedir);

  const moduleLoaded = new Promise((r) => (Module.postRun = r));

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

  // Disable further loading of Emscripten file_packager stuff.
  Module.locateFile = (path: string) => {
    throw new Error("Didn't expect to load any more file_packager files!");
  };

  const pyodide_py_tar = await pyodide_py_tar_promise;
  unpackPyodidePy(Module, pyodide_py_tar);
  Module._pyodide_init();

  const pyodide = finalizeBootstrap(API, config);
  // API.runPython works starting here.
  if (!pyodide.version.includes("dev")) {
    // Currently only used in Node to download packages the first time they are
    // loaded. But in other cases it's harmless.
    API.setCdnUrl(`https://cdn.jsdelivr.net/pyodide/v${pyodide.version}/full/`);
  }
  await API.packageIndexReady;
  if (API.repodata_info.version !== pyodide.version) {
    throw new Error("Lock file version doesn't match Pyodide version");
  }
  if (config.fullStdLib) {
    await pyodide.loadPackage(["distutils"]);
  }
  pyodide.runPython("print('Python initialization complete')");
  return pyodide;
}
