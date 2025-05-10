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
_js2python_none(void)
{
  Py_RETURN_NONE;
}

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_true(void)
{
  Py_RETURN_TRUE;
}

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_false(void)
{
  Py_RETURN_FALSE;
}

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_pyproxy(PyObject* val)
{
  Py_INCREF(val);
  return val;
}

EM_JS_REF(PyObject*, js2python_immutable_js, (JsVal value), {
  let result = Module.js2python_convertImmutable(value);
  // clang-format off
  if (result !== undefined) {
    // clang-format on
    return result;
  }
  return 0;
});

EMSCRIPTEN_KEEPALIVE PyObject*
js2python_immutable(JsVal val)
{
  return js2python_immutable_js(val);
}

EM_JS_REF(PyObject*, js2python_js, (JsVal value), {
  let result = Module.js2python_convertImmutable(value);
  // clang-format off
  if (result !== undefined) {
    // clang-format on
    return result;
  }
  return _JsProxy_create(value);
})

EMSCRIPTEN_KEEPALIVE PyObject*
js2python(JsVal val)
{
  return js2python_js(val);
}

/**
 * Convert a JavaScript object to Python to a given depth. This is the
 * implementation of `toJs`.
 */
// clang-format off
EM_JS_REF(PyObject*, js2python_convert, (JsVal v, int depth, JsVal defaultConverter), {
  return Module.js2python_convert(v, { depth, defaultConverter });
});
// clang-format on
