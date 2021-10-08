import { Module } from "./module.js";
import { loadPackage, loadedPackages } from "./load-pyodide.js";
import { isPyProxy, PyBuffer } from "./pyproxy.gen.js";
export { loadPackage, loadedPackages, isPyProxy };

/**
 * @typedef {import('./pyproxy.gen').Py2JsResult} Py2JsResult
 * @typedef {import('./pyproxy.gen').PyProxy} PyProxy
 * @typedef {import('./pyproxy.gen').TypedArray} TypedArray
 * @typedef {import('emscripten')} Emscripten
 */

/**
 * An alias to the Python :py:mod:`pyodide` package.
 *
 * You can use this to call functions defined in the Pyodide Python package
 * from JavaScript.
 *
 * @type {PyProxy}
 */
let pyodide_py = {}; // actually defined in runPythonSimple in loadPyodide (see pyodide.js)

/**
 *
 * An alias to the global Python namespace.
 *
 * For example, to access a variable called ``foo`` in the Python global
 * scope, use ``pyodide.globals.get("foo")``
 *
 * @type {PyProxy}
 */
let globals = {}; // actually defined in runPythonSimple in loadPyodide (see pyodide.js)

/**
 * A JavaScript error caused by a Python exception.
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
export class PythonError {
  // actually defined in error_handling.c. TODO: would be good to move this
  // documentation and the definition of PythonError to error_handling.js
  constructor() {
    /**
     * The Python traceback.
     * @type {string}
     */
    this.message;
  }
}

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
export let version = ""; // actually defined in runPythonSimple in loadPyodide (see pyodide.js)

/**
 * Runs a string of Python code from JavaScript.
 *
 * The last part of the string may be an expression, in which case, its value
 * is returned.
 *
 * @param {string} code Python code to evaluate
 * @param {PyProxy} globals An optional Python dictionary to use as the globals.
 *        Defaults to :any:`pyodide.globals`. Uses the Python API
 *        :any:`pyodide.eval_code` to evaluate the code.
 * @returns {Py2JsResult} The result of the Python code translated to JavaScript. See the
 *          documentation for :any:`pyodide.eval_code` for more info.
 */
export function runPython(code, globals = Module.globals) {
  return Module.pyodide_py.eval_code(code, globals);
}
Module.runPython = runPython;

/**
 * @callback LogFn
 * @param {string} msg
 * @returns {void}
 * @private
 */

/**
 * Inspect a Python code chunk and use :js:func:`pyodide.loadPackage` to install
 * any known packages that the code chunk imports. Uses the Python API
 * :func:`pyodide.find\_imports` to inspect the code.
 *
 * For example, given the following code as input
 *
 * .. code-block:: python
 *
 *    import numpy as np x = np.array([1, 2, 3])
 *
 * :js:func:`loadPackagesFromImports` will call
 * ``pyodide.loadPackage(['numpy'])``.
 *
 * @param {string} code The code to inspect.
 * @param {LogFn=} messageCallback The ``messageCallback`` argument of
 * :any:`pyodide.loadPackage` (optional).
 * @param {LogFn=} errorCallback The ``errorCallback`` argument of
 * :any:`pyodide.loadPackage` (optional).
 * @async
 */
export async function loadPackagesFromImports(
  code,
  messageCallback,
  errorCallback
) {
  let pyimports = Module.pyodide_py.find_imports(code);
  let imports;
  try {
    imports = pyimports.toJs();
  } finally {
    pyimports.destroy();
  }
  if (imports.length === 0) {
    return;
  }

  let packageNames = Module._import_name_to_package_name;
  let packages = new Set();
  for (let name of imports) {
    if (packageNames.has(name)) {
      packages.add(packageNames.get(name));
    }
  }
  if (packages.size) {
    await loadPackage(Array.from(packages), messageCallback, errorCallback);
  }
}

/**
 * Access a Python object in the global namespace from JavaScript.
 *
 * @deprecated This function will be removed in version 0.18.0. Use
 *    :any:`pyodide.globals.get('key') <pyodide.globals>` instead.
 *
 * @param {string} name Python variable name
 * @returns {Py2JsResult} The Python object translated to JavaScript.
 */
export function pyimport(name) {
  console.warn(
    "Access to the Python global namespace via pyodide.pyimport is deprecated and " +
      "will be removed in version 0.18.0. Use pyodide.globals.get('key') instead."
  );
  return Module.globals.get(name);
}
/**
 * Runs Python code using `PyCF_ALLOW_TOP_LEVEL_AWAIT
 * <https://docs.python.org/3/library/ast.html?highlight=pycf_allow_top_level_await#ast.PyCF_ALLOW_TOP_LEVEL_AWAIT>`_.
 *
 * .. admonition:: Python imports
 *    :class: warning
 *
 *    Since pyodide 0.18.0, you must call :js:func:`loadPackagesFromImports` to
 *    import any python packages referenced via `import` statements in your code.
 *    This function will no longer do it for you.
 *
 * For example:
 *
 * .. code-block:: pyodide
 *
 *    let result = await pyodide.runPythonAsync(`
 *        from js import fetch
 *        response = await fetch("./packages.json")
 *        packages = await response.json()
 *        # If final statement is an expression, its value is returned to JavaScript
 *        len(packages.packages.object_keys())
 *    `);
 *    console.log(result); // 79
 *
 * @param {string} code Python code to evaluate
 * @returns {Py2JsResult} The result of the Python code translated to JavaScript.
 * @async
 */
