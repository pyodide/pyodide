#include "error_handling.h"
#include "Python.h"
#include "jsproxy.h"
#include <emscripten.h>

EM_JS_NUM(errcode, log_error, (char* msg), {
  let jsmsg = UTF8ToString(msg);
  console.error(jsmsg);
});

void
PyodideErr_SetJsError(JsRef err)
{
  PyObject* py_err = JsProxy_new_error(err);
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
