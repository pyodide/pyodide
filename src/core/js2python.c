#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "js2python.h"

#include <emscripten.h>

#include "jsmemops.h"
#include "jsproxy.h"
#include "pyproxy.h"

// PyUnicodeDATA is a macro, we need to access it from JavaScript
EMSCRIPTEN_KEEPALIVE void*
PyUnicode_Data(PyObject* obj)
{
  return PyUnicode_DATA(obj);
}

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_none()
{
  Py_RETURN_NONE;
}

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_true()
{
  Py_RETURN_TRUE;
}

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_false()
{
  Py_RETURN_FALSE;
}

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_pyproxy(PyObject* val)
{
  Py_INCREF(val);
  return val;
}

EM_JS_REF(PyObject*, js2python_immutable_js, (JsRef id), {
  let value = Hiwire.get_value(id);
  let result = Module.js2python_convertImmutable(value, id);
  // clang-format off
  if (result !== undefined) {
    // clang-format on
    return result;
  }
  return 0;
});

EMSCRIPTEN_KEEPALIVE PyObject*
js2python_immutable(JsRef id)
{
  return js2python_immutable_js(id);
}

EM_JS_REF(PyObject*, js2python_val, (JsVal value), {
  let result = Module.js2python_convertImmutable(value, undefined);
  // clang-format off
  if (result !== undefined) {
    // clang-format on
    return result;
  }
  return _JsProxy_create_val(value);
})

EMSCRIPTEN_KEEPALIVE PyObject*
js2python(JsRef id)
{
  return js2python_val(hiwire_get(id));
}

/**
 * Convert a JavaScript object to Python to a given depth. This is the
 * implementation of `toJs`.
 */
// clang-format off
EM_JS_REF(PyObject*, js2python_convert, (JsRef id, int depth, JsRef default_converter), {
  let defaultConverter = default_converter
    ? Module.hiwire.get_value(default_converter)
    : undefined;
  return Module.js2python_convert(id, { depth, defaultConverter });
});
// clang-format on

#include "include_js_file.h"
#include "js2python.js"
