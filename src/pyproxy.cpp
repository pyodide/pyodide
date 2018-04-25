#include "pyproxy.hpp"

using emscripten::val;

Py::Py(PyObject *obj) : x(obj) {
  Py_INCREF(x);
}

Py::Py(const Py& o) : x(o.x) {
  Py_INCREF(x);
}

Py::~Py() {
  Py_DECREF(x);
}

val Py::call(val args, val kwargs) {
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

val Py::getattr(val idx) {
  PyObject *pyidx = jsToPython(idx);
  PyObject *attr = PyObject_GetAttr(x, pyidx);
  Py_DECREF(pyidx);
  if (attr == NULL) {
    return pythonExcToJs();
  }

  val ret = pythonToJs(attr);
  Py_DECREF(attr);
  return ret;
}

void Py::setattr(val idx, val v) {
  PyObject *pyidx = jsToPython(idx);
  PyObject *pyv = jsToPython(v);

  int ret = PyObject_SetAttr(x, pyidx, pyv);
  Py_DECREF(pyidx);
  Py_DECREF(pyv);
  if (ret) {
    pythonExcToJs();
  }
}

val Py::hasattr(val idx) {
  PyObject *pyidx = jsToPython(idx);
  val result(PyObject_HasAttr(x, pyidx) ? true : false);
  Py_DECREF(pyidx);
  return result;
}

val Py::getitem(val idx) {
  PyObject *pyidx = jsToPython(idx);
  PyObject *item = PyObject_GetItem(x, pyidx);
  Py_DECREF(pyidx);
  if (item == NULL) {
    return pythonExcToJs();
  }

  val ret = pythonToJs(item);
  Py_DECREF(item);
  return ret;
}

void Py::setitem(val idx, val v) {
  PyObject *pyidx = jsToPython(idx);
  PyObject *pyv = jsToPython(v);

  int ret = PyObject_SetItem(x, pyidx, pyv);
  Py_DECREF(pyidx);
  Py_DECREF(pyv);
  if (ret) {
    pythonExcToJs();
  }
}

val Py::hasitem(val idx) {
  PyObject *pyidx = jsToPython(idx);
  val result(PySequence_Contains(x, pyidx) ? true : false);
  Py_DECREF(pyidx);
  return result;
}
