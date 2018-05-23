#include "js2python.h"

#include <emscripten.h>

#include "jsproxy.h"
#include "pyproxy.h"

// Since we're going *to* Python, just let any Python exceptions at conversion
// bubble out to Python

int _jsStringToPython(char *val) {
  return (int)PyUnicode_FromString(val);
}

int _jsNumberToPython(double val) {
  return (int)PyFloat_FromDouble(val);
}

int _pythonNone() {
  Py_INCREF(Py_None);
  return (int)Py_None;
}

int _pythonTrue() {
  Py_INCREF(Py_True);
  return (int)Py_True;
}

int _pythonFalse() {
  Py_INCREF(Py_False);
  return (int)Py_False;
}

int _jsPyProxyToPython(PyObject *val) {
  Py_INCREF(val);
  return (int)val;
}

int _jsBytesToPython(char *bytes, int length) {
  return (int)PyBytes_FromStringAndSize(bytes, length);
}

int _jsProxyToPython(int id) {
  return (int)JsProxy_cnew(id);
}

// TODO: Add some meaningful order

EM_JS(int, __jsToPython, (int id), {
  var value = Module.hiwire_get_value(id);
  var type = typeof value;
  if (type === 'string') {
    var charptr = allocate(intArrayFromString(value), 'i8', ALLOC_NORMAL);
    var result = __jsStringToPython(charptr);
    _free(charptr);
    return result;
  } else if (type === 'number') {
    return __jsNumberToPython(value);
  } else if (value === undefined || value === null) {
    return __pythonNone();
  } else if (value === true) {
    return __pythonTrue();
  } else if (value === false) {
    return __pythonFalse();
    // TODO: Add attribute for type of object and check it here
  } else if (value['$$'] !== undefined) {
    return __jsPyProxyToPython(value['$$']);
  } else if (value['byteLength'] !== undefined) {
    var bytes = allocate(value, 'i8', ALLOC_NORMAL);
    var result = __jsBytesToPython(bytes, value['byteLength']);
    _free(bytes);
    return result;
  } else {
    return __jsProxyToPython(id);
  }
});

PyObject *jsToPython(int id) {
  return (PyObject *)__jsToPython(id);
}

int jsToPython_Ready() {
  return 0;
}
