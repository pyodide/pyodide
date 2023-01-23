declare var Module: any;
declare var Hiwire: any;
declare var API: any;
import "./module.ts";

import { loadPackage, loadedPackages } from "./load-package";
import { isPyProxy, PyBuffer, PyProxy, TypedArray } from "./pyproxy.gen";
import { PythonError } from "./error_handling.gen";
import { loadBinaryFile } from "./compat";
import { version } from "./version";
export { loadPackage, loadedPackages, isPyProxy };
import "./error_handling.gen.js";
import { setStdin, setStdout, setStderr } from "./streams";

API.loadBinaryFile = loadBinaryFile;

/**
 * An alias to the Python :ref:`pyodide <python-api>` package.
 *
 * You can use this to call functions defined in the Pyodide Python package
 * from JavaScript.
 */
export let pyodide_py: PyProxy; // actually defined in loadPyodide (see pyodide.js)

/**
 *
 * An alias to the global Python namespace.
 *
 * For example, to access a variable called ``foo`` in the Python global
 * scope, use ``pyodide.globals.get("foo")``
 */
export let globals: PyProxy; // actually defined in loadPyodide (see pyodide.js)

/**
 * Runs code after python vm has been initialized but prior to any bootstrapping.
 */
API.rawRun = function rawRun(code: string): [number, string] {
  const code_ptr = Module.stringToNewUTF8(code);
  Module.API.capture_stderr();
  let errcode = Module._PyRun_SimpleString(code_ptr);
  Module._free(code_ptr);
  const captured_stderr = Module.API.restore_stderr().trim();
  return [errcode, captured_stderr];
};

/**
 * Just like `runPython` except uses a different globals dict and gets
 * `eval_code` from `_pyodide` so that it can work before `pyodide` is imported.
 * @private
 */
API.runPythonInternal = function (code: string): any {
  // API.runPythonInternal_dict is initialized in finalizeBootstrap
  return API._pyodide._base.eval_code(code, API.runPythonInternal_dict);
};

/**
 * Runs a string of Python code from JavaScript, using :any:`pyodide.code.eval_code`
 * to evaluate the code. If the last statement in the Python code is an
 * expression (and the code doesn't end with a semicolon), the value of the
 * expression is returned.
 *
 * @param code Python code to evaluate
 * @param options
 * @param options.globals An optional Python dictionary to use as the globals.
 *        Defaults to :any:`pyodide.globals`.
 * @returns The result of the Python code translated to JavaScript. See the
 *          documentation for :any:`pyodide.code.eval_code` for more info.
 */
export function runPython(
  code: string,
  options: { globals?: PyProxy } = {},
): any {
  if (!options.globals) {
    options.globals = API.globals;
  }
  return API.pyodide_code.eval_code(code, options.globals);
}
API.runPython = runPython;

let loadPackagesFromImportsPositionalCallbackDeprecationWarned = false;
/**
 * Inspect a Python code chunk and use :js:func:`pyodide.loadPackage` to install
 * any known packages that the code chunk imports. Uses the Python API
 * :func:`pyodide.code.find\_imports` to inspect the code.
 *
 * For example, given the following code as input
 *
 * .. code-block:: python
 *
 *    import numpy as np
 *    x = np.array([1, 2, 3])
 *
 * :js:func:`loadPackagesFromImports` will call
 * ``pyodide.loadPackage(['numpy'])``.
 *
 * @param code The code to inspect.
 * @param options Options passed to :any:`pyodide.loadPackage`.
 * @param options.messageCallback A callback, called with progress messages
 *    (optional)
 * @param options.errorCallback A callback, called with error/warning messages
 *    (optional)
 * @param options.checkIntegrity If true, check the integrity of the downloaded
 *    packages (default: true)
 * @param errorCallbackDeprecated @ignore
 * @async
 */
export async function loadPackagesFromImports(
  code: string,
  options: {
    messageCallback?: (message: string) => void;
    errorCallback?: (message: string) => void;
    checkIntegrity?: boolean;
  } = {
    checkIntegrity: true,
  },
  errorCallbackDeprecated?: (message: string) => void,
) {
  if (typeof options === "function") {
    if (!loadPackagesFromImportsPositionalCallbackDeprecationWarned) {
      console.warn(
        "Passing a messageCallback (resp. errorCallback) as the second (resp. third) argument to loadPackageFromImports " +
          "is deprecated and will be removed in v0.24. Instead use:\n" +
          "   { messageCallback : callbackFunc }",
      );
      loadPackagesFromImportsPositionalCallbackDeprecationWarned = true;
    }
    options = {
      messageCallback: options,
      errorCallback: errorCallbackDeprecated,
    };
  }

  let pyimports = API.pyodide_code.find_imports(code);
  let imports;
  try {
    imports = pyimports.toJs();
  } finally {
    pyimports.destroy();
  }
  if (imports.length === 0) {
    return;
  }

  let packageNames = API._import_name_to_package_name;
  let packages: Set<string> = new Set();
  for (let name of imports) {
    if (packageNames.has(name)) {
      packages.add(packageNames.get(name));
    }
  }
  if (packages.size) {
    await loadPackage(Array.from(packages), options);
  }
}

