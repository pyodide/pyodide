import ErrorStackParser from "error-stack-parser";
import { Module, API } from "./module.js";

function isPyodideFrame(frame: ErrorStackParser.StackFrame): boolean {
  const fileName = frame.fileName || "";
  if (fileName.includes("pyodide.asm")) {
    return true;
  }
  if (fileName.includes("wasm-function")) {
    return true;
  }
  if (!fileName.includes("pyodide.js")) {
    return false;
  }
  let funcName = frame.functionName || "";
  if (funcName.startsWith("Object.")) {
    funcName = funcName.slice("Object.".length);
  }
  if (funcName in API.public_api && funcName !== "PythonError") {
    frame.functionName = funcName;
    return false;
  }
  return true;
}

function isErrorStart(frame: ErrorStackParser.StackFrame): boolean {
  if (!isPyodideFrame(frame)) {
    return false;
  }
  const funcName = frame.functionName;
  return funcName === "PythonError" || funcName === "new_error";
}

Module.handle_js_error = function (e: any) {
  if (e.pyodide_fatal_error) {
    throw e;
  }
  if (e instanceof Module._PropagatePythonError) {
    // Python error indicator is already set in this case. If this branch is
    // not taken, Python error indicator should be unset, and we have to set
    // it. In this case we don't want to tamper with the traceback.
    return;
  }
  let restored_error = false;
  if (e instanceof API.PythonError) {
    // Try to restore the original Python exception.
    restored_error = Module._restore_sys_last_exception(e.__error_address);
  }
  if (!restored_error) {
    // Wrap the JavaScript error
    let eidx = Module.hiwire.new_value(e);
    let err = Module._JsProxy_create(eidx);
    Module._set_error(err);
    Module._Py_DecRef(err);
    Module.hiwire.decref(eidx);
  }
  let stack = ErrorStackParser.parse(e);
  if (isErrorStart(stack[0])) {
    while (isPyodideFrame(stack[0])) {
      stack.shift();
    }
  }
  // Add the Javascript stack frames to the Python traceback
  for (const frame of stack) {
    if (isPyodideFrame(frame)) {
      break;
    }
    const funcnameAddr = Module.stringToNewUTF8(frame.functionName || "???");
    const fileNameAddr = Module.stringToNewUTF8(frame.fileName || "???.js");
    Module.__PyTraceback_Add(funcnameAddr, fileNameAddr, frame.lineNumber);
    Module._free(funcnameAddr);
    Module._free(fileNameAddr);
  }
};

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
 */
export class PythonError extends Error {
  /**
   * The Python traceback.
   */
  message: string;
  /**  The address of the error we are wrapping. We may later compare this
   * against sys.last_value.
   * WARNING: we don't own a reference to this pointer, dereferencing it
   * may be a use-after-free error!
   * @private
   */
  __error_address: number;

  constructor(message: string, error_address: number) {
    const oldLimit = Error.stackTraceLimit;
    Error.stackTraceLimit = Infinity;
    super(message);
    Error.stackTraceLimit = oldLimit;
    this.name = this.constructor.name;
    this.__error_address = error_address;
  }
}
API.PythonError = PythonError;
// A special marker. If we call a CPython API from an EM_JS function and the
// CPython API sets an error, we might want to return an error status back to
// C keeping the current Python error flag. This signals to the EM_JS wrappers
// that the Python error flag is set and to leave it alone and return the
// appropriate error value (either NULL or -1).
class _PropagatePythonError extends Error {
  constructor() {
    API.fail_test = true;
    super(
      "If you are seeing this message, an internal Pyodide error has " +
        "occurred. Please report it to the Pyodide maintainers."
    );
  }
}
Module._PropagatePythonError = _PropagatePythonError;
