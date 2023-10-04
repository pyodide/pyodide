// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "error_handling.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include <emscripten.h>
#include <stdio.h>

static PyObject* tbmod = NULL;

_Py_IDENTIFIER(__qualname__);
_Py_IDENTIFIER(format_exception);

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
EM_JS(void, console_error_obj, (JsRef obj), {
  console.error(Hiwire.get_value(obj));
});

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
EM_JS_REF(
JsRef,
new_error,
(const char* type, const char* msg, PyObject* err),
{
  return Hiwire.new_value(
    new API.PythonError(UTF8ToString(type), UTF8ToString(msg), err));
});
// clang-format on

/**
 * Fetch the exception, normalize it, and ensure that traceback is not NULL.
 *
 * Always succeeds, always results in type, value, traceback not NULL.
 */
static void
fetch_and_normalize_exception(PyObject** type,
                              PyObject** value,
                              PyObject** traceback)
{
  PyErr_Fetch(type, value, traceback);
  PyErr_NormalizeException(type, value, traceback);
  if (*type == NULL || Py_IsNone(*type) || *value == NULL ||
      Py_IsNone(*value)) {
    Py_CLEAR(*type);
    Py_CLEAR(*value);
    Py_CLEAR(*traceback);
    fail_test();
    PyErr_SetString(PyExc_TypeError,
                    "Pyodide internal error: no exception type or value");
    PyErr_Fetch(type, value, traceback);
    PyErr_NormalizeException(type, value, traceback);
  }

  if (*traceback == NULL) {
    *traceback = Py_None;
    Py_INCREF(*traceback);
  }
  PyException_SetTraceback(*value, *traceback);
}

static void
store_sys_last_exception(PyObject* type, PyObject* value, PyObject* traceback)
{
  PySys_SetObject("last_type", type);
  PySys_SetObject("last_value", value);
  PySys_SetObject("last_traceback", traceback);
}

/**
 * Restore sys.last_exception as the current exception if sys.last_value matches
 * the argument value. Used for reentrant errors.
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
bool
restore_sys_last_exception(void* value)
{
  bool success = false;
  FAIL_IF_NULL(value);
  PyObject* last_type = PySys_GetObject("last_type");
  FAIL_IF_NULL(last_type);
  PyObject* last_value = PySys_GetObject("last_value");
  FAIL_IF_NULL(last_value);
  PyObject* last_traceback = PySys_GetObject("last_traceback");
  FAIL_IF_NULL(last_traceback);
  if (value != last_value) {
    return 0;
  }
  // PyErr_Restore steals a reference to each of its arguments so need to incref
  // them first.
  Py_INCREF(last_type);
  Py_INCREF(last_value);
  Py_INCREF(last_traceback);
  PyErr_Restore(last_type, last_value, last_traceback);
  success = true;
finally:
  return success;
}

EM_JS(void, fail_test, (), { API.fail_test = true; })

/**
 * Calls traceback.format_exception(type, value, traceback) and joins the
 * resulting list of strings together.
 */
static PyObject*
format_exception_traceback(PyObject* type, PyObject* value, PyObject* traceback)
{
  PyObject* pylines = NULL;
  PyObject* empty = NULL;
  PyObject* result = NULL;

  pylines = _PyObject_CallMethodIdObjArgs(
    tbmod, &PyId_format_exception, type, value, traceback, NULL);
  FAIL_IF_NULL(pylines);
  empty = PyUnicode_New(0, 0);
  FAIL_IF_NULL(empty);
  result = PyUnicode_Join(empty, pylines);
  FAIL_IF_NULL(result);

finally:
  Py_CLEAR(pylines);
  Py_CLEAR(empty);
  return result;
}

/**
 * Wrap the exception in a JavaScript PythonError object.
 *
 * The return value of this function is always a valid hiwire ID to an error
 * object. It never returns NULL.
 *
 * We are cautious about leaking the Python stack frame, so we don't increment
 * the reference count on the exception object, we just store a pointer to it.
 * Later we can check if this pointer is equal to sys.last_value and if so
 * restore the exception (see restore_sys_last_exception).
 *
 * WARNING: dereferencing the error pointer stored on the PythonError is a
 * use-after-free bug.
 */
JsRef
wrap_exception()
{
  bool success = false;
  PyObject* type = NULL;
  PyObject* value = NULL;
  PyObject* traceback = NULL;
  PyObject* typestr = NULL;
  PyObject* pystr = NULL;
  JsRef jserror = NULL;
  fetch_and_normalize_exception(&type, &value, &traceback);
  store_sys_last_exception(type, value, traceback);

  typestr = _PyObject_GetAttrId(type, &PyId___qualname__);
  FAIL_IF_NULL(typestr);
  const char* typestr_utf8 = PyUnicode_AsUTF8(typestr);
  FAIL_IF_NULL(typestr_utf8);
  pystr = format_exception_traceback(type, value, traceback);
  FAIL_IF_NULL(pystr);
  const char* pystr_utf8 = PyUnicode_AsUTF8(pystr);
  FAIL_IF_NULL(pystr_utf8);
  jserror = new_error(typestr_utf8, pystr_utf8, value);
  FAIL_IF_NULL(jserror);

  success = true;
finally:
  if (!success) {
    fail_test();
    PySys_WriteStderr(
      "Pyodide: Internal error occurred while formatting traceback:\n");
    PyErr_Print();
    if (type != NULL) {
      PySys_WriteStderr("\nOriginal exception was:\n");
      PyErr_Display(type, value, traceback);
    }
    jserror = new_error(
      "PyodideInternalError", "Error occurred while formatting traceback", 0);
  }
  Py_CLEAR(type);
  Py_CLEAR(value);
  Py_CLEAR(traceback);
  Py_CLEAR(pystr);
  return jserror;
}

#ifdef DEBUG_F
EM_JS(void, log_python_error, (JsRef jserror), {
  // If a js error occurs in here, it's a weird edge case. This will probably
  // never happen, but for maximum paranoia let's double check.
  try {
    let msg = Hiwire.get_value(jserror).message;
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
  JsRef jserror = wrap_exception();
#ifdef DEBUG_F
  log_python_error(jserror);
#endif
  // hiwire_throw_error steals jserror
  hiwire_throw_error(jserror);
}

PyObject*
trigger_fatal_error(PyObject* mod, PyObject* _args)
{
  EM_ASM(throw new Error("intentionally triggered fatal error!"););
  Py_UNREACHABLE();
}

/**
 * This is for testing fatal errors in test_pyodide
 */
PyObject*
raw_call(PyObject* mod, PyObject* jsproxy)
{
  JsRef func = JsProxy_AsJs(jsproxy);
  EM_ASM(Hiwire.get_value($0)(), func);
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
  return success ? 0 : -1;
}
