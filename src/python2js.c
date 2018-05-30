#include "python2js.h"

#include <emscripten.h>

#include "hiwire.h"
#include "jsproxy.h"
#include "pyproxy.h"

int pythonExcToJs() {
  PyObject *type;
  PyObject *value;
  PyObject *traceback;
  int no_traceback = 0;

  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);

  int excval = -1;
  int exc;

  if (type == NULL || type == Py_None ||
      value == NULL || value == Py_None) {
    excval = hiwire_string_utf8((int)"No exception type or value");
    PyErr_Print();
    PyErr_Clear();
    goto exit;
  }

  PyObject *tbmod = PyImport_ImportModule("traceback");
  if (tbmod == NULL) {
    PyObject *repr = PyObject_Repr(value);
    if (repr == NULL) {
      excval = hiwire_string_utf8((int)"Could not get repr for exception");
    } else {
      excval = pythonToJs(repr);
      Py_DECREF(repr);
    }
  } else {
    PyObject *format_exception;
    if (traceback == NULL || traceback == Py_None) {
      no_traceback = 1;
      format_exception = PyObject_GetAttrString(tbmod, "format_exception_only");
    } else {
      format_exception = PyObject_GetAttrString(tbmod, "format_exception");
    }
    if (format_exception == NULL) {
      excval = hiwire_string_utf8((int)"Could not get format_exception function");
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
        excval = hiwire_string_utf8((int)"Error calling traceback.format_exception");
        PyErr_Print();
        PyErr_Clear();
        goto exit;
      } else {
        PyObject *newline = PyUnicode_FromString("");
        PyObject *pystr = PyUnicode_Join(newline, pylines);
        printf("Python exception:\n");
        printf("%s\n", PyUnicode_AsUTF8(pystr));
        excval = pythonToJs(pystr);
        Py_DECREF(pystr);
        Py_DECREF(newline);
        Py_DECREF(pylines);
      }
      Py_DECREF(format_exception);
    }
    Py_DECREF(tbmod);
  }

 exit:
  Py_XDECREF(type);
  Py_XDECREF(value);
  Py_XDECREF(traceback);

  PyErr_Clear();

  hiwire_throw_error(excval);

  return -1;
}

static int isTypeName(PyObject *x, const char *name) {
  PyObject *x_type = PyObject_Type(x);
  if (x_type == NULL) {
    // If we can't get a type, that's probably ok in this case...
    PyErr_Clear();
    return 0;
  }

  PyObject *x_type_name = PyObject_Repr(x_type);
  Py_DECREF(x_type);

  int result = (PyUnicode_CompareWithASCIIString(x_type_name, name) == 0);

  Py_DECREF(x_type_name);
  return result;
}

int pythonToJs(PyObject *x) {
  if (x == Py_None) {
    return hiwire_undefined();
  } else if (x == Py_True) {
    return hiwire_true();
  } else if (x == Py_False) {
    return hiwire_false();
  } else if (PyLong_Check(x)) {
    long x_long = PyLong_AsLongLong(x);
    if (x_long == -1 && PyErr_Occurred()) {
      return pythonExcToJs();
    }
    return hiwire_int(x_long);
  } else if (PyFloat_Check(x)) {
    double x_double = PyFloat_AsDouble(x);
    if (x_double == -1.0 && PyErr_Occurred()) {
      return pythonExcToJs();
    }
    return hiwire_double(x_double);
  } else if (PyUnicode_Check(x)) {
    Py_ssize_t length;
    char *chars = PyUnicode_AsUTF8AndSize(x, &length);
    if (chars == NULL) {
      return pythonExcToJs();
    }
    return hiwire_string_utf8_length((int)(void *)chars, length);
  } else if (PyBytes_Check(x)) {
    char *x_buff;
    Py_ssize_t length;
    if (PyBytes_AsStringAndSize(x, &x_buff, &length)) {
      return pythonExcToJs();
    }
    return hiwire_bytes((int)(void *)x_buff, length);
  } else if (JsProxy_Check(x)) {
    return JsProxy_AsJs(x);
  } else if (PyList_Check(x) || isTypeName(x, "<class 'numpy.ndarray'>")) {
    int jsarray = hiwire_array();
    size_t length = PySequence_Size(x);
    for (size_t i = 0; i < length; ++i) {
      PyObject *item = PySequence_GetItem(x, i);
      if (item == NULL) {
        // If something goes wrong converting the sequence (as is the case with
        // Pandas data frames), fallback to the Python object proxy
        hiwire_decref(jsarray);
        PyErr_Clear();
        Py_INCREF(x);
        return pyproxy_new((int)x);
      }
      int jsitem = pythonToJs(item);
      if (jsitem == -1) {
        Py_DECREF(item);
        hiwire_decref(jsarray);
        return pythonExcToJs();
      }
      Py_DECREF(item);
      hiwire_push_array(jsarray, jsitem);
    }
    return jsarray;
  } else if (PyDict_Check(x)) {
    int jsdict = hiwire_object();
    PyObject *k, *v;
    Py_ssize_t pos = 0;
    while (PyDict_Next(x, &pos, &k, &v)) {
      int jsk = pythonToJs(k);
      if (jsk == -1) {
        hiwire_decref(jsdict);
        // TODO: Return a proxy instead here???
        return pythonExcToJs();
      }
      int jsv = pythonToJs(v);
      if (jsv == -1) {
        // TODO: Return a proxy instead here???
        hiwire_decref(jsk);
        hiwire_decref(jsdict);
        return pythonExcToJs();
      }
      hiwire_push_object_pair(jsdict, jsk, jsv);
    }
    return jsdict;
  } else {
    Py_INCREF(x);
    return pyproxy_new((int)x);
  }
}

int pythonToJs_Ready() {
  return 0;
}