/**
 * Run a Python code string with top level await using
 * :any:`pyodide.code.eval_code_async` to evaluate the code. Returns a promise which
 * resolves when execution completes. If the last statement in the Python code
 * is an expression (and the code doesn't end with a semicolon), the returned
 * promise will resolve to the value of this expression.
 *
 * For example:
 *
 * .. code-block:: pyodide
 *
 *    let result = await pyodide.runPythonAsync(`
 *        from js import fetch
 *        response = await fetch("./repodata.json")
 *        packages = await response.json()
 *        # If final statement is an expression, its value is returned to JavaScript
 *        len(packages.packages.object_keys())
 *    `);
 *    console.log(result); // 79
 *
 * .. admonition:: Python imports
 *    :class: warning
 *
 *    Since pyodide 0.18.0, you must call :js:func:`loadPackagesFromImports` to
 *    import any python packages referenced via ``import`` statements in your
 *    code. This function will no longer do it for you.
 *
 * @param code Python code to evaluate
 * @param options
 * @param options.globals An optional Python dictionary to use as the globals.
 * Defaults to :any:`pyodide.globals`.
 * @returns The result of the Python code translated to JavaScript.
 * @async
 */
export async function runPythonAsync(
  code: string,
  options: { globals?: PyProxy } = {},
): Promise<any> {
  if (!options.globals) {
    options.globals = API.globals;
  }
  return await API.pyodide_code.eval_code_async(code, options.globals);
}
API.runPythonAsync = runPythonAsync;

/**
 * Registers the JavaScript object ``module`` as a JavaScript module named
 * ``name``. This module can then be imported from Python using the standard
 * Python import system. If another module by the same name has already been
 * imported, this won't have much effect unless you also delete the imported
 * module from :py:data:`sys.modules`. This calls the :any:`pyodide_py` API
 * :func:`~pyodide.ffi.register_js_module`.
 *
 * @param name Name of the JavaScript module to add
 * @param module JavaScript object backing the module
 */
export function registerJsModule(name: string, module: object) {
  API.pyodide_ffi.register_js_module(name, module);
}

/**
 * Tell Pyodide about Comlink.
 * Necessary to enable importing Comlink proxies into Python.
 */
export function registerComlink(Comlink: any) {
  API._Comlink = Comlink;
}

/**
 * Unregisters a JavaScript module with given name that has been previously
 * registered with :js:func:`pyodide.registerJsModule` or
 * :func:`~pyodide.ffi.register_js_module`. If a JavaScript module with that
 * name does not already exist, will throw an error. Note that if the module has
 * already been imported, this won't have much effect unless you also delete the
 * imported module from :py:data:`sys.modules`. This calls the :any:`pyodide_py`
 * API :func:`~pyodide.ffi.unregister_js_module`.
 *
 * @param name Name of the JavaScript module to remove
 */
export function unregisterJsModule(name: string) {
  API.pyodide_ffi.unregister_js_module(name);
}

/**
 * Convert a JavaScript object to a Python object as best as possible.
 *
 * This is similar to :any:`JsProxy.to_py` but for use from JavaScript. If the
 * object is immutable or a :any:`PyProxy`, it will be returned unchanged. If
 * the object cannot be converted into Python, it will be returned unchanged.
 *
 * See :ref:`type-translations-jsproxy-to-py` for more information.
 *
 * @param obj The object to convert.
 * @param options
 * @returns The object converted to Python.
 */
export function toPy(
  obj: any,
  {
    depth,
    defaultConverter,
  }: {
    /**
     *  Optional argument to limit the depth of the conversion.
     */
    depth: number;
    /**
     * Optional argument to convert objects with no default conversion. See the
     * documentation of :any:`JsProxy.to_py`.
     */
    defaultConverter?: (
      value: any,
      converter: (value: any) => any,
      cacheConversion: (input: any, output: any) => void,
    ) => any;
  } = { depth: -1 },
): any {
  // No point in converting these, it'd be dumb to proxy them so they'd just
  // get converted back by `js2python` at the end
  switch (typeof obj) {
    case "string":
    case "number":
    case "boolean":
    case "bigint":
    case "undefined":
      return obj;
  }
  if (!obj || API.isPyProxy(obj)) {
    return obj;
  }
  let obj_id = 0;
  let py_result = 0;
  let result = 0;
  try {
    obj_id = Hiwire.new_value(obj);
    try {
      py_result = Module.js2python_convert(obj_id, { depth, defaultConverter });
    } catch (e) {
      if (e instanceof Module._PropagatePythonError) {
        Module._pythonexc2js();
      }
      throw e;
    }
    if (Module._JsProxy_Check(py_result)) {
      // Oops, just created a JsProxy. Return the original object.
      return obj;
      // return Module.pyproxy_new(py_result);
    }
    result = Module._python2js(py_result);
    if (result === 0) {
      Module._pythonexc2js();
    }
  } finally {
    Hiwire.decref(obj_id);
    Module._Py_DecRef(py_result);
  }
  return Hiwire.pop_value(result);
}

