import ErrorStackParser from "error-stack-parser";
import { Module, API, Hiwire } from "./module.js";

/**
 * Dump the Python traceback to the browser console.
 *
 * @private
 */
 API.dump_traceback = function () {
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
API.fatal_error = function (e: any) {
  if (e.pyodide_fatal_error) {
    return;
  }
  if (fatal_error_occurred) {
    console.error("Recursive call to fatal_error. Inner error was:");
    console.error(e);
    return;
  }
  if(typeof e === "number"){
    // A C++ exception. Have to do some conversion work.
    e = convertCppException(e);
  }
  // Mark e so we know not to handle it later in EM_JS wrappers
  e.pyodide_fatal_error = true;
  fatal_error_occurred = true;
  console.error(
    "Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers."
  );
  console.error("The cause of the fatal error was:");
  if (API.inTestHoist) {
    // Test hoist won't print the error object in a useful way so convert it to
    // string.
    console.error(e.toString());
    console.error(e.stack);
  } else {
    console.error(e);
  }
  try {
    API.dump_traceback();
    for (let key of Object.keys(API.public_api)) {
      if (key.startsWith("_") || key === "version") {
        continue;
      }
      Object.defineProperty(API.public_api, key, {
        enumerable: true,
        configurable: true,
        get: () => {
          throw new Error(
            "Pyodide already fatally failed and can no longer be used."
          );
        },
      });
    }
    if (API.on_fatal) {
      API.on_fatal(e);
    }
  } catch (err2) {
    console.error("Another error occurred while handling the fatal error:");
    console.error(err2);
  }
  throw e;
};

class CppException extends Error {}
Object.defineProperty(CppException.prototype, 'name', {
  value: CppException.name,
});

function convertCppException(ptr : number): CppException {
  const catchInfo = new Module.CatchInfo(ptr)
  const msgPtr = catchInfo.get_adjusted_ptr();
  const msg = Module.UTF8ToString(msgPtr);
  return new CppException(msg)
}


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
    let eidx = Hiwire.new_value(e);
    let err = Module._JsProxy_create(eidx);
    Module._set_error(err);
    Module._Py_DecRef(err);
    Hiwire.decref(eidx);
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
    this.__error_address = error_address;
  }
}
Object.defineProperty(PythonError.prototype, 'name', {
  value: PythonError.name,
});
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
Object.defineProperty(_PropagatePythonError.prototype, 'name', {
  value: _PropagatePythonError.name,
});
Module._PropagatePythonError = _PropagatePythonError;
