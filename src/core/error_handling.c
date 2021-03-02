// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "error_handling.h"
#include "jsproxy.h"
#include <emscripten.h>

EM_JS_NUM(errcode, log_error, (char* msg), {
  let jsmsg = UTF8ToString(msg);
  console.error(jsmsg);
});

// Right now this is dead code (probably), please don't remove it.
// Intended for debugging purposes.
EM_JS_NUM(errcode, log_error_obj, (JsRef obj), {
  console.error(Module.hiwire.get_value(obj));
});

void
PyodideErr_SetJsError(JsRef err)
{
  PyObject* py_err = JsProxy_create(err);
  PyErr_SetObject((PyObject*)(py_err->ob_type), py_err);
}

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

  EM_ASM({
    Module.handle_js_error = function(e)
    {
      let err = Module.hiwire.new_value(e);
      _PyodideErr_SetJsError(err);
      Module.hiwire.decref(err);
    };
  });

  success = true;
finally:
  return success ? 0 : -1;
}
