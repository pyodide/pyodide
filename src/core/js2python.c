#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "js2python.h"

#include <emscripten.h>

#include "jsproxy.h"
#include "pyproxy.h"

// Since we're going *to* Python, just let any Python exceptions at conversion
// bubble out to Python

PyObject*
_js2python_allocate_string(int size, int max_code_point)
{
  return PyUnicode_New(size, max_code_point);
}

void*
_js2python_get_ptr(PyObject* obj)
{
  return PyUnicode_DATA(obj);
}

PyObject*
_js2python_number(double val)
{
  double i;

  if (modf(val, &i) == 0.0)
    return PyLong_FromDouble(i);

  return PyFloat_FromDouble(val);
}

PyObject*
_js2python_none()
{
  Py_RETURN_NONE;
}

PyObject*
_js2python_true()
{
  Py_RETURN_TRUE;
}

PyObject*
_js2python_false()
{
  Py_RETURN_FALSE;
}

PyObject*
_js2python_pyproxy(PyObject* val)
{
  Py_INCREF(val);
  return val;
}

PyObject*
_js2python_memoryview(JsRef id)
{
  PyObject* jsproxy = JsProxy_create(id);
  return PyMemoryView_FromObject(jsproxy);
}

PyObject*
_js2python_jsproxy(JsRef id)
{
  return JsProxy_create(id);
}

// TODO: Add some meaningful order
EM_JS_REF(PyObject*, __js2python, (JsRef id), {
  function __js2python_string(value)
  {
    // The general idea here is to allocate a Python string and then
    // have Javascript write directly into its buffer.  We first need
    // to determine if is needs to be a 1-, 2- or 4-byte string, since
    // Python handles all 3.
    let max_code_point = 0;
    let length = value.length;
    for (let i = 0; i < value.length; i++) {
      let code_point = value.codePointAt(i);
      max_code_point = Math.max(max_code_point, code_point);
      if (code_point > 0xffff) {
        // If we have a code point requiring UTF-16 surrogate pairs, the
        // number of characters (codePoints) is less than value.length,
        // so skip the next charCode and subtract 1 from the length.
        i++;
        length--;
      }
    }

    let result = __js2python_allocate_string(length, max_code_point);
    // clang-format off
    if (result === 0) {
      // clang-format on
      return 0;
    }

    let ptr = __js2python_get_ptr(result);
    if (max_code_point > 0xffff) {
      ptr = ptr / 4;
      for (let i = 0, j = 0; j < length; i++, j++) {
        let code_point = value.codePointAt(i);
        Module.HEAPU32[ptr + j] = code_point;
        if (code_point > 0xffff) {
          i++;
        }
      }
    } else if (max_code_point > 0xff) {
      ptr = ptr / 2;
      for (let i = 0; i < length; i++) {
        Module.HEAPU16[ptr + i] = value.codePointAt(i);
      }
    } else {
      for (let i = 0; i < length; i++) {
        Module.HEAPU8[ptr + i] = value.codePointAt(i);
      }
    }

    return result;
  }

  // clang-format off
  let value = Module.hiwire.get_value(id);
  let type = typeof value;
  if (type === 'string') {
    return __js2python_string(value);
  } else if (type === 'number') {
    return __js2python_number(value);
  } else if (value === undefined || value === null) {
    return __js2python_none();
  } else if (value === true) {
    return __js2python_true();
  } else if (value === false) {
    return __js2python_false();
  } else if (Module.PyProxy.isPyProxy(value)) {
    return __js2python_pyproxy(Module.PyProxy._getPtr(value));
  } else if (value['byteLength'] !== undefined) {
    return __js2python_memoryview(id);
  } else {
    return __js2python_jsproxy(id);
  }
  // clang-format on
});

PyObject*
js2python(JsRef id)
{
  return (PyObject*)__js2python(id);
}

int
js2python_init()
{
  return 0;
}
