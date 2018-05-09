#include "pyproxy.hpp"

using emscripten::val;

val Py::makeProxy(PyObject *obj) {
  Py_INCREF(obj);
  return val::global("Proxy").new_(val(obj), val::global("pyodide")["Py"]);
}

bool Py::isExtensible(val obj, val proxy) {
  return true;
}

bool Py::has(val obj, val idx) {
  PyObject *x = obj.as<PyObject *>(emscripten::allow_raw_pointers());
  PyObject *pyidx = jsToPython(idx);
  bool result = PyObject_HasAttr(x, pyidx) ? true: false;
  Py_DECREF(pyidx);
  return result;
}

val Py::get(val obj, val idx, val proxy) {
  if (idx.equals(val("$$"))) {
    return obj["$$"];
  }

  PyObject *x = obj.as<PyObject *>(emscripten::allow_raw_pointers());
  PyObject *pyidx = jsToPython(idx);
  PyObject *attr = PyObject_GetAttr(x, pyidx);
  Py_DECREF(pyidx);
  if (attr == NULL) {
    return pythonExcToJs();
  }

  val ret = pythonToJs(attr);
  Py_DECREF(attr);
  return ret;
};

val Py::set(val obj, val idx, val value, val proxy) {
  PyObject *x = obj.as<PyObject *>(emscripten::allow_raw_pointers());
  PyObject *pyidx = jsToPython(idx);
  PyObject *pyvalue = jsToPython(value);
  int ret = PyObject_SetAttr(x, pyidx, pyvalue);
  Py_DECREF(pyidx);
  Py_DECREF(pyvalue);

  if (ret) {
    return pythonExcToJs();
  }
  return value;
}

val Py::deleteProperty(val obj, val idx) {
  PyObject *x = obj.as<PyObject *>(emscripten::allow_raw_pointers());
  PyObject *pyidx = jsToPython(idx);

  int ret = PyObject_DelAttr(x, pyidx);
  Py_DECREF(pyidx);

  if (ret) {
    return pythonExcToJs();
  }

  return val::global("undefined");
}

val Py::ownKeys(val obj) {
  PyObject *x = obj.as<PyObject *>(emscripten::allow_raw_pointers());
  PyObject *dir = PyObject_Dir(x);
  if (dir == NULL) {
    return pythonExcToJs();
  }

  val result = val::global("Array").new_();
  result.call<int>("push", val("$$"));
  Py_ssize_t n = PyList_Size(dir);
  for (Py_ssize_t i = 0; i < n; ++i) {
    PyObject *entry = PyList_GetItem(dir, i);
    result.call<int>("push", pythonToJs(entry));
  }
  Py_DECREF(dir);

  return result;
}

val Py::enumerate(val obj) {
  return Py::ownKeys(obj);
}

val PyCallable::makeCallableProxy(PyObject *obj) {
  return val::global("pyodide").call<val>("makeCallableProxy", PyCallable(obj));
}

val PyCallable::call(val args, val kwargs) {
  PyObject *pyargs = jsToPythonArgs(args);
  if (pyargs == NULL) {
    return pythonExcToJs();
  }

  PyObject *pykwargs = jsToPythonKwargs(kwargs);
  if (pykwargs == NULL) {
    Py_DECREF(pyargs);
    return pythonExcToJs();
  }

  PyObject *pyret = PyObject_Call(x, pyargs, pykwargs);
  Py_DECREF(pyargs);
  Py_DECREF(pykwargs);
  if (pyret == NULL) {
    return pythonExcToJs();
  }

  val ret = pythonToJs(pyret);
  Py_DECREF(pyret);
  return ret;
}
