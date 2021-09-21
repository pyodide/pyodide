// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "error_handling.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include <emscripten.h>

static PyObject* tbmod = NULL;

_Py_IDENTIFIER(format_exception);
_Py_IDENTIFIER(last_type);
_Py_IDENTIFIER(last_value);
_Py_IDENTIFIER(last_traceback);

EM_JS_NUM(errcode, console_error, (char* msg), {
  let jsmsg = UTF8ToString(msg);
  console.error(jsmsg);
});

// Right now this is dead code (probably), please don't remove it.
// Intended for debugging purposes.
EM_JS_NUM(errcode, console_error_obj, (JsRef obj), {
  console.error(Module.hiwire.get_value(obj));
});

/**
 * Set Python error indicator from Javascript.
 *
 * In Javascript, we can't access the type without relying on the ABI of
 * PyObject. Py_TYPE is part of the Python restricted API which means that there
 * are fairly strong guarantees about the ABI stability, but even so writing
 * HEAP32[err/4 + 1] is a bit opaque.
 */
void
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
EM_JS_REF(JsRef, new_error, (const char* msg, PyObject* err), {
  return Module.hiwire.new_value(
    new Module.PythonError(UTF8ToString(msg), err));
});

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
  if (*type == NULL || *type == Py_None || *value == NULL ||
      *value == Py_None) {
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
  _PySys_SetObjectId(&PyId_last_type, type);
  _PySys_SetObjectId(&PyId_last_value, value);
  _PySys_SetObjectId(&PyId_last_traceback, traceback);
}

/**
 * Restore sys.last_exception as the current exception if sys.last_value matches
 * the argument value. Used for reentrant errors.
 * Returns true if it restored the error indicator, false otherwise.
 *
 * If we throw a Javascript PythonError and it bubbles out to the enclosing
 * Python scope (i.e., doesn't get caught in Javascript) then we want to restore
 * the original Python exception. This produces much better stack traces in case
 * of reentrant calls and prevents issues like a KeyboardInterrupt being wrapped
 * into a PythonError being wrapped into a JsException and being caught.
 *
 * We don't do the same thing for Javascript messages that pass through Python
 * because the Python exceptions have good Javascript stack traces but
 * Javascript errors have no Python stack info. Also, Javascript has much weaker
 * support for catching errors by type.
 */
bool
restore_sys_last_exception(void* value)
{
  bool success = false;
  FAIL_IF_NULL(value);
  PyObject* last_type = _PySys_GetObjectId(&PyId_last_type);
  FAIL_IF_NULL(last_type);
  PyObject* last_value = _PySys_GetObjectId(&PyId_last_value);
  FAIL_IF_NULL(last_value);
  PyObject* last_traceback = _PySys_GetObjectId(&PyId_last_traceback);
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

EM_JS(void, fail_test, (), { Module.fail_test = true; })

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
 * Wrap the exception in a Javascript PythonError object.
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
  PyObject* pystr = NULL;
  JsRef jserror = NULL;
  fetch_and_normalize_exception(&type, &value, &traceback);
  store_sys_last_exception(type, value, traceback);

  pystr = format_exception_traceback(type, value, traceback);
  FAIL_IF_NULL(pystr);
  const char* pystr_utf8 = PyUnicode_AsUTF8(pystr);
  FAIL_IF_NULL(pystr_utf8);
  jserror = new_error(pystr_utf8, value);
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
    jserror = new_error("Error occurred while formatting traceback", 0);
  }
  Py_CLEAR(type);
  Py_CLEAR(value);
  Py_CLEAR(traceback);
  Py_CLEAR(pystr);
  return jserror;
}

EM_JS_NUM(errcode, log_python_error, (JsRef jserror), {
  let msg = Module.hiwire.get_value(jserror).message;
  console.warn("Python exception:\n" + msg + "\n");
  return 0;
});

/**
 * Convert the current Python error to a javascript error and throw it.
 */
void _Py_NO_RETURN
pythonexc2js()
{
  JsRef jserror = wrap_exception();
  log_python_error(jserror);
  // hiwire_throw_error steals jserror
  hiwire_throw_error(jserror);
}

char* error__js_funcname_string = "<javascript frames>";
char* error__js_filename_string = "???.js";

EM_JS_NUM(errcode, error_handling_init_js, (), {
  Module.handle_js_error = function(e)
  {
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
      // Wrap the Javascript error
      let eidx = Module.hiwire.new_value(e);
      let err = _JsProxy_create(eidx);
      _set_error(err);
      _Py_DecRef(err);
      Module.hiwire.decref(eidx);
    }
    // Add a marker to the traceback to indicate that we passed through "native"
    // frames.
    // TODO? Use stacktracejs to add more detailed info here.
    __PyTraceback_Add(HEAPU32[_error__js_funcname_string / 4],
                      HEAPU32[_error__js_filename_string / 4],
                      -1);
  };
  class PythonError extends Error
  {
    constructor(message, error_address)
    {
      super(message);
      this.name = this.constructor.name;
      // The address of the error we are wrapping. We may later compare this
      // against sys.last_value.
      // WARNING: we don't own a reference to this pointer, dereferencing it
      // may be a use-after-free error!
      this.__error_address = error_address;
    }
  };
  Module.PythonError = PythonError;
  // A special marker. If we call a CPython API from an EM_JS function and the
  // CPython API sets an error, we might want to return an error status back to
  // C keeping the current Python error flag. This signals to the EM_JS wrappers
  // that the Python error flag is set and to leave it alone and return the
  // appropriate error value (either NULL or -1).
  class _PropagatePythonError extends Error
  {
    constructor()
    {
      Module.fail_test = true;
      super("If you are seeing this message, an internal Pyodide error has " +
            "occurred. Please report it to the Pyodide maintainers.");
    }
  } Module._PropagatePythonError = _PropagatePythonError;
  return 0;
})

PyObject*
trigger_fatal_error(PyObject* mod, PyObject* _args)
{
  EM_ASM(throw new Error("intentionally triggered fatal error!"););
  Py_UNREACHABLE();
}

static PyMethodDef methods[] = {
  {
    "trigger_fatal_error",
    trigger_fatal_error,
    METH_NOARGS,
  },
  { NULL } /* Sentinel */
};

PyObject* internal_error;
PyObject* conversion_error;

int
error_handling_init(PyObject* core_module)
{
  bool success = false;
  internal_error = PyErr_NewException("pyodide.InternalError", NULL, NULL);
  FAIL_IF_NULL(internal_error);

  conversion_error = PyErr_NewExceptionWithDoc(
    "pyodide.ConversionError",
    PyDoc_STR("Raised when conversion between Javascript and Python fails."),
    NULL,
    NULL);
  FAIL_IF_NULL(conversion_error);
  // ConversionError is public
  FAIL_IF_MINUS_ONE(
    PyObject_SetAttrString(core_module, "ConversionError", conversion_error));
  FAIL_IF_MINUS_ONE(PyModule_AddFunctions(core_module, methods));

  FAIL_IF_MINUS_ONE(error_handling_init_js());

  tbmod = PyImport_ImportModule("traceback");
  FAIL_IF_NULL(tbmod);

  success = true;
finally:
  return success ? 0 : -1;
}
