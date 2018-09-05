#include "python2js.h"

#include <emscripten.h>

#include "hiwire.h"
#include "jsproxy.h"
#include "pyproxy.h"

int
pythonexc2js()
{
  PyObject* type;
  PyObject* value;
  PyObject* traceback;
  int no_traceback = 0;

  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);

  int excval = -1;
  int exc;

  if (type == NULL || type == Py_None || value == NULL || value == Py_None) {
    excval = hiwire_string_utf8((int)"No exception type or value");
    PyErr_Print();
    PyErr_Clear();
    goto exit;
  }

  PyObject* tbmod = PyImport_ImportModule("traceback");
  if (tbmod == NULL) {
    PyObject* repr = PyObject_Repr(value);
    if (repr == NULL) {
      excval = hiwire_string_utf8((int)"Could not get repr for exception");
    } else {
      excval = python2js(repr);
      Py_DECREF(repr);
    }
  } else {
    PyObject* format_exception;
    if (traceback == NULL || traceback == Py_None) {
      no_traceback = 1;
      format_exception = PyObject_GetAttrString(tbmod, "format_exception_only");
    } else {
      format_exception = PyObject_GetAttrString(tbmod, "format_exception");
    }
    if (format_exception == NULL) {
      excval =
        hiwire_string_utf8((int)"Could not get format_exception function");
    } else {
      PyObject* pylines;
      if (no_traceback) {
        pylines =
          PyObject_CallFunctionObjArgs(format_exception, type, value, NULL);
      } else {
        pylines = PyObject_CallFunctionObjArgs(
          format_exception, type, value, traceback, NULL);
      }
      if (pylines == NULL) {
        excval =
          hiwire_string_utf8((int)"Error calling traceback.format_exception");
        PyErr_Print();
        PyErr_Clear();
        goto exit;
      } else {
        PyObject* newline = PyUnicode_FromString("");
        PyObject* pystr = PyUnicode_Join(newline, pylines);
        printf("Python exception:\n");
        printf("%s\n", PyUnicode_AsUTF8(pystr));
        excval = python2js(pystr);
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

static int
is_type_name(PyObject* x, const char* name)
{
  PyObject* x_type = PyObject_Type(x);
  if (x_type == NULL) {
    // If we can't get a type, that's probably ok in this case...
    PyErr_Clear();
    return 0;
  }

  PyObject* x_type_name = PyObject_Repr(x_type);
  Py_DECREF(x_type);

  int result = (PyUnicode_CompareWithASCIIString(x_type_name, name) == 0);

  Py_DECREF(x_type_name);
  return result;
}

static int
_python2js(PyObject* x)
{
  if (x == Py_None) {
    return hiwire_undefined();
  } else if (x == Py_True) {
    return hiwire_true();
  } else if (x == Py_False) {
    return hiwire_false();
  } else if (PyLong_Check(x)) {
    long x_long = PyLong_AsLongLong(x);
    if (x_long == -1 && PyErr_Occurred()) {
      return -1;
    }
    return hiwire_int(x_long);
  } else if (PyFloat_Check(x)) {
    double x_double = PyFloat_AsDouble(x);
    if (x_double == -1.0 && PyErr_Occurred()) {
      return -1;
    }
    return hiwire_double(x_double);
  } else if (PyUnicode_Check(x)) {
    int kind = PyUnicode_KIND(x);
    int data = (int)PyUnicode_DATA(x);
    int length = (int)PyUnicode_GET_LENGTH(x);
    switch (kind) {
      case PyUnicode_1BYTE_KIND:
        return hiwire_string_ucs1(data, length);
      case PyUnicode_2BYTE_KIND:
        return hiwire_string_ucs2(data, length);
      case PyUnicode_4BYTE_KIND:
        return hiwire_string_ucs4(data, length);
      default:
        PyErr_SetString(PyExc_ValueError, "Unknown Unicode KIND");
        return -1;
    }
  } else if (PyBytes_Check(x)) {
    char* x_buff;
    Py_ssize_t length;
    if (PyBytes_AsStringAndSize(x, &x_buff, &length)) {
      return -1;
    }
    return hiwire_bytes((int)(void*)x_buff, length);
  } else if (JsProxy_Check(x)) {
    return JsProxy_AsJs(x);
  } else if (PyList_Check(x) || is_type_name(x, "<class 'numpy.ndarray'>")) {
    int jsarray = hiwire_array();
    size_t length = PySequence_Size(x);
    for (size_t i = 0; i < length; ++i) {
      PyObject* pyitem = PySequence_GetItem(x, i);
      if (pyitem == NULL) {
        // If something goes wrong converting the sequence (as is the case with
        // Pandas data frames), fallback to the Python object proxy
        hiwire_decref(jsarray);
        PyErr_Clear();
        Py_INCREF(x);
        return pyproxy_new((int)x);
      }
      int jsitem = _python2js(pyitem);
      if (jsitem == -1) {
        Py_DECREF(pyitem);
        hiwire_decref(jsarray);
        return -1;
      }
      Py_DECREF(pyitem);
      hiwire_push_array(jsarray, jsitem);
      hiwire_decref(jsitem);
    }
    return jsarray;
  } else if (PyDict_Check(x)) {
    int jsdict = hiwire_object();
    PyObject *pykey, *pyval;
    Py_ssize_t pos = 0;
    while (PyDict_Next(x, &pos, &pykey, &pyval)) {
      int jskey = _python2js(pykey);
      if (jskey == -1) {
        hiwire_decref(jsdict);
        return -1;
      }
      int jsval = _python2js(pyval);
      if (jsval == -1) {
        hiwire_decref(jskey);
        hiwire_decref(jsdict);
        return -1;
      }
      hiwire_push_object_pair(jsdict, jskey, jsval);
      hiwire_decref(jskey);
      hiwire_decref(jsval);
    }
    return jsdict;
  } else {
    Py_INCREF(x);
    return pyproxy_new((int)x);
  }
}

int
python2js(PyObject* x)
{
  int result = _python2js(x);
  if (result == -1) {
    return pythonexc2js();
  }
  return result;
}

int
python2js_init()
{
  return 0;
}
