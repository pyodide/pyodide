// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "error_handling.h"
#include "jslib.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include <emscripten.h>
#include <stdio.h>

static PyObject* tbmod = NULL;
static PyObject* _pyodide_importhook = NULL;

_Py_IDENTIFIER(__qualname__);
_Py_IDENTIFIER(add_note_to_module_not_found_error);

void
_Py_DumpTraceback(int fd, PyThreadState* tstate);

EMSCRIPTEN_KEEPALIVE void
dump_traceback()
{
  _Py_DumpTraceback(fileno(stdout), PyGILState_GetThisThreadState());
}

EM_JS(void, console_error, (char* msg), {
  let jsmsg = UTF8ToString(msg);
  console.error(jsmsg);
});

// Right now this is dead code (probably), please don't remove it.
// Intended for debugging purposes.
// clang-format off
EM_JS(void, console_error_obj, (JsVal obj), {
  console.error(obj);
});
// clang-format on

/**
 * Set Python error indicator from JavaScript.
 *
 * In JavaScript, we can't access the type without relying on the ABI of
 * PyObject. Py_TYPE is part of the Python restricted API which means that there
 * are fairly strong guarantees about the ABI stability, but even so writing
 * HEAP32[err/4 + 1] is a bit opaque.
 */
EMSCRIPTEN_KEEPALIVE void
set_error(PyObject* err)
{
  PyErr_SetObject((PyObject*)Py_TYPE(err), err);
}

/**
 * Make a new PythonError.
 *
 * msg - the Python traceback + error message
 * err - The error object
 */
// clang-format off
EM_JS(
JsVal,
new_error,
(const char* type, JsVal msg, PyObject* err),
{
  return new API.PythonError(UTF8ToString(type), msg, err);
});
// clang-format on

/**
 * Restore sys.last_exception as the current exception if sys.last_exc matches
 * the argument `exc`. Used for reentrant errors.
 * Returns true if it restored the error indicator, false otherwise.
 *
 * If we throw a JavaScript PythonError and it bubbles out to the enclosing
 * Python scope (i.e., doesn't get caught in JavaScript) then we want to restore
 * the original Python exception. This produces much better stack traces in case
 * of reentrant calls and prevents issues like a KeyboardInterrupt being wrapped
 * into a PythonError being wrapped into a JsException and being caught.
 *
 * We don't do the same thing for JavaScript messages that pass through Python
 * because the Python exceptions have good JavaScript stack traces but
 * JavaScript errors have no Python stack info. Also, JavaScript has much weaker
 * support for catching errors by type.
 */
EMSCRIPTEN_KEEPALIVE bool
restore_sys_last_exception(void* exc)
{
  if (exc == NULL) {
    return false;
  }
  // PySys_GetObject returns a borrowed reference and will return NULL without
  // setting an exception if it fails.
  PyObject* last_exc = PySys_GetObject("last_exc");
  if (last_exc != exc) {
    return false;
  }
  // PyErr_SetRaisedException steals a reference to its argument and
  // PySys_GetObject returns a borrow so need to incref last_xxc first.
  Py_INCREF(last_exc);
  PyErr_SetRaisedException(last_exc);
  return true;
}

// clang-format off
EM_JS(void, fail_test, (), {
  API.fail_test = true;
})

EM_JS(void, capture_stderr, (void), {
  API.capture_stderr();
});

EM_JS(JsVal, restore_stderr, (void), {
  return API.restore_stderr();
});
// clang-format on

/**
 * Wrap the exception in a JavaScript PythonError object.
 *
 * The return value of this function is always a JavaScript error object. It
 * never returns null.
 *
 * We are cautious about leaking the Python stack frame, so we don't increment
 * the reference count on the exception object, we just store a pointer to it.
 * Later we can check if this pointer is equal to sys.last_exc and if so restore
 * the exception (see restore_sys_last_exception).
 *
 * WARNING: dereferencing the error pointer stored on the PythonError is a
 * use-after-free bug.
 */