export async function runPythonAsync(code) {
  let coroutine = Module.pyodide_py.eval_code_async(code, Module.globals);
  try {
    return await coroutine;
  } finally {
    coroutine.destroy();
  }
}
Module.runPythonAsync = runPythonAsync;

/**
 * Registers the JavaScript object ``module`` as a JavaScript module named
 * ``name``. This module can then be imported from Python using the standard
 * Python import system. If another module by the same name has already been
 * imported, this won't have much effect unless you also delete the imported
 * module from ``sys.modules``. This calls the ``pyodide_py`` API
 * :func:`pyodide.register_js_module`.
 *
 * @param {string} name Name of the JavaScript module to add
 * @param {object} module JavaScript object backing the module
 */
export function registerJsModule(name, module) {
  Module.pyodide_py.register_js_module(name, module);
}

/**
 * Tell Pyodide about Comlink.
 * Necessary to enable importing Comlink proxies into Python.
 */
export function registerComlink(Comlink) {
  Module._Comlink = Comlink;
}

/**
 * Unregisters a JavaScript module with given name that has been previously
 * registered with :js:func:`pyodide.registerJsModule` or
 * :func:`pyodide.register_js_module`. If a JavaScript module with that name
 * does not already exist, will throw an error. Note that if the module has
 * already been imported, this won't have much effect unless you also delete
 * the imported module from ``sys.modules``. This calls the ``pyodide_py`` API
 * :func:`pyodide.unregister_js_module`.
 *
 * @param {string} name Name of the JavaScript module to remove
 */
export function unregisterJsModule(name) {
  Module.pyodide_py.unregister_js_module(name);
}

/**
 * Convert the JavaScript object to a Python object as best as possible.
 *
 * This is similar to :any:`JsProxy.to_py` but for use from JavaScript. If the
 * object is immutable or a :any:`PyProxy`, it will be returned unchanged. If
 * the object cannot be converted into Python, it will be returned unchanged.
 *
 * See :ref:`type-translations-jsproxy-to-py` for more information.
 *
 * @param {*} obj
 * @param {object} options
 * @param {number} options.depth Optional argument to limit the depth of the
 * conversion.
 * @returns {PyProxy} The object converted to Python.
 */
export function toPy(obj, { depth = -1 } = {}) {
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
  if (!obj || Module.isPyProxy(obj)) {
    return obj;
  }
  let obj_id = 0;
  let py_result = 0;
  let result = 0;
  try {
    obj_id = Module.hiwire.new_value(obj);
    try {
      py_result = Module.js2python_convert(obj_id, new Map(), depth);
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
    Module.hiwire.decref(obj_id);
    Module._Py_DecRef(py_result);
  }
  return Module.hiwire.pop_value(result);
}

/**
 * @private
 */
Module.saveState = () => Module.pyodide_py._state.save_state();

/**
 * @private
 */
Module.restoreState = (state) => Module.pyodide_py._state.restore_state(state);

/**
 * Sets the interrupt buffer to be `interrupt_buffer`. This is only useful when
 * Pyodide is used in a webworker. The buffer should be a `SharedArrayBuffer`
 * shared with the main browser thread (or another worker). To request an
 * interrupt, a `2` should be written into `interrupt_buffer` (2 is the posix
 * constant for SIGINT).
 *
 * @param {TypedArray} interrupt_buffer
 */
export function setInterruptBuffer(interrupt_buffer) {
  Module.interrupt_buffer = interrupt_buffer;
  Module._set_pyodide_callback(!!interrupt_buffer);
}

/**
 * Throws a KeyboardInterrupt error if a KeyboardInterrupt has been requested
 * via the interrupt buffer.
 *
 * This can be used to enable keyboard interrupts during execution of JavaScript
 * code, just as `PyErr_CheckSignals` is used to enable keyboard interrupts
 * during execution of C code.
 */
export function checkInterrupt() {
  if (Module.interrupt_buffer[0] === 2) {
    Module.interrupt_buffer[0] = 0;
    Module._PyErr_SetInterrupt();
    Module.runPython("");
  }
}

export function makePublicAPI() {
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
   * While all of the file systems implementations are enabled, only the default
   * ``MEMFS`` is guaranteed to work in all runtime settings. The implementations
   * are available as members of ``FS.filesystems``:
   * ``IDBFS``, ``NODEFS``, ``PROXYFS``, ``WORKERFS``.
   *
   * @type {FS} The Emscripten File System API.
   */
  const FS = Module.FS;
  let namespace = {
    globals,
    FS,
    pyodide_py,
    version,
    loadPackage,
    loadPackagesFromImports,
    loadedPackages,
    isPyProxy,
    pyimport,
    runPython,
    runPythonAsync,
    registerJsModule,
    unregisterJsModule,
    setInterruptBuffer,
    checkInterrupt,
    toPy,
    registerComlink,
    PythonError,
    PyBuffer,
  };

  namespace._module = Module; // @private
  Module.public_api = namespace;
  return namespace;
}
