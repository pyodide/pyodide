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

void
PyodideErr_SetJsError(JsRef err)
{
  PyObject* py_err = JsProxy_create(err);
  PyErr_SetObject((PyObject*)(py_err->ob_type), py_err);
  Py_DECREF(py_err);
}

PyObject* internal_error;
PyObject* conversion_error;

EM_JS_REF(JsRef, new_error, (const char* msg, JsRef pyproxy), {
  return Module.hiwire.new_value(new Module.PythonError(
    UTF8ToString(msg), Module.hiwire.get_value(pyproxy)));
});

static int
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
    PyErr_SetString(PyExc_TypeError, "No exception type or value");
    FAIL();
  }

  if (*traceback == NULL) {
    *traceback = Py_None;
    Py_INCREF(*traceback);
  }
  PyException_SetTraceback(*value, *traceback);
  return 0;

finally:
  return -1;
}

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

JsRef
wrap_exception(bool attach_python_error)
{
  bool success = false;
  PyObject* type = NULL;
  PyObject* value = NULL;
  PyObject* traceback = NULL;
  PyObject* pystr = NULL;
  JsRef pyexc_proxy = NULL;
  JsRef jserror = NULL;

  FAIL_IF_MINUS_ONE(fetch_and_normalize_exception(&type, &value, &traceback));
  pystr = format_exception_traceback(type, value, traceback);
  FAIL_IF_NULL(pystr);
  const char* pystr_utf8 = PyUnicode_AsUTF8(pystr);
  FAIL_IF_NULL(pystr_utf8);

  if (attach_python_error) {
    pyexc_proxy = pyproxy_new(value);
  } else {
    pyexc_proxy = Js_undefined;
  }
  jserror = new_error(pystr_utf8, pyexc_proxy);

  success = true;
finally:
  // Log an appropriate warning.
  if (!success) {
    PySys_WriteStderr("Error occurred while formatting traceback:\n");
    PyErr_Print();
    if (type != NULL) {
      PySys_WriteStderr("\nOriginal exception was:\n");
      PyErr_Display(type, value, traceback);
    }
  }

  if (success) {
    _PySys_SetObjectId(&PyId_last_type, type);
    _PySys_SetObjectId(&PyId_last_value, value);
    _PySys_SetObjectId(&PyId_last_traceback, traceback);
  }
  Py_CLEAR(type);
  Py_CLEAR(value);
  Py_CLEAR(traceback);
  Py_CLEAR(pystr);
  hiwire_CLEAR(pyexc_proxy);
  if (!success) {
    hiwire_CLEAR(jserror);
  }
  return jserror;
}

EM_JS_NUM(errcode, log_python_error, (JsRef jserror), {
  let msg = Module.hiwire.get_value(jserror).message;
  console.warn("Python exception:\n" + msg + "\n");
  return 0;
});

void _Py_NO_RETURN
pythonexc2js()
{
  JsRef jserror = wrap_exception(false);
  if (jserror != NULL) {
    log_python_error(jserror);
  } else {
    jserror =
      new_error("Error occurred while formatting traceback", Js_undefined);
  }
  // hiwire_throw_error steals jserror
  hiwire_throw_error(jserror);
}

EM_JS_NUM(errcode, error_handling_init_js, (), {
  Module.handle_js_error = function(e)
  {
    let err = Module.hiwire.new_value(e);
    _PyodideErr_SetJsError(err);
    Module.hiwire.decref(err);
  };
  class PythonError extends Error
  {
    constructor(message, pythonError)
    {
      super(message);
      this.name = this.constructor.name;
      this.pythonError = pythonError;
    }

    clear()
    {
      if (this.pythonError) {
        this.pythonError.destroy();
        delete this.pythonError;
      }
    }
  };
  Module.PythonError = PythonError;
  return 0;
})

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

  FAIL_IF_MINUS_ONE(error_handling_init_js());

  tbmod = PyImport_ImportModule("traceback");
  FAIL_IF_NULL(tbmod);

  success = true;
finally:
  return success ? 0 : -1;
}
