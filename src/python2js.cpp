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

  if (type == NULL || type == Py_None ||
      value == NULL || value == Py_None) {
    excval = val("No exception type or value");
    PyErr_Print();
    PyErr_Clear();
    goto exit;
  }

  {
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
          PyErr_Clear();
          goto exit;
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
  }

 exit:
  val exc = val::global("Error").new_(excval);

  Py_XDECREF(type);
  Py_XDECREF(value);
  Py_XDECREF(traceback);

  PyErr_Clear();

  return exc;
}

static bool isTypeName(PyObject *x, const char *name) {
  PyObject *x_type = PyObject_Type(x);
  if (x_type == NULL) {
    // If we can't get a type, that's probably ok in this case...
    PyErr_Clear();
    return false;
  }

  PyObject *x_type_name = PyObject_Repr(x_type);
  Py_DECREF(x_type);

  bool result = (PyUnicode_CompareWithASCIIString(x_type_name, name) == 0);

  Py_DECREF(x_type_name);
  return result;
}

val pythonToJs(PyObject *x) {

  if (PyBytes_Check(x)) {
    char *x_buff;
    Py_ssize_t length;
    PyBytes_AsStringAndSize(x, &x_buff, &length);
    return val::global("Uint8ClampedArray").new_(
                                                 val(emscripten::typed_memory_view(length, (unsigned char *)x_buff)));
  } else if (x == Py_None) {
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
  } else if (JsProxy_Check(x)) {
    return JsProxy_AsVal(x);
  } else if (PyList_Check(x) || isTypeName(x, "<class 'numpy.ndarray'>")) {
    val array = val::global("Array");
    val x_array = array.new_();
    size_t length = PySequence_Size(x);
    for (size_t i = 0; i < length; ++i) {
      PyObject *item = PySequence_GetItem(x, i);
      if (item == NULL) {
        // If something goes wrong converting the sequence (as is the case with
        // Pandas data frames), fallback to the Python object proxy
        PyErr_Clear();
        return Py::makeProxy(x);
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
  } else if (PyCallable_Check(x)) {
    return PyCallable::makeCallableProxy(x);
  } else {
    return Py::makeProxy(x);
  }
}

int pythonToJs_Ready() {
  undefined = new val(val::global("undefined"));
  return 0;
}
