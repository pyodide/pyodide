#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "hiwire.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include "python2js.h"
#include <emscripten.h>

#include "python2js_buffer.h"

static PyObject* tbmod = NULL;

_Py_IDENTIFIER(format_exception);

static JsRef
_python2js_unicode(PyObject* x);

void
pythonexc2js()
{
  bool success = false;
  PyObject* type = NULL;
  PyObject* value = NULL;
  PyObject* traceback = NULL;
  JsRef excval = NULL;
  PyObject* pylines = NULL;
  PyObject* empty = NULL;
  PyObject* pystr = NULL;

  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);

  if (type == NULL || type == Py_None || value == NULL || value == Py_None) {
    excval = hiwire_string_ascii("No exception type or value");
    PySys_WriteStderr("No exception type or value\n");
    goto finally__skip_print_tb;
    return;
  }

  if (traceback == NULL) {
    traceback = Py_None;
    Py_INCREF(traceback);
  }

  pylines = _PyObject_CallMethodIdObjArgs(
    tbmod, &PyId_format_exception, type, value, traceback, NULL);
  FAIL_IF_NULL(pylines);
  empty = PyUnicode_New(0, 0);
  FAIL_IF_NULL(empty);
  pystr = PyUnicode_Join(empty, pylines);
  FAIL_IF_NULL(pystr);
  const char* pystr_utf8 = PyUnicode_AsUTF8(pystr);
  FAIL_IF_NULL(pystr_utf8);
  PySys_WriteStderr("Python exception:\n");
  PySys_WriteStderr("%s\n", pystr_utf8);
  excval = _python2js_unicode(pystr);

  success = true;
finally:
  if (!success) {
    excval = hiwire_string_ascii("Error occurred while formatting traceback");
    PySys_WriteStderr("Error occurred while formatting traceback:\n");
    PyErr_Print();
    PySys_WriteStderr("\nOriginal exception was:\n");
    PyErr_Display(type, value, traceback);
  }
finally__skip_print_tb:
  Py_CLEAR(type);
  Py_CLEAR(value);
  Py_CLEAR(traceback);
  Py_CLEAR(pylines);
  Py_CLEAR(empty);
  Py_CLEAR(pystr);
  if (excval != NULL) {
    // this throws an error making it pretty difficult to decref excval.
    // hiwire_throw_error will decref it for us (so it steals a reference to its
    // argument).
    hiwire_throw_error(excval);
  } else {
    // In this case there will be an error in the calling code, calling code
    // currently expects us to throw no matter what.
    PySys_WriteStderr("Internal error: failed to generate exception!\n");
  }
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
    return NULL;
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
        return NULL;
      }
      return _python2js_float(py_float);
    } else if (PyErr_Occurred()) {
      return NULL;
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
      return NULL;
  }
}

static JsRef
_python2js_bytes(PyObject* x)
{
  char* x_buff;
  Py_ssize_t length;
  if (PyBytes_AsStringAndSize(x, &x_buff, &length)) {
    return NULL;
  }
  return hiwire_bytes(x_buff, length);
}

static JsRef
_python2js_sequence(PyObject* x, PyObject* map)
{
  JsRef jsarray = hiwire_array();
  if (_python2js_add_to_cache(map, x, jsarray)) {
    hiwire_decref(jsarray);
    return NULL;
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
    if (jsitem == NULL) {
      _python2js_remove_from_cache(map, x);
      Py_DECREF(pyitem);
      hiwire_decref(jsarray);
      return NULL;
    }
    Py_DECREF(pyitem);
    hiwire_push_array(jsarray, jsitem);
    hiwire_decref(jsitem);
  }
  if (_python2js_remove_from_cache(map, x)) {
    hiwire_decref(jsarray);
    return NULL;
  }
  return jsarray;
}

static JsRef
_python2js_dict(PyObject* x, PyObject* map)
{
  JsRef jsdict = hiwire_object();
  if (_python2js_add_to_cache(map, x, jsdict)) {
    hiwire_decref(jsdict);
    return NULL;
  }
  PyObject *pykey, *pyval;
  Py_ssize_t pos = 0;
  while (PyDict_Next(x, &pos, &pykey, &pyval)) {
    JsRef jskey = _python2js_cache(pykey, map);
    if (jskey == NULL) {
      _python2js_remove_from_cache(map, x);
      hiwire_decref(jsdict);
      return NULL;
    }
    JsRef jsval = _python2js_cache(pyval, map);
    if (jsval == NULL) {
      _python2js_remove_from_cache(map, x);
      hiwire_decref(jskey);
      hiwire_decref(jsdict);
      return NULL;
    }
    hiwire_push_object_pair(jsdict, jskey, jsval);
    hiwire_decref(jskey);
    hiwire_decref(jsval);
  }
  if (_python2js_remove_from_cache(map, x)) {
    hiwire_decref(jsdict);
    return NULL;
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

    if (ret != NULL) {
      return ret;
    }
    PyErr_Clear();
    if (PySequence_Check(x)) {
      return _python2js_sequence(x, map);
    }

    // Proxies we've already created are just returned again, so that the
    // same object on the Python side is always the same object on the
    // Javascript side.
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
    if (result != NULL) {
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

  if (result == NULL) {
    pythonexc2js();
  }

  return result;
}

int
python2js_init()
{
  bool success = false;
  tbmod = PyImport_ImportModule("traceback");
  FAIL_IF_NULL(tbmod);
  success = true;
finally:
  return success ? 0 : -1;
}