EMSCRIPTEN_KEEPALIVE JsVal
wrap_exception()
{
  bool success = false;
  PyObject* exc = NULL;
  PyObject* typestr = NULL;

  exc = PyErr_GetRaisedException();

  if (PyErr_GivenExceptionMatches(exc, PyExc_ModuleNotFoundError)) {
    PyObject* res = _PyObject_CallMethodIdOneArg(
      _pyodide_importhook, &PyId_add_note_to_module_not_found_error, exc);
    FAIL_IF_NULL(res);
    Py_CLEAR(res);
  }

  capture_stderr();
  PyErr_SetRaisedException(Py_NewRef(exc));
  // print standard traceback to standard error, clear the error flag, and set
  // sys.last_exc, sys.last_type, etc
  //
  // Calls sys.excepthook. We set the excepthook to call
  // traceback.print_exception, see `set_excepthook()` in
  // `_pyodide/__init__.py`.
  //
  // If the error is a SystemExit and the PyConfig.inspect flag is not set,
  // PyErr_Print() will call exit(). We don't want this generally, so we will
  // generally set the `inspect` flag. The exception is in the CLI runner.
  //
  // In the CLI runner, if we call back into JS then back into Python and the
  // inner Python raises SystemExit, we won't actually unwind the Python frames
  // in the outer Python. Hypothetically this could cause trouble and we should
  // fix it, but it's probably not worth the effort.
  PyErr_Print();
  JsVal formatted_exception = restore_stderr();

  typestr = _PyObject_GetAttrId((PyObject*)Py_TYPE(exc), &PyId___qualname__);
  FAIL_IF_NULL(typestr);
  const char* typestr_utf8 = PyUnicode_AsUTF8(typestr);
  FAIL_IF_NULL(typestr_utf8);

  JsVal jserror = new_error(typestr_utf8, formatted_exception, exc);
  FAIL_IF_JS_NULL(jserror);

  success = true;
finally:
  if (!success) {
    fail_test();
    PySys_WriteStderr(
      "Pyodide: Internal error occurred while formatting traceback:\n");
    PyErr_Print();
    if (exc != NULL) {
      PySys_WriteStderr("\nOriginal exception was:\n");
      PyErr_DisplayException(exc);
    }
    Js_static_string(msg, "Error occurred while formatting traceback");
    jserror = new_error("PyodideInternalError", JsvString_FromId(&msg), 0);
  }
  Py_CLEAR(exc);
  Py_CLEAR(typestr);
  return jserror;
}

#ifdef DEBUG_F
EM_JS(void, log_python_error, (JsVal jserror), {
  // If a js error occurs in here, it's a weird edge case. This will probably
  // never happen, but for maximum paranoia let's double check.
  try {
    let msg = jserror.message;
    console.warn("Python exception:\n" + msg + "\n");
  } catch (e) {
    API.fatal_error(e);
  }
});
#endif

/**
 * Convert the current Python error to a javascript error and throw it.
 */
EMSCRIPTEN_KEEPALIVE void _Py_NO_RETURN
pythonexc2js()
{
  JsVal jserror = wrap_exception();
#ifdef DEBUG_F
  log_python_error(jserror);
#endif
  JsvError_Throw(jserror);
}

PyObject*
trigger_fatal_error(PyObject* mod, PyObject* _args)
{
  EM_ASM(throw new Error("intentionally triggered fatal error!"););
  Py_UNREACHABLE();
}

// clang-format off
EM_JS(void, raw_call_js, (JsVal func), {
  func();
});
// clang-format on

/**
 * This is for testing fatal errors in test_pyodide
 */
PyObject*
raw_call(PyObject* mod, PyObject* jsproxy)
{
  raw_call_js(JsProxy_Val(jsproxy));
  Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
  {
    "trigger_fatal_error",
    trigger_fatal_error,
    METH_NOARGS,
  },
  { "raw_call", raw_call, METH_O },
  { NULL } /* Sentinel */
};

PyObject* internal_error;
PyObject* conversion_error;

int
error_handling_init(PyObject* core_module)
{
  bool success = false;
  PyObject* _pyodide_core_docs = NULL;

  _pyodide_core_docs = PyImport_ImportModule("_pyodide._core_docs");
  FAIL_IF_NULL(_pyodide_core_docs);

  _pyodide_importhook = PyImport_ImportModule("_pyodide._importhook");

  internal_error = PyObject_GetAttrString(_pyodide_core_docs, "InternalError");
  FAIL_IF_NULL(internal_error);
  conversion_error =
    PyObject_GetAttrString(_pyodide_core_docs, "ConversionError");
  FAIL_IF_NULL(conversion_error);

  FAIL_IF_MINUS_ONE(PyModule_AddFunctions(core_module, methods));

  tbmod = PyImport_ImportModule("traceback");
  FAIL_IF_NULL(tbmod);

  success = true;
finally:
  Py_CLEAR(_pyodide_core_docs);
  return success ? 0 : -1;
}
