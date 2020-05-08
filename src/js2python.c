#include "js2python.h"

#include <emscripten.h>

#include "jsproxy.h"
#include "pyproxy.h"

// Since we're going *to* Python, just let any Python exceptions at conversion
// bubble out to Python

int
_js2python_allocate_string(int size, int max_code_point)
{
  return (int)PyUnicode_New(size, max_code_point);
}

int
_js2python_get_ptr(int obj)
{
  return (int)PyUnicode_DATA((PyObject*)obj);
}

int
_js2python_number(double val)
{
  double i;

  if (modf(val, &i) == 0.0)
    return (int)PyLong_FromDouble(i);

  return (int)PyFloat_FromDouble(val);
}

int
_js2python_none()
{
  Py_INCREF(Py_None);
  return (int)Py_None;
}

int
_js2python_true()
{
  Py_INCREF(Py_True);
  return (int)Py_True;
}

int
_js2python_false()
{
  Py_INCREF(Py_False);
  return (int)Py_False;
}

int
_js2python_pyproxy(PyObject* val)
{
  Py_INCREF(val);
  return (int)val;
}

int
_js2python_memoryview(int id)
{
  PyObject* jsproxy = JsProxy_cnew(id);
  return (int)PyMemoryView_FromObject(jsproxy);
}

int
_js2python_jsproxy(int id)
{
  return (int)JsProxy_cnew(id);
}

// TODO: Add some meaningful order

EM_JS(int, __js2python, (int id), {
  // clang-format off
  var value = Module.hiwire_get_value(id);
  var type = typeof value;
  if (type === 'string') {
    // The general idea here is to allocate a Python string and then
    // have Javascript write directly into its buffer.  We first need
    // to determine if is needs to be a 1-, 2- or 4-byte string, since
    // Python handles all 3.
    var max_code_point = 0;
    var length = value.length;
    for (var i = 0; i < value.length; i++) {
      code_point = value.codePointAt(i);
      max_code_point = Math.max(max_code_point, code_point);
      if (code_point > 0xffff) {
        // If we have a code point requiring UTF-16 surrogate pairs, the
        // number of characters (codePoints) is less than value.length,
        // so skip the next charCode and subtract 1 from the length.
        i++;
        length--;
      }
    }

    var result = __js2python_allocate_string(length, max_code_point);
    if (result == 0) {
      return 0;
    }

    var ptr = __js2python_get_ptr(result);
    if (max_code_point > 0xffff) {
      ptr = ptr / 4;
      for (var i = 0, j = 0; j < length; i++, j++) {
        var code_point = value.codePointAt(i);
        Module.HEAPU32[ptr + j] = code_point;
        if (code_point > 0xffff) {
          i++;
        }
      }
    } else if (max_code_point > 0xff) {
      ptr = ptr / 2;
      for (var i = 0; i < length; i++) {
        Module.HEAPU16[ptr + i] = value.codePointAt(i);
      }
    } else {
      for (var i = 0; i < length; i++) {
        Module.HEAPU8[ptr + i] = value.codePointAt(i);
      }
    }

    return result;
  } else if (type === 'number') {
    return __js2python_number(value);
  } else if (value === undefined || value === null) {
    return __js2python_none();
  } else if (value === true) {
    return __js2python_true();
  } else if (value === false) {
    return __js2python_false();
  } else if (Module.PyProxy.isPyProxy(value)) {
    return __js2python_pyproxy(Module.PyProxy.getPtr(value));
  } else if (value['byteLength'] !== undefined) {
    return __js2python_memoryview(id);
  } else {
    return __js2python_jsproxy(id);
  }
  // clang-format on
});

PyObject*
js2python(int id)
{
  return (PyObject*)__js2python(id);
}

int
js2python_init()
{
  return 0;
}
