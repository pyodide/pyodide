import { Module } from "./module.js";
import { loadPackage, loadedPackages } from "./load-pyodide.js";
import { isPyProxy, PyBuffer } from "./pyproxy.gen.js";
export { loadPackage, loadedPackages, isPyProxy };

/**
 * @typedef {import('./pyproxy.gen').Py2JsResult} Py2JsResult
 * @typedef {import('./pyproxy.gen').PyProxy} PyProxy
 * @typedef {import('./pyproxy.gen').TypedArray} TypedArray
 */

/**
 * An alias to the Python :py:mod:`pyodide` package.
 *
 * You can use this to call functions defined in the Pyodide Python package
 * from Javascript.
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
 * Runs a string of Python code from Javascript.
 *
 * The last part of the string may be an expression, in which case, its value
 * is returned.
 *
 * @param {string} code Python code to evaluate
 * @param {PyProxy} globals An optional Python dictionary to use as the globals.
 *        Defaults to :any:`pyodide.globals`. Uses the Python API
 *        :any:`pyodide.eval_code` to evaluate the code.
 * @returns {Py2JsResult} The result of the Python code translated to Javascript. See the
 *          documentation for :any:`pyodide.eval_code` for more info.
 */
export function runPython(code, globals = Module.globals) {
  let eval_code = Module.pyodide_py.eval_code;
  try {
    return eval_code(code, globals);
  } finally {
    eval_code.destroy();
  }
}
Module.runPython = runPython;

/**
 * @callback LogFn
 * @param {string} msg
 * @returns {void}
 * @private
 */

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
  let find_imports = Module.pyodide_py.find_imports;
  let imports;
  let pyimports;
  try {
    pyimports = find_imports(code);
    imports = pyimports.toJs();
  } finally {
    find_imports.destroy();
    pyimports && pyimports.destroy();
  }
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
    await loadPackage(
      Array.from(packages.keys()),
      messageCallback,
      errorCallback
    );
  }
}

/**
 * Access a Python object in the global namespace from Javascript.
 *
 * @deprecated This function will be removed in version 0.18.0. Use
 *    :any:`pyodide.globals.get('key') <pyodide.globals>` instead.
 *
 * @param {string} name Python variable name
 * @returns {Py2JsResult} The Python object translated to Javascript.
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
 * For example:
 *
 * .. code-block:: pyodide
 *
 *    let result = await pyodide.runPythonAsync(`
 *        from js import fetch
 *        response = await fetch("./packages.json")
 *        packages = await response.json()
 *        # If final statement is an expression, its value is returned to
 * Javascript len(packages.dependencies.object_keys())
 *    `);
 *    console.log(result); // 72
 *
 * @param {string} code Python code to evaluate
 * @returns {Py2JsResult} The result of the Python code translated to Javascript.
 * @async
 */
export async function runPythonAsync(code) {
  let eval_code_async = Module.pyodide_py.eval_code_async;
  let coroutine = eval_code_async(code, Module.globals);
  try {
    let result = await coroutine;
    return result;
  } finally {
    eval_code_async.destroy();
    coroutine.destroy();
  }
}
Module.runPythonAsync = runPythonAsync;

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
export function registerJsModule(name, module) {
  let register_js_module = Module.pyodide_py.register_js_module;
  try {
    register_js_module(name, module);
  } finally {
    register_js_module.destroy();
  }
}

/**
 * Tell Pyodide about Comlink.
 * Necessary to enable importing Comlink proxies into Python.
 */
export function registerComlink(Comlink) {
  Module._Comlink = Comlink;
}

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
export function unregisterJsModule(name) {
  let unregister_js_module = Module.pyodide_py.unregister_js_module;
  try {
    unregister_js_module(name);
  } finally {
    unregister_js_module.destroy();
  }
}

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
export function toPy(obj, depth = -1) {
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
    py_result = Module.__js2python_convert(obj_id, new Map(), depth);
    if (py_result === 0) {
      Module._pythonexc2js();
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
 * @param {TypedArray} interrupt_buffer
 */
function setInterruptBuffer(interrupt_buffer) {}
setInterruptBuffer = Module.setInterruptBuffer;
export { setInterruptBuffer };

export function makePublicAPI() {
  let namespace = {
    globals,
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
    toPy,
    registerComlink,
    PythonError,
    PyBuffer,
  };
  namespace._module = Module; // @private
  Module.public_api = namespace;
  return namespace;
}