/**
 * Imports a module and returns it.
 *
 * .. admonition:: Warning
 *    :class: warning
 *
 *    This function has a completely different behavior than the old removed pyimport function!
 *
 *    ``pyimport`` is roughly equivalent to:
 *
 *    .. code-block:: js
 *
 *      pyodide.runPython(`import ${pkgname}; ${pkgname}`);
 *
 *    except that the global namespace will not change.
 *
 *    Example:
 *
 *    .. code-block:: js
 *
 *      let sysmodule = pyodide.pyimport("sys");
 *      let recursionLimit = sysmodule.getrecursionlimit();
 *
 * @param mod_name The name of the module to import
 * @returns A PyProxy for the imported module
 */
export function pyimport(mod_name: string): PyProxy {
  return API.importlib.import_module(mod_name);
}

/**
 * Unpack an archive into a target directory.
 *
 * @param buffer The archive as an :js:class:`ArrayBuffer` or :js:class:`TypedArray`.
 * @param format The format of the archive. Should be one of the formats
 * recognized by :any:`shutil.unpack_archive`. By default the options are
 * ``'bztar'``, ``'gztar'``, ``'tar'``, ``'zip'``, and ``'wheel'``. Several
 * synonyms are accepted for each format, e.g., for ``'gztar'`` any of
 * ``'.gztar'``, ``'.tar.gz'``, ``'.tgz'``, ``'tar.gz'`` or ``'tgz'`` are
 * considered to be
 * synonyms.
 *
 * @param options
 * @param options.extractDir The directory to unpack the archive into. Defaults
 * to the working directory.
 */
export function unpackArchive(
  buffer: TypedArray | ArrayBuffer,
  format: string,
  options: {
    extractDir?: string;
  } = {},
) {
  if (
    !ArrayBuffer.isView(buffer) &&
    API.getTypeTag(buffer) !== "[object ArrayBuffer]"
  ) {
    throw new TypeError(
      `Expected argument 'buffer' to be an ArrayBuffer or an ArrayBuffer view`,
    );
  }
  API.typedArrayAsUint8Array(buffer);

  let extract_dir = options.extractDir;
  API.package_loader.unpack_buffer.callKwargs({
    buffer,
    format,
    extract_dir,
    installer: "pyodide.unpackArchive",
  });
}

type NativeFS = {
  syncfs: Function;
};

/**
 * Mounts FileSystemDirectoryHandle in to the target directory.
 *
 * @param path The absolute path in the Emscripten file system to mount the
 * native directory. If the directory does not exist, it will be created. If it
 * does exist, it must be empty.
 * @param fileSystemHandle A handle returned by navigator.storage.getDirectory()
 * or window.showDirectoryPicker().
 */
export async function mountNativeFS(
  path: string,
  fileSystemHandle: FileSystemDirectoryHandle,
  // TODO: support sync file system
  // sync: boolean = false
): Promise<NativeFS> {
  if (fileSystemHandle.constructor.name !== "FileSystemDirectoryHandle") {
    throw new TypeError(
      `Expected argument 'fileSystemHandle' to be a FileSystemDirectoryHandle`,
    );
  }

  if (Module.FS.findObject(path) == null) {
    Module.FS.mkdirTree(path);
  }

  Module.FS.mount(
    Module.FS.filesystems.NATIVEFS_ASYNC,
    { fileSystemHandle: fileSystemHandle },
    path,
  );

  // sync native ==> browser
  await new Promise((resolve, _) => Module.FS.syncfs(true, resolve));

  return {
    // sync browser ==> native
    syncfs: async () =>
      new Promise((resolve, _) => Module.FS.syncfs(false, resolve)),
  };
}

/**
 * @private
 */
API.saveState = () => API.pyodide_py._state.save_state();

/**
 * @private
 */
API.restoreState = (state: any) => API.pyodide_py._state.restore_state(state);

