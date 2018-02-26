#include "js2python.hpp"

#include "jsproxy.hpp"

using emscripten::val;

PyObject *jsToPython(val x, val *parent, const char *name) {
  val xType = x.typeOf();

  if (xType.equals(val("string"))) {
    std::wstring x_str = x.as<std::wstring>();
    return PyUnicode_FromWideChar(&*x_str.begin(), x_str.size());
  } else if (xType.equals(val("number"))) {
    double x_double = x.as<double>();
    return PyFloat_FromDouble(x_double);
  } else if (xType.equals(val("undefined"))) {
    Py_INCREF(Py_None);
    return Py_None;
  } else {
    return JsProxy_cnew(x, parent, name);
  }
}
