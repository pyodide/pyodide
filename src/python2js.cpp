#include "python2js.hpp"
#include "jsproxy.hpp"
#include "pyproxy.hpp"

using emscripten::val;

static val *undefined;

val pythonExcToJs() {
  PyObject *type;
  PyObject *value;
  PyObject *traceback;
  bool no_traceback = false;

  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);

  val excval("");

  PyObject *tbmod = PyImport_ImportModule("traceback");
  if (tbmod == NULL) {
    excval = pythonToJs(PyObject_Repr(value));
  } else {
    PyObject *format_exception;
    if (traceback == NULL || traceback == Py_None) {
      no_traceback = true;
      format_exception = PyObject_GetAttrString(tbmod, "format_exception_only");
    } else {
      format_exception = PyObject_GetAttrString(tbmod, "format_exception");
    }
    if (format_exception == NULL) {
      excval = val("Couldn't get format_exception function");
    } else {
      PyObject *pylines;
      if (no_traceback) {
        pylines = PyObject_CallFunctionObjArgs
          (format_exception, type, value, NULL);
      } else {
        pylines = PyObject_CallFunctionObjArgs
          (format_exception, type, value, traceback, NULL);
      }
      if (pylines == NULL) {
        excval = val("Error calling traceback.format_exception");
        PyErr_Print();
      } else {
        PyObject *newline = PyUnicode_FromString("\n");
        PyObject *pystr = PyUnicode_Join(newline, pylines);
        PyObject_Print(pystr, stderr, 0);
        excval = pythonToJs(pystr);
        Py_DECREF(pystr);
        Py_DECREF(newline);
        Py_DECREF(pylines);
      }
      Py_DECREF(format_exception);
    }
    Py_DECREF(tbmod);
  }

  val exc = val::global("Error").new_(excval);

  Py_DECREF(type);
  Py_DECREF(value);
  Py_XDECREF(traceback);

  PyErr_Clear();

  return exc;
}

val pythonToJs(PyObject *x) {
  // TODO: bool, None
  if (x == Py_None) {
    return val(*undefined);
  } else if (x == Py_True) {
    return val(true);
  } else if (x == Py_False) {
    return val(false);
  } else if (PyLong_Check(x)) {
    long x_long = PyLong_AsLongLong(x);
    if (x_long == -1 && PyErr_Occurred()) {
      return pythonExcToJs();
    }
    return val(x_long);
  } else if (PyFloat_Check(x)) {
    double x_double = PyFloat_AsDouble(x);
    if (x_double == -1.0 && PyErr_Occurred()) {
      return pythonExcToJs();
    }
    return val(x_double);
  } else if (PyUnicode_Check(x)) {
    // TODO: Not clear whether this is UTF-16 or UCS2
    // TODO: This is doing two copies.  Can we reduce?
    Py_ssize_t length;
    wchar_t *chars = PyUnicode_AsWideCharString(x, &length);
    if (chars == NULL) {
      return pythonExcToJs();
    }
    std::wstring x_str(chars, length);
    PyMem_Free(chars);
    return val(x_str);
  } else if (PyBytes_Check(x)) {
    // TODO: This is doing two copies.  Can we reduce?
    char *x_buff;
    Py_ssize_t length;
    PyBytes_AsStringAndSize(x, &x_buff, &length);
    std::string x_str(x_buff, length);
    return val(x_str);
  } else if (JsProxy_Check(x)) {
    return JsProxy_AsVal(x);
  } else if (PySequence_Check(x)) {
    val array = val::global("Array");
    val x_array = array.new_();
    size_t length = PySequence_Size(x);
    for (size_t i = 0; i < length; ++i) {
      PyObject *item = PySequence_GetItem(x, i);
      if (item == NULL) {
        return pythonExcToJs();
      }
      x_array.call<int>("push", pythonToJs(item));
      Py_DECREF(item);
    }
    return x_array;
  } else if (PyDict_Check(x)) {
    val object = val::global("Object");
    val x_object = object.new_();
    PyObject *k, *v;
    Py_ssize_t pos = 0;
    while (PyDict_Next(x, &pos, &k, &v)) {
      x_object.set(pythonToJs(k), pythonToJs(v));
    }
    return x_object;
  } else {
    return val(Py(x));
  }
}

int pythonToJs_Ready() {
  undefined = new val(val::global("undefined"));
  return 0;
}
