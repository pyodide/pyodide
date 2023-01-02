import ErrorStackParser from "error-stack-parser";
declare var Module: any;
declare var Hiwire: any;
declare var API: any;
declare var Tests: any;

function ensureCaughtObjectIsError(e: any): Error {
  if (typeof e === "string") {
    // Sometimes emscripten throws a raw string...
    e = new Error(e);
  } else if (
    typeof e !== "object" ||
    e === null ||
    typeof e.stack !== "string" ||
    typeof e.message !== "string"
  ) {
    // We caught something really weird. Be brave!
    const typeTag = API.getTypeTag(e);
    let msg = `A value of type ${typeof e} with tag ${typeTag} was thrown as an error!`;
    try {
      msg += `\nString interpolation of the thrown value gives """${e}""".`;
    } catch (e) {
      msg += `\nString interpolation of the thrown value fails.`;
    }
    try {
      msg += `\nThe thrown value's toString method returns """${e.toString()}""".`;
    } catch (e) {
      msg += `\nThe thrown value's toString method fails.`;
    }
    e = new Error(msg);
  }
  // Post conditions:
  // 1. typeof e is object
  // 2. hiwire_is_error(e) returns true
  return e;
}

class CppException extends Error {
  ty: string;
  constructor(ty: string, msg: string | undefined, ptr: number) {
    if (!msg) {
      msg = `The exception is an object of type ${ty} at address ${ptr} which does not inherit from std::exception`;
    }
    super(msg);
    this.ty = ty;
  }
}
Object.defineProperty(CppException.prototype, "name", {
  get() {
    return `${this.constructor.name} ${this.ty}`;
  },
});

function convertCppException(e: number) {
  let [ty, msg]: [string, string] = Module.getExceptionMessage(e);
  return new CppException(ty, msg, e);
}
Tests.convertCppException = convertCppException;

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
  if (e && e.pyodide_fatal_error) {
    return;
  }
  if (fatal_error_occurred) {
    console.error("Recursive call to fatal_error. Inner error was:");
    console.error(e);
    return;
  }
  if (typeof e === "number") {
    // Hopefully a C++ exception?
    e = convertCppException(e);
  } else {
    e = ensureCaughtObjectIsError(e);
  }
  // Mark e so we know not to handle it later in EM_JS wrappers
  e.pyodide_fatal_error = true;
  fatal_error_occurred = true;
  console.error(
    "Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.",
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
    Module._dump_traceback();
    for (let key of Object.keys(API.public_api)) {
      if (key.startsWith("_") || key === "version") {
        continue;
      }
      Object.defineProperty(API.public_api, key, {
        enumerable: true,
        configurable: true,
        get: () => {
          throw new Error(
            "Pyodide already fatally failed and can no longer be used.",
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

class FatalPyodideError extends Error {}
Object.defineProperty(FatalPyodideError.prototype, "name", {
  value: FatalPyodideError.name,
});

let stderr_chars: number[] = [];
API.capture_stderr = function () {
  stderr_chars = [];
  const FS = Module.FS;
  FS.createDevice("/dev", "capture_stderr", null, (e: number) =>
    stderr_chars.push(e),
  );
  FS.closeStream(2 /* stderr */);
  // open takes the lowest available file descriptor. Since 0 and 1 are occupied by stdin and stdout it takes 2.
  FS.open("/dev/capture_stderr", 1 /* O_WRONLY */);
};

API.restore_stderr = function () {
  const FS = Module.FS;
  FS.closeStream(2 /* stderr */);
  FS.unlink("/dev/capture_stderr");
  // open takes the lowest available file descriptor. Since 0 and 1 are occupied by stdin and stdout it takes 2.
  FS.open("/dev/stderr", 1 /* O_WRONLY */);
  return new TextDecoder().decode(new Uint8Array(stderr_chars));
};

API.fatal_loading_error = function (...args: string[]) {
  let message = args.join(" ");
  if (Module._PyErr_Occurred()) {
    API.capture_stderr();
    // Prints traceback to stderr
    Module._PyErr_Print();
    const captured_stderr = API.restore_stderr();
    message += "\n" + captured_stderr;
  }
  throw new FatalPyodideError(message);
};

function isPyodideFrame(frame: ErrorStackParser.StackFrame): boolean {
  if (!frame) {
    return false;
  }
  const fileName = frame.fileName || "";
  if (fileName.includes("wasm-function")) {
    return true;
  }
  if (!fileName.includes("pyodide.asm.js")) {
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
  if (e && e.pyodide_fatal_error) {
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
  let stack: any;
  let weirdCatch;
  try {
    stack = ErrorStackParser.parse(e);
  } catch (_) {
    weirdCatch = true;
  }
  if (weirdCatch) {
    e = ensureCaughtObjectIsError(e);
  }
  if (!restored_error) {
    // Wrap the JavaScript error
    let eidx = Hiwire.new_value(e);
    let err = Module._JsProxy_create(eidx);
    Module._set_error(err);
    Module._Py_DecRef(err);
    Hiwire.decref(eidx);
  }
  if (weirdCatch) {
    // In this case we have no stack frames so we can quit
    return;
  }
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
 * In order to reduce the risk of large memory leaks, the :any:`PythonError`
 * contains no reference to the Python exception that caused it. You can find
 * the actual Python exception that caused this error as :any:`sys.last_value`.
 *
 * See :ref:`type-translations-errors` for more information.
 *
 * .. admonition:: Avoid leaking stack Frames
 *    :class: warning
 *
 *    If you make a :any:`PyProxy` of :any:`sys.last_value`, you should be
 *    especially careful to :any:`destroy() <PyProxy.destroy>` it when you are
 *    done. You may leak a large amount of memory including the local
 *    variables of all the stack frames in the traceback if you don't. The
 *    easiest way is to only handle the exception in Python.
 *
 * @hideconstructor
 */
export class PythonError extends Error {
  /**
   * The address of the error we are wrapping. We may later compare this
   * against sys.last_value.
   * WARNING: we don't own a reference to this pointer, dereferencing it
   * may be a use-after-free error!
   * @private
   */
  __error_address: number;
  /**
   * The Python type, e.g, :any:`RuntimeError` or :any:`KeyError`.
   */
  type: string;
  constructor(type: string, message: string, error_address: number) {
    const oldLimit = Error.stackTraceLimit;
    Error.stackTraceLimit = Infinity;
    super(message);
    Error.stackTraceLimit = oldLimit;
    this.type = type;
    this.__error_address = error_address;
  }
}
Object.defineProperty(PythonError.prototype, "name", {
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
        "occurred. Please report it to the Pyodide maintainers.",
    );
  }
}
Object.defineProperty(_PropagatePythonError.prototype, "name", {
  value: _PropagatePythonError.name,
});
Module._PropagatePythonError = _PropagatePythonError;
