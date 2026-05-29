#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "datetime.h"

#include "error_handling.h"
#include "js2python.h"
#include "python2js.h"

#include <emscripten.h>
#include <math.h>

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

EMSCRIPTEN_KEEPALIVE int compat_null_to_none = 0;
EMSCRIPTEN_KEEPALIVE int auto_convert_date = 1;

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_null(void)
{
  if (compat_null_to_none) {
    Py_RETURN_NONE;
  }
  Py_INCREF(py_jsnull);
  return py_jsnull;
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

EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_bigint(PyObject* val)
{
  return PyObject_CallOneArg(py_JsBigInt, val);
}

EMSCRIPTEN_KEEPALIVE int
_js2python_should_convert_date(void)
{
  return auto_convert_date;
}

// Convert a JS Date timestamp (UTC milliseconds since epoch) to a
// timezone-aware Python datetime. Microsecond precision comes from
// the fractional part of timestamp_ms / 1000, handled internally by
// datetime.fromtimestamp().
EMSCRIPTEN_KEEPALIVE PyObject*
_js2python_datetime(double timestamp_ms)
{
  double timestamp_s = timestamp_ms / 1000.0;

  PyObject* ts_obj = PyFloat_FromDouble(timestamp_s);
  if (ts_obj == NULL) {
    return NULL;
  }

  PyObject* result = PyObject_CallMethod(
    py_datetime_class, "fromtimestamp", "OO", ts_obj, py_timezone_utc);
  Py_DECREF(ts_obj);
  if (result == NULL) {
    // fromtimestamp raises OverflowError if the timestamp is out of range,
    // or OSError on localtime() failure.
    // https://docs.python.org/3/library/datetime.html#datetime.date.fromtimestamp
    if (PyErr_ExceptionMatches(PyExc_OverflowError) ||
        PyErr_ExceptionMatches(PyExc_OSError)) {
      PyErr_Clear();
      PyErr_SetString(conversion_error,
                      "Cannot convert JavaScript Date to Python datetime: "
                      "timestamp out of range for datetime");
    }
    return NULL;
  }
  return result;
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
