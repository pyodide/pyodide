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

int
error_handling_init()
{
  EM_ASM({
    Module.handle_js_error = function(e)
    {
      let err = Module.hiwire.new_value(e);
      _PyodideErr_SetJsError(err);
      Module.hiwire.decref(err);
    };
  });
  return 0;
}
