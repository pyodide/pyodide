#include "python2js.h"

#include <emscripten.h>

#include "hiwire.h"
#include "jsproxy.h"
#include "pyproxy.h"

#include "python2js_buffer.h"

static PyObject* tbmod = NULL;

static JsRef
_python2js_unicode(PyObject* x);

void
pythonexc2js()
{
  PyObject* type;
  PyObject* value;
  PyObject* traceback;
  int no_traceback = 0;

  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);

  JsRef excval = Js_ERROR;
  int exc;

  if (type == NULL || type == Py_None || value == NULL || value == Py_None) {
    excval = hiwire_string_ascii("No exception type or value");
    PyErr_Print();
    PyErr_Clear();
    goto exit;
  }

  if (tbmod == NULL) {
    tbmod = PyImport_ImportModule("traceback");
    if (tbmod == NULL) {
      PyObject* repr = PyObject_Repr(value);
      if (repr == NULL) {
        excval = hiwire_string_ascii("Could not get repr for exception");
      } else {
        excval = _python2js_unicode(repr);
        Py_DECREF(repr);
      }
      goto exit;
    }
  }

  PyObject* format_exception;
  if (traceback == NULL || traceback == Py_None) {
    no_traceback = 1;
    format_exception = PyObject_GetAttrString(tbmod, "format_exception_only");
  } else {
    format_exception = PyObject_GetAttrString(tbmod, "format_exception");
  }
  if (format_exception == NULL) {
    excval = hiwire_string_ascii("Could not get format_exception function");
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
      excval = hiwire_string_ascii("Error calling traceback.format_exception");
      PyErr_Print();
      PyErr_Clear();
      goto exit;
    } else {
      PyObject* empty = PyUnicode_FromString("");
      PyObject* pystr = PyUnicode_Join(empty, pylines);
      printf("Python exception:\n");
      printf("%s\n", PyUnicode_AsUTF8(pystr));
      excval = _python2js_unicode(pystr);
      Py_DECREF(pystr);
      Py_DECREF(empty);
      Py_DECREF(pylines);
    }
    Py_DECREF(format_exception);
  }

exit:
  PyErr_Clear();
  hiwire_throw_error(excval);
}

int
_python2js_add_to_cache(PyObject* map, PyObject* pyparent, JsRef jsparent);

int
_python2js_remove_from_cache(PyObject* map, PyObject* pyparent);

JsRef
_python2js_cache(PyObject* x, PyObject* map);

static JsRef
_python2js_float(PyObject* x)
{
  double x_double = PyFloat_AsDouble(x);
  if (x_double == -1.0 && PyErr_Occurred()) {
    return Js_ERROR;
  }
  return hiwire_double(x_double);
}

static JsRef
_python2js_long(PyObject* x)
{
  int overflow;
  long x_long = PyLong_AsLongAndOverflow(x, &overflow);
  if (x_long == -1) {
    if (overflow) {
      PyObject* py_float = PyNumber_Float(x);
      if (py_float == NULL) {
        return Js_ERROR;
      }
      return _python2js_float(py_float);
    } else if (PyErr_Occurred()) {
      return Js_ERROR;
    }
  }
  return hiwire_int(x_long);
}

static JsRef
_python2js_unicode(PyObject* x)
{
  int kind = PyUnicode_KIND(x);
  char* data = (char*)PyUnicode_DATA(x);
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
      return Js_ERROR;
  }
}

static JsRef
_python2js_bytes(PyObject* x)
{
  char* x_buff;
  Py_ssize_t length;
  if (PyBytes_AsStringAndSize(x, &x_buff, &length)) {
    return Js_ERROR;
  }
  return hiwire_bytes(x_buff, length);
}

static JsRef
_python2js_sequence(PyObject* x, PyObject* map)
{
  JsRef jsarray = hiwire_array();
  if (_python2js_add_to_cache(map, x, jsarray)) {
    hiwire_decref(jsarray);
    return Js_ERROR;
  }
  size_t length = PySequence_Size(x);
  for (size_t i = 0; i < length; ++i) {
    PyObject* pyitem = PySequence_GetItem(x, i);
    if (pyitem == NULL) {
      // If something goes wrong converting the sequence (as is the case with
      // Pandas data frames), fallback to the Python object proxy
      _python2js_remove_from_cache(map, x);
      hiwire_decref(jsarray);
      PyErr_Clear();
      Py_INCREF(x);
      return pyproxy_new(x);
    }
    JsRef jsitem = _python2js_cache(pyitem, map);
    if (jsitem == Js_ERROR) {
      _python2js_remove_from_cache(map, x);
      Py_DECREF(pyitem);
      hiwire_decref(jsarray);
      return Js_ERROR;
    }
    Py_DECREF(pyitem);
    hiwire_push_array(jsarray, jsitem);
    hiwire_decref(jsitem);
  }
  if (_python2js_remove_from_cache(map, x)) {
    hiwire_decref(jsarray);
    return Js_ERROR;
  }
  return jsarray;
}

