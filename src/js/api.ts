import { ffi } from "./ffi";
import { CanvasInterface, canvas } from "./canvas";

import { loadPackage, loadedPackages } from "./load-package";
import { type PyProxy, type PyDict } from "generated/pyproxy";
import { loadBinaryFile, nodeFSMod } from "./compat";
import { version } from "./version";
import { setStdin, setStdout, setStderr } from "./streams";
import { scheduleCallback } from "./scheduler";
import { TypedArray, PackageData, FSType } from "./types";
import { IN_NODE, detectEnvironment } from "./environments";
// @ts-ignore
import LiteralMap from "./common/literal-map";
import abortSignalAny from "./common/abortSignalAny";
import {
  makeGlobalsProxy,
  SnapshotConfig,
  syncUpSnapshotLoad1,
  syncUpSnapshotLoad2,
} from "./snapshot";
import { unpackArchiveMetadata } from "./constants";
import { syncLocalToRemote, syncRemoteToLocal } from "./nativefs";

// Exported for micropip
API.loadBinaryFile = loadBinaryFile;

/**
 * Runs code after python vm has been initialized but prior to any bootstrapping.
 */
API.rawRun = function rawRun(code: string): [number, string] {
  const code_ptr = Module.stringToNewUTF8(code);
  Module.API.capture_stderr();
  let errcode = _PyRun_SimpleString(code_ptr);
  _free(code_ptr);
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

API.setPyProxyToStringMethod = function (useRepr: boolean): void {
  Module.HEAP8[Module._compat_to_string_repr] = +useRepr;
};

API.setCompatNullToNone = function (compat: boolean): void {
  Module.HEAP8[Module._compat_null_to_none] = +compat;
}

/** @hidden */
export type NativeFS = {
  syncfs: () => Promise<void>;
};

/** @private */
API.saveState = () => API.pyodide_py._state.save_state();

/** @private */
API.restoreState = (state: any) => API.pyodide_py._state.restore_state(state);

// Used in webloop
/** @private */
API.scheduleCallback = scheduleCallback;

/** @private */
API.detectEnvironment = detectEnvironment;

// @ts-ignore
if (typeof AbortSignal !== "undefined" && AbortSignal.any) {
  /** @private */
  // @ts-ignore
  API.abortSignalAny = AbortSignal.any;
} else {
  /** @private */
  API.abortSignalAny = abortSignalAny;
}

API.LiteralMap = LiteralMap;

function ensureMountPathExists(path: string): void {
  Module.FS.mkdirTree(path);
  const { node } = Module.FS.lookupPath(path, {
    follow_mount: false,
  });

  if (FS.isMountpoint(node)) {
    throw new Error(`path '${path}' is already a file system mount point`);
  }
  if (!FS.isDir(node.mode)) {
    throw new Error(`path '${path}' points to a file not a directory`);
  }
  for (const _ in node.contents) {
    throw new Error(`directory '${path}' is not empty`);
  }
}

/**
 * Why is this a class rather than an object?
 * 1. It causes documentation items to be created for the entries so we can copy
 *    the definitions here rather than having to export things just so that they
 *    appear in the docs.
 * 2. We can use `@warnOnce` decorators (currently can only decorate class
 *    methods)
 * 3. It allows us to rebind names `PyBuffer` etc without causing
 *    `dts-bundle-generator` to generate broken type declarations.
 *
 * Between typescript, typedoc, dts-bundle-generator, rollup, and Emscripten,
 * there are a lot of constraints so we have to do some slightly weird things.
 * We convert it back into an object in makePublicAPI.
 * @private
 */
export class PyodideAPI {
  /** @hidden */
  static version = version;
  /** @hidden */
  static loadPackage = loadPackage;
  /** @hidden */
  static loadedPackages = loadedPackages;
  /** @hidden */
  static ffi = ffi;
  /** @hidden */
  static setStdin = setStdin;
  /** @hidden */
  static setStdout = setStdout;
  /** @hidden */
  static setStderr = setStderr;

  /**
   *
   * An alias to the global Python namespace.
   *
   * For example, to access a variable called ``foo`` in the Python global
   * scope, use ``pyodide.globals.get("foo")``
   */
  static globals = {} as PyProxy; // actually defined in loadPyodide (see pyodide.js)
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
  static FS = {} as FSType;
  /**
   * An alias to the `Emscripten Path API
   * <https://github.com/emscripten-core/emscripten/blob/main/src/library_path.js>`_.
   *
   * This provides a variety of operations for working with file system paths, such as
   * ``dirname``, ``normalize``, and ``splitPath``.
   */
  static PATH = {} as any;

  /**
   * APIs to set a canvas for rendering graphics.
   * @summaryLink :ref:`canvas <js-api-pyodide-canvas>`
   * @omitFromAutoModule
   */
  static canvas: CanvasInterface = canvas;

  /**
   * A map from posix error names to error codes.
   */
  static ERRNO_CODES = {} as { [code: string]: number };
  /**
   * An alias to the Python :ref:`pyodide <python-api>` package.
   *
   * You can use this to call functions defined in the Pyodide Python package
   * from JavaScript.
   */
  static pyodide_py = {} as PyProxy; // actually defined in loadPyodide (see pyodide.js)

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
   * @param options Options passed to :js:func:`pyodide.loadPackage`.
   * @param options.messageCallback A callback, called with progress messages
   *    (optional)
   * @param options.errorCallback A callback, called with error/warning messages
   *    (optional)
   * @param options.checkIntegrity If true, check the integrity of the downloaded
   *    packages (default: true)
   */
  static async loadPackagesFromImports(
    code: string,
    options: {
      messageCallback?: (message: string) => void;
      errorCallback?: (message: string) => void;
      checkIntegrity?: boolean;
    } = {
      checkIntegrity: true,
    },
  ): Promise<Array<PackageData>> {
    let pyimports = API.pyodide_code.find_imports(code);
    let imports;
    try {
      imports = pyimports.toJs();
    } finally {
      pyimports.destroy();
    }
    if (imports.length === 0) {
      return [];
    }

    let packageNames = API._import_name_to_package_name;
    let packages: Set<string> = new Set();
    for (let name of imports) {
      if (packageNames.has(name)) {
        packages.add(packageNames.get(name)!);
      }
    }
    if (packages.size) {
      return await loadPackage(Array.from(packages), options);
    }
    return [];
  }

  /**
   * Runs a string of Python code from JavaScript, using :py:func:`~pyodide.code.eval_code`
   * to evaluate the code. If the last statement in the Python code is an
   * expression (and the code doesn't end with a semicolon), the value of the
   * expression is returned.
   *
   * @param code The Python code to run
   * @param options
   * @param options.globals An optional Python dictionary to use as the globals.
   *        Defaults to :js:attr:`pyodide.globals`.
   * @param options.locals An optional Python dictionary to use as the locals.
   *        Defaults to the same as ``globals``.
   * @param options.filename An optional string to use as the file name.
   *        Defaults to ``"<exec>"``. If a custom file name is given, the
   *        traceback for any exception that is thrown will show source lines
   *        (unless the given file name starts with ``<`` and ends with ``>``).
   * @returns The result of the Python code translated to JavaScript. See the
   *          documentation for :py:func:`~pyodide.code.eval_code` for more info.
   * @example
   * async function main(){
   *   const pyodide = await loadPyodide();
   *   console.log(pyodide.runPython("1 + 2"));
   *   // 3
   *
   *   const globals = pyodide.toPy({ x: 3 });
   *   console.log(pyodide.runPython("x + 1", { globals }));
   *   // 4
   *
   *   const locals = pyodide.toPy({ arr: [1, 2, 3] });
   *   console.log(pyodide.runPython("sum(arr)", { locals }));
   *   // 6
   * }
   * main();
   */
  static runPython(
    code: string,
    options: { globals?: PyProxy; locals?: PyProxy; filename?: string } = {},
  ): any {
    if (!options.globals) {
      options.globals = API.globals;
    }
    return API.pyodide_code.eval_code.callKwargs(code, options);
  }

  /**
   * Run a Python code string with top level await using
   * :py:func:`~pyodide.code.eval_code_async` to evaluate the code. Returns a promise which
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
   *        response = await fetch("./pyodide-lock.json")
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
   * @param code The Python code to run
   * @param options
   * @param options.globals An optional Python dictionary to use as the globals.
   * Defaults to :js:attr:`pyodide.globals`.
   * @param options.locals An optional Python dictionary to use as the locals.
   *        Defaults to the same as ``globals``.
   * @param options.filename An optional string to use as the file name.
   *        Defaults to ``"<exec>"``. If a custom file name is given, the
   *        traceback for any exception that is thrown will show source lines
   *        (unless the given file name starts with ``<`` and ends with ``>``).
   * @returns The result of the Python code translated to JavaScript.
   */
  static async runPythonAsync(
    code: string,
    options: { globals?: PyProxy; locals?: PyProxy; filename?: string } = {},
  ): Promise<any> {
    if (!options.globals) {
      options.globals = API.globals;
    }
    return await API.pyodide_code.eval_code_async.callKwargs(code, options);
  }

  /**
   * Registers the JavaScript object ``module`` as a JavaScript module named
   * ``name``. This module can then be imported from Python using the standard
   * Python import system. If another module by the same name has already been
   * imported, this won't have much effect unless you also delete the imported
   * module from :py:data:`sys.modules`. This calls
   * :func:`~pyodide.ffi.register_js_module`.
   *
   * Any attributes of the JavaScript objects which are themselves objects will
   * be treated as submodules:
   * ```pyodide
   * pyodide.registerJsModule("mymodule", { submodule: { value: 7 } });
   * pyodide.runPython(`
   *     from mymodule.submodule import value
   *     assert value == 7
   * `);
   * ```
   * If you wish to prevent this, try the following instead:
   * ```pyodide
   * const sys = pyodide.pyimport("sys");
   * sys.modules.set("mymodule", { obj: { value: 7 } });
   * pyodide.runPython(`
   *     from mymodule import obj
   *     assert obj.value == 7
   *     # attempting to treat obj as a submodule raises ModuleNotFoundError:
   *     # "No module named 'mymodule.obj'; 'mymodule' is not a package"
   *     from mymodule.obj import value
   * `);
   * ```
   *
   * @param name Name of the JavaScript module to add
   * @param module JavaScript object backing the module
   */
  static registerJsModule(name: string, module: object) {
    API.pyodide_ffi.register_js_module(name, module);
  }
  /**
   * Unregisters a JavaScript module with given name that has been previously
   * registered with :js:func:`pyodide.registerJsModule` or
   * :func:`~pyodide.ffi.register_js_module`. If a JavaScript module with that
   * name does not already exist, will throw an error. Note that if the module has
   * already been imported, this won't have much effect unless you also delete the
   * imported module from :py:data:`sys.modules`. This calls
   * :func:`~pyodide.ffi.unregister_js_module`.
   *
   * @param name Name of the JavaScript module to remove
   */
  static unregisterJsModule(name: string) {
    API.pyodide_ffi.unregister_js_module(name);
  }

  /**
   * Convert a JavaScript object to a Python object as best as possible.
   *
   * This is similar to :py:meth:`~pyodide.ffi.JsProxy.to_py` but for use from
   * JavaScript. If the object is immutable or a :js:class:`~pyodide.ffi.PyProxy`,
   * it will be returned unchanged. If the object cannot be converted into Python,
   * it will be returned unchanged.
   *
   * See :ref:`type-translations-jsproxy-to-py` for more information.
   *
   * @param obj The object to convert.
   * @param options
   * @returns The object converted to Python.
   */
  static toPy(
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
       * documentation of :py:meth:`~pyodide.ffi.JsProxy.to_py`.
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
    let py_result = 0;
    let result = 0;
    try {
      py_result = Module.js2python_convert(obj, {
        depth,
        defaultConverter,
      });
    } catch (e) {
      if (e instanceof Module._PropagatePythonError) {
        _pythonexc2js();
      }
      throw e;
    }
    try {
      if (_JsProxy_Check(py_result)) {
        // Oops, just created a JsProxy. Return the original object.
        return obj;
        // return Module.pyproxy_new(py_result);
      }
      result = _python2js(py_result);
      if (result === null) {
        _pythonexc2js();
      }
    } finally {
      _Py_DecRef(py_result);
    }
    return result;
  }

  /**
   * Imports a module and returns it.
   *
   * If `name` has no dot in it, then `pyimport(name)` is approximately
   * equivalent to:
   * ```js
   * pyodide.runPython(`import ${name}; ${name}`)
   * ```
   * except that `name` is not introduced into the Python global namespace. If
   * the name has one or more dots in it, say it is of the form `path.name`
   * where `name` has no dots but path may have zero or more dots. Then it is
   * approximately the same as:
   * ```js
   * pyodide.runPython(`from ${path} import ${name}; ${name}`);
   * ```
   *
   * @param mod_name The name of the module to import
   *
   * @example
   * pyodide.pyimport("math.comb")(4, 2) // returns 4 choose 2 = 6
   */
  static pyimport(mod_name: string): any {
    return API.pyodide_base.pyimport_impl(mod_name);
  }

  /**
   * Unpack an archive into a target directory.
   *
   * @param buffer The archive as an :js:class:`ArrayBuffer` or :js:class:`TypedArray`.
   * @param format The format of the archive. Should be one of the formats
   * recognized by :py:func:`shutil.unpack_archive`. By default the options are
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
  static unpackArchive(
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
      metadata: unpackArchiveMetadata,
    });
  }

  /**
   * Mounts a :js:class:`FileSystemDirectoryHandle` into the target directory.
   * Currently it's only possible to acquire a
   * :js:class:`FileSystemDirectoryHandle` in Chrome.
   *
   * @param path The absolute path in the Emscripten file system to mount the
   * native directory. If the directory does not exist, it will be created. If
   * it does exist, it must be empty.
   * @param fileSystemHandle A handle returned by
   * :js:func:`navigator.storage.getDirectory() <getDirectory>` or
   * :js:func:`window.showDirectoryPicker() <showDirectoryPicker>`.
   */
  static async mountNativeFS(
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
    ensureMountPathExists(path);

    Module.FS.mount(
      Module.FS.filesystems.NATIVEFS_ASYNC,
      { fileSystemHandle },
      path,
    );

    // sync native ==> browser
    await syncRemoteToLocal(Module);

    return {
      // sync browser ==> native
      syncfs: async () => await syncLocalToRemote(Module),
    };
  }

  /**
   * Mounts a host directory into Pyodide file system. Only works in node.
   *
   * @param emscriptenPath The absolute path in the Emscripten file system to
   * mount the native directory. If the directory does not exist, it will be
   * created. If it does exist, it must be empty.
   * @param hostPath The host path to mount. It must be a directory that exists.
   */
  static mountNodeFS(emscriptenPath: string, hostPath: string): void {
    if (!IN_NODE) {
      throw new Error("mountNodeFS only works in Node");
    }
    ensureMountPathExists(emscriptenPath);
    let stat;
    try {
      stat = nodeFSMod.lstatSync(hostPath);
    } catch (e) {
      throw new Error(`hostPath '${hostPath}' does not exist`);
    }
    if (!stat.isDirectory()) {
      throw new Error(`hostPath '${hostPath}' is not a directory`);
    }

    Module.FS.mount(
      Module.FS.filesystems.NODEFS,
      { root: hostPath },
      emscriptenPath,
    );
  }

  /**
   * Tell Pyodide about Comlink.
   * Necessary to enable importing Comlink proxies into Python.
   */
  static registerComlink(Comlink: any) {
    API._Comlink = Comlink;
  }

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
   * If you wish to trigger a :py:exc:`KeyboardInterrupt`, write ``SIGINT`` (a 2)
   * into the interrupt buffer.
   *
   * By default ``SIGINT`` raises a :py:exc:`KeyboardInterrupt` and all other signals
   * are ignored. You can install custom signal handlers with the signal module.
   * Even signals that normally have special meaning and can't be overridden like
   * ``SIGKILL`` and ``SIGSEGV`` are ignored by default and can be used for any
   * purpose you like.
   */
  static setInterruptBuffer(interrupt_buffer: TypedArray) {
    Module.HEAP8[Module._Py_EMSCRIPTEN_SIGNAL_HANDLING] = +!!interrupt_buffer;
    Module.Py_EmscriptenSignalBuffer = interrupt_buffer;
  }

  /**
   * Throws a :py:exc:`KeyboardInterrupt` error if a :py:exc:`KeyboardInterrupt` has
   * been requested via the interrupt buffer.
   *
   * This can be used to enable keyboard interrupts during execution of JavaScript
   * code, just as :c:func:`PyErr_CheckSignals` is used to enable keyboard interrupts
   * during execution of C code.
   */
  static checkInterrupt() {
    if (_PyGILState_Check()) {
      // GIL held, so it's okay to call __PyErr_CheckSignals.
      if (__PyErr_CheckSignals()) {
        _pythonexc2js();
      }
      return;
    } else {
      // GIL not held. This is very likely because we're in a IO handler. If
      // buffer has a 2, throwing EINTR quits out from the IO handler and tells
      // the calling context to call `PyErr_CheckSignals`.
      const buf = Module.Py_EmscriptenSignalBuffer;
      if (buf && buf[0] === 2) {
        throw new Module.FS.ErrnoError(cDefs.EINTR);
      }
    }
  }

  /**
   * Turn on or off debug mode. In debug mode, some error messages are improved
   * at a performance cost.
   * @param debug If true, turn debug mode on. If false, turn debug mode off.
   * @returns The old value of the debug flag.
   */
  static setDebug(debug: boolean): boolean {
    const orig = !!API.debug_ffi;
    API.debug_ffi = debug;
    return orig;
  }

  /**
   *
   * @param param0
   * @returns
   */
  static makeMemorySnapshot({
    serializer,
  }: {
    serializer?: (obj: any) => any;
  } = {}): Uint8Array {
    if (!API.config._makeSnapshot) {
      throw new Error(
        "Can only use pyodide.makeMemorySnapshot if the _makeSnapshot option is passed to loadPyodide",
      );
    }
    return API.makeSnapshot(serializer);
  }

  /**
   * Returns the pyodide lockfile used to load the current Pyodide instance.
   * The format of the lockfile is defined in the `pyodide/pyodide-lock
   * <https://github.com/pyodide/pyodide-lock>`_ repository.
   */
  static get lockfile() {
    return API.lockfile;
  }

  /**
   * Returns the base URL of the lockfile, which is used to locate the packages
   * distributed with the lockfile.
   */
  static get lockfileBaseUrl() {
    return API.lockfileBaseUrl;
  }
}

/** @hidden */
export type PyodideInterface = typeof PyodideAPI;

/** @private */
function makePublicAPI(): PyodideInterface {
  // Create a copy of PyodideAPI that is an object instead of a class. This
  // displays a bit better in debuggers / consoles.
  let d = Object.getOwnPropertyDescriptors(PyodideAPI);
  // @ts-ignore
  delete d["prototype"];
  const pyodideAPI = Object.create({}, d);
  API.public_api = pyodideAPI;
  pyodideAPI.FS = Module.FS;
  pyodideAPI.PATH = Module.PATH;
  pyodideAPI.ERRNO_CODES = Module.ERRNO_CODES;
  pyodideAPI._module = Module;
  pyodideAPI._api = API;
  return pyodideAPI;
}

/**
 * A proxy around globals that falls back to checking for a builtin if has or
 * get fails to find a global with the given key. Note that this proxy is
 * transparent to js2python: it won't notice that this wrapper exists at all and
 * will translate this proxy to the globals dictionary.
 * @private
 */
function wrapPythonGlobals(globals_dict: PyDict, builtins_dict: PyDict) {
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

let bootstrapFinalized: () => void;
API.bootstrapFinalizedPromise = new Promise<void>(
  (r) => (bootstrapFinalized = r),
);

/**
 * This function is called after the emscripten module is finished initializing,
 * so eval_code is newly available.
 * It finishes the bootstrap so that once it is complete, it is possible to use
 * the core `pyodide` apis. (But package loading is not ready quite yet.)
 * @private
 */
API.finalizeBootstrap = function (
  snapshotConfig?: SnapshotConfig,
  snapshotDeserializer?: (obj: any) => any,
): PyodideInterface {
  if (snapshotConfig) {
    syncUpSnapshotLoad1();
  }
  let [err, captured_stderr] = API.rawRun("import _pyodide_core");
  if (err) {
    API.fatal_loading_error(
      "Failed to import _pyodide_core\n",
      captured_stderr,
    );
  }

  // First make internal dict so that we can use runPythonInternal.
  // runPythonInternal uses a separate namespace, so we don't pollute the main
  // environment with variables from our setup.
  API.runPythonInternal_dict = API._pyodide._base.eval_code("{}") as PyProxy;
  API.importlib = API.runPythonInternal("import importlib; importlib");
  let import_module = API.importlib.import_module;

  API.sys = import_module("sys");
  API.os = import_module("os");

  // Set up globals
  let globals = API.runPythonInternal(
    "import __main__; __main__.__dict__",
  ) as PyDict;
  let builtins = API.runPythonInternal(
    "import builtins; builtins.__dict__",
  ) as PyDict;
  API.globals = wrapPythonGlobals(globals, builtins);

  // Set up key Javascript modules.
  let importhook = API._pyodide._importhook;
  let pyodide = makePublicAPI();
  if (API.config._makeSnapshot) {
    API.config.jsglobals = makeGlobalsProxy(API.config.jsglobals);
  }
  const jsglobals = API.config.jsglobals;
  if (snapshotConfig) {
    syncUpSnapshotLoad2(jsglobals, snapshotConfig, snapshotDeserializer);
  } else {
    importhook.register_js_finder();
    importhook.register_js_module("js", jsglobals);
    importhook.register_js_module("pyodide_js", pyodide);
  }

  // import pyodide_py. We want to ensure that as much stuff as possible is
  // already set up before importing pyodide_py to simplify development of
  // pyodide_py code (Otherwise it's very hard to keep track of which things
  // aren't set up yet.)
  API.pyodide_py = import_module("pyodide");
  API.pyodide_code = import_module("pyodide.code");
  API.pyodide_ffi = import_module("pyodide.ffi");
  API.package_loader = import_module("pyodide._package_loader");
  API.pyodide_base = import_module("_pyodide._base");

  API.sitepackages = API.package_loader.SITE_PACKAGES.__str__();
  API.dsodir = API.package_loader.DSO_DIR.__str__();
  API.defaultLdLibraryPath = [API.dsodir, API.sitepackages];

  API.os.environ.__setitem__(
    "LD_LIBRARY_PATH",
    API.defaultLdLibraryPath.join(":"),
  );

  // copy some last constants onto public API.
  pyodide.pyodide_py = API.pyodide_py;
  pyodide.globals = API.globals;
  bootstrapFinalized!();
  return pyodide;
};
