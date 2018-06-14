#include "js2python.h"

#include <emscripten.h>

#include "jsproxy.h"
#include "pyproxy.h"

// Since we're going *to* Python, just let any Python exceptions at conversion
// bubble out to Python

int
_js2python_string(char* val)
{
  return (int)PyUnicode_FromString(val);
}

int
_js2python_number(double val)
{
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
_js2python_bytes(char* bytes, int length)
{
  return (int)PyBytes_FromStringAndSize(bytes, length);
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
    var charptr = allocate(intArrayFromString(value), 'i8', ALLOC_NORMAL);
    var result = __js2python_string(charptr);
    _free(charptr);
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
    var bytes = allocate(value, 'i8', ALLOC_NORMAL);
    var result = __js2python_bytes(bytes, value['byteLength']);
    _free(bytes);
    return result;
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