static JsRef
_python2js_dict(PyObject* x, PyObject* map)
{
  JsRef jsdict = hiwire_object();
  if (_python2js_add_to_cache(map, x, jsdict)) {
    hiwire_decref(jsdict);
    return Js_ERROR;
  }
  PyObject *pykey, *pyval;
  Py_ssize_t pos = 0;
  while (PyDict_Next(x, &pos, &pykey, &pyval)) {
    JsRef jskey = _python2js_cache(pykey, map);
    if (jskey == Js_ERROR) {
      _python2js_remove_from_cache(map, x);
      hiwire_decref(jsdict);
      return Js_ERROR;
    }
    JsRef jsval = _python2js_cache(pyval, map);
    if (jsval == Js_ERROR) {
      _python2js_remove_from_cache(map, x);
      hiwire_decref(jskey);
      hiwire_decref(jsdict);
      return Js_ERROR;
    }
    hiwire_push_object_pair(jsdict, jskey, jsval);
    hiwire_decref(jskey);
    hiwire_decref(jsval);
  }
  if (_python2js_remove_from_cache(map, x)) {
    hiwire_decref(jsdict);
    return Js_ERROR;
  }
  return jsdict;
}

static JsRef
_python2js(PyObject* x, PyObject* map)
{
  if (x == Py_None) {
    return hiwire_undefined();
  } else if (x == Py_True) {
    return hiwire_true();
  } else if (x == Py_False) {
    return hiwire_false();
  } else if (PyLong_Check(x)) {
    return _python2js_long(x);
  } else if (PyFloat_Check(x)) {
    return _python2js_float(x);
  } else if (PyUnicode_Check(x)) {
    return _python2js_unicode(x);
  } else if (PyBytes_Check(x)) {
    return _python2js_bytes(x);
  } else if (JsProxy_Check(x)) {
    return JsProxy_AsJs(x);
  } else if (JsException_Check(x)) {
    return JsException_AsJs(x);
  } else if (PyList_Check(x) || PyTuple_Check(x)) {
    return _python2js_sequence(x, map);
  } else if (PyDict_Check(x)) {
    return _python2js_dict(x, map);
  } else {
    JsRef ret = _python2js_buffer(x);

    if (ret != Js_ERROR) {
      return ret;
    }
    if (PySequence_Check(x)) {
      return _python2js_sequence(x, map);
    }

    // Proxies we've already created are just returned again, so that the
    // same object on the Python side is always the same object on the
    // Javascript side.
    ret = pyproxy_use(x);
    if (ret != Js_ERROR) {
      return ret;
    }

    // Reference counter is increased only once when a PyProxy is created.
    Py_INCREF(x);
    return pyproxy_new(x);
  }
}

/* During conversion of collection types (lists and dicts) from Python to
 * Javascript, we need to make sure that those collections don't include
 * themselves, otherwise infinite recursion occurs.
 *
 * The solution is to maintain a cache mapping from the PyObject* to the
 * Javascript object id for all collection objects. (One could do this for
 * scalars as well, but that would imply a larger cache, and identical scalars
 * are probably interned for deduplication on the Javascript side anyway).
 *
 * This cache only lives for each invocation of python2js.
 */

int
_python2js_add_to_cache(PyObject* map, PyObject* pyparent, JsRef jsparent)
{
  /* Use the pointer converted to an int so cache is by identity, not hash */
  PyObject* pyparentid = PyLong_FromSize_t((size_t)pyparent);
  PyObject* jsparentid = PyLong_FromLong((int)jsparent);
  int result = PyDict_SetItem(map, pyparentid, jsparentid);
  Py_DECREF(pyparentid);
  Py_DECREF(jsparentid);

  return result;
}

int
_python2js_remove_from_cache(PyObject* map, PyObject* pyparent)
{
  PyObject* pyparentid = PyLong_FromSize_t((size_t)pyparent);
  int result = PyDict_DelItem(map, pyparentid);
  Py_DECREF(pyparentid);

  return result;
}

JsRef
_python2js_cache(PyObject* x, PyObject* map)
{
  PyObject* id = PyLong_FromSize_t((size_t)x);
  PyObject* val = PyDict_GetItem(map, id);
  JsRef result;
  if (val) {
    result = (JsRef)PyLong_AsLong(val);
    if (result != Js_ERROR) {
      result = hiwire_incref(result);
    }
  } else {
    result = _python2js(x, map);
  }
  Py_DECREF(id);
  return result;
}

JsRef
python2js(PyObject* x)
{
  PyObject* map = PyDict_New();
  JsRef result = _python2js_cache(x, map);
  Py_DECREF(map);

  if (result == Js_ERROR) {
    pythonexc2js();
  }

  return result;
}

int
python2js_init()
{
  return 0;
}