/**
 * Sets the interrupt buffer to be ``interrupt_buffer``. This is only useful
 * when Pyodide is used in a webworker. The buffer should be a
 * :js:class:`SharedArrayBuffer` shared with the main browser thread (or another
 * worker). In that case, signal ``signum`` may be sent by writing ``signum``
 * into the interrupt buffer. If ``signum`` does not satisfy 0 < ``signum`` < 65
 * it will be silently ignored.
 *
 * You can disable interrupts by calling ``setInterruptBuffer(undefined)``.
 *
 * If you wish to trigger a :any:`KeyboardInterrupt`, write ``SIGINT`` (a 2),
 * into the interrupt buffer.
 *
 * By default ``SIGINT`` raises a :any:`KeyboardInterrupt` and all other signals
 * are ignored. You can install custom signal handlers with the signal module.
 * Even signals that normally have special meaning and can't be overridden like
 * ``SIGKILL`` and ``SIGSEGV`` are ignored by default and can be used for any
 * purpose you like.
 */
export function setInterruptBuffer(interrupt_buffer: TypedArray) {
  Module.HEAP8[Module._Py_EMSCRIPTEN_SIGNAL_HANDLING] = !!interrupt_buffer;
  Module.Py_EmscriptenSignalBuffer = interrupt_buffer;
}

/**
 * Throws a :any:`KeyboardInterrupt` error if a :any:`KeyboardInterrupt` has
 * been requested via the interrupt buffer.
 *
 * This can be used to enable keyboard interrupts during execution of JavaScript
 * code, just as :any:`PyErr_CheckSignals` is used to enable keyboard interrupts
 * during execution of C code.
 */
export function checkInterrupt() {
  if (Module.__PyErr_CheckSignals()) {
    Module._pythonexc2js();
  }
}

export type PyodideInterface = {
  globals: typeof globals;
  FS: typeof FS;
  PATH: typeof PATH;
  ERRNO_CODES: typeof ERRNO_CODES;
  pyodide_py: typeof pyodide_py;
  version: typeof version;
  loadPackage: typeof loadPackage;
  loadPackagesFromImports: typeof loadPackagesFromImports;
  loadedPackages: typeof loadedPackages;
  isPyProxy: typeof isPyProxy;
  runPython: typeof runPython;
  runPythonAsync: typeof runPythonAsync;
  registerJsModule: typeof registerJsModule;
  unregisterJsModule: typeof unregisterJsModule;
  setInterruptBuffer: typeof setInterruptBuffer;
  checkInterrupt: typeof checkInterrupt;
  toPy: typeof toPy;
  pyimport: typeof pyimport;
  unpackArchive: typeof unpackArchive;
  mountNativeFS: typeof mountNativeFS;
  registerComlink: typeof registerComlink;
  PythonError: typeof PythonError;
  PyBuffer: typeof PyBuffer;
  setStdin: typeof setStdin;
  setStdout: typeof setStdout;
  setStderr: typeof setStderr;
};

/**
 * An alias to the `Emscripten File System API
 * <https://emscripten.org/docs/api_reference/Filesystem-API.html>`_.
 *
 * This provides a wide range of POSIX-`like` file/device operations, including
 * `mount
 * <https://emscripten.org/docs/api_reference/Filesystem-API.html#FS.mount>`_
 * which can be used to extend the in-memory filesystem with features like `persistence
 * <https://emscripten.org/docs/api_reference/Filesystem-API.html#persistent-data>`_.
 *
 * While all the file systems implementations are enabled, only the default
 * ``MEMFS`` is guaranteed to work in all runtime settings. The implementations
 * are available as members of ``FS.filesystems``:
 * ``IDBFS``, ``NODEFS``, ``PROXYFS``, ``WORKERFS``.
 */
export let FS: any;

/**
 * An alias to the `Emscripten Path API
 * <https://github.com/emscripten-core/emscripten/blob/main/src/library_path.js>`_.
 *
 * This provides a variety of operations for working with file system paths, such as
 * ``dirname``, ``normalize``, and ``splitPath``.
 */
export let PATH: any;

/**
 * A map from posix error names to error codes.
 */
export let ERRNO_CODES: { [code: string]: number };

/**
 * @private
 */
API.makePublicAPI = function (): PyodideInterface {
  FS = Module.FS;
  PATH = Module.PATH;
  ERRNO_CODES = Module.ERRNO_CODES;
  let namespace = {
    globals,
    FS,
    PATH,
    ERRNO_CODES,
    pyodide_py,
    version,
    loadPackage,
    loadPackagesFromImports,
    loadedPackages,
    isPyProxy,
    runPython,
    runPythonAsync,
    registerJsModule,
    unregisterJsModule,
    setInterruptBuffer,
    checkInterrupt,
    toPy,
    pyimport,
    unpackArchive,
    mountNativeFS,
    registerComlink,
    PythonError,
    PyBuffer,
    _module: Module,
    _api: API,
    setStdin,
    setStdout,
    setStderr,
  };

  API.public_api = namespace;
  return namespace;
};
