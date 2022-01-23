import ErrorStackParser from "error-stack-parser";
import { Module } from "./module.js";

Module.handle_js_error = function (e) {
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
  if (e instanceof Module.PythonError) {
    // Try to restore the original Python exception.
    restored_error = _restore_sys_last_exception(e.__error_address);
  }
  if (!restored_error) {
    // Wrap the JavaScript error
    let eidx = Module.hiwire.new_value(e);
    let err = Module._JsProxy_create(eidx);
    Module._set_error(err);
    Module._Py_DecRef(err);
    Module.hiwire.decref(eidx);
  }
  // Add the Javascript stack frames to the Python traceback
  for (const stack of ErrorStackParser.parse(e)) {
    const funcnameAddr = Module.stringToNewUTF8(stack.functionName || "???");
    const fileNameAddr = Module.stringToNewUTF8(stack.fileName || "???.js");
    if (stack.fileName && stack.fileName.includes("pyodide.asm")) {
      break;
    }
    Module.__PyTraceback_Add(funcnameAddr, fileNameAddr, stack.lineNumber);
    Module._free(funcnameAddr);
    Module._free(fileNameAddr);
  }
};
class PythonError extends Error {
  constructor(message, error_address) {
    super(message);
    this.name = this.constructor.name;
    // The address of the error we are wrapping. We may later compare this
    // against sys.last_value.
    // WARNING: we don't own a reference to this pointer, dereferencing it
    // may be a use-after-free error!
    this.__error_address = error_address;
  }
}
Module.PythonError = PythonError;
// A special marker. If we call a CPython API from an EM_JS function and the
// CPython API sets an error, we might want to return an error status back to
// C keeping the current Python error flag. This signals to the EM_JS wrappers
// that the Python error flag is set and to leave it alone and return the
// appropriate error value (either NULL or -1).
class _PropagatePythonError extends Error {
  constructor() {
    Module.fail_test = true;
    super(
      "If you are seeing this message, an internal Pyodide error has " +
        "occurred. Please report it to the Pyodide maintainers."
    );
  }
}
Module._PropagatePythonError = _PropagatePythonError;
