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

static inline JsRef
_python2js_immutable(PyObject* x);

EM_JS_REF(JsRef, pyproxy_to_js_error, (JsRef pyproxy), {
  return Module.hiwire.new_value(
    new Module.PythonError(Module.hiwire.get_value(pyproxy)));
});

JsRef
wrap_exception()
{
  bool success = true;
  PyObject* type = NULL;
  PyObject* value = NULL;
  PyObject* traceback = NULL;
  JsRef pyexc_proxy = NULL;
  JsRef jserror = NULL;

  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);
  if (type == NULL || type == Py_None || value == NULL || value == Py_None) {
    PyErr_SetString(PyExc_TypeError, "No exception type or value");
    FAIL();
  }

  if (traceback == NULL) {
    traceback = Py_None;
    Py_INCREF(traceback);
  }
  PyException_SetTraceback(value, traceback);

  pyexc_proxy = pyproxy_new(value);
  jserror = pyproxy_to_js_error(pyexc_proxy);

  success = true;
finally:
  Py_CLEAR(type);
  Py_CLEAR(value);
  Py_CLEAR(traceback);
  hiwire_CLEAR(pyexc_proxy);
  if (!success) {
    hiwire_CLEAR(jserror);
  }
  return jserror;
}

void _Py_NO_RETURN
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
  FAIL_IF_NULL(excval);

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
  // hiwire_string_ascii never fails so excval is guaranteed not to be null at
  // this point. This throws an error making it pretty difficult to decref
  // excval, so hiwire_throw_error will decref it for us (in other words
  // hiwire_throw_error steals a reference to its argument).
  hiwire_throw_error(excval);
}

int
_python2js_add_to_cache(PyObject* map, PyObject* pyparent, JsRef jsparent);

JsRef
_python2js_cache(PyObject* x, PyObject* map, int depth);

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
      FAIL_IF_NULL(py_float);
      return _python2js_float(py_float);
    }
    FAIL_IF_ERR_OCCURRED();
  }
  return hiwire_int(x_long);
finally:
  return NULL;
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

/** WARNING: This function is not suitable for fallbacks. If this function
 * returns NULL, we must assume that the cache has been corrupted and bail out.
 */
static JsRef
_python2js_sequence(PyObject* x, PyObject* map, int depth)
{
  bool success = false;
  PyObject* pyitem = NULL;
  JsRef jsitem = NULL;
  // result:
  JsRef jsarray = NULL;

  jsarray = hiwire_array();
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(map, x, jsarray));
  Py_ssize_t length = PySequence_Size(x);
  FAIL_IF_MINUS_ONE(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    PyObject* pyitem = PySequence_GetItem(x, i);
    FAIL_IF_NULL(pyitem);
    FAIL_IF_NULL(jsitem = _python2js_cache(pyitem, map, depth));
    hiwire_push_array(jsarray, jsitem);
    Py_CLEAR(pyitem);
    hiwire_CLEAR(jsitem);
  }
  success = true;
finally:
  Py_CLEAR(pyitem);
  hiwire_CLEAR(jsitem);
  if (!success) {
    hiwire_CLEAR(jsarray);
  }
  return jsarray;
}

/** WARNING: This function is not suitable for fallbacks. If this function
 * returns NULL, we must assume that the cache has been corrupted and bail out.
 */
static JsRef
_python2js_dict(PyObject* x, PyObject* map, int depth)
{
  bool success = false;
  JsRef jskey = NULL;
  JsRef jsval = NULL;
  // result:
  JsRef jsdict = NULL;

  jsdict = JsMap_New();
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(map, x, jsdict));
  PyObject *pykey, *pyval;
  Py_ssize_t pos = 0;
  while (PyDict_Next(x, &pos, &pykey, &pyval)) {
    jskey = _python2js_immutable(pykey);
    if (jskey == NULL) {
      FAIL_IF_ERR_OCCURRED();
      PyErr_Format(
        conversion_error, "Cannot use %R as a key for a Javascript map", pykey);
      FAIL();
    }
    jsval = _python2js_cache(pyval, map, depth);
    FAIL_IF_NULL(jsval);
    FAIL_IF_MINUS_ONE(JsMap_Set(jsdict, jskey, jsval));
    hiwire_CLEAR(jskey);
    hiwire_CLEAR(jsval);
  }
  success = true;
finally:
  hiwire_CLEAR(jskey);
  hiwire_CLEAR(jsval);
  if (!success) {
    hiwire_CLEAR(jsdict);
  }
  return jsdict;
}

static JsRef
_python2js_set(PyObject* x, PyObject* map, int depth)
{
  bool success = false;
  bool cached = false;
  PyObject* iter = NULL;
  PyObject* pykey = NULL;
  JsRef jskey = NULL;
  // result:
  JsRef jsset = NULL;

  jsset = JsSet_New();
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(map, x, jsset));
  iter = PyObject_GetIter(x);
  FAIL_IF_NULL(iter);
  while ((pykey = PyIter_Next(iter))) {
    jskey = _python2js_immutable(pykey);
    if (jskey == NULL) {
      FAIL_IF_ERR_OCCURRED();
      PyErr_Format(
        conversion_error, "Cannot use %R as a key for a Javascript set", pykey);
      FAIL();
    }
    FAIL_IF_MINUS_ONE(JsSet_Add(jsset, jskey));
    Py_CLEAR(pykey);
    hiwire_CLEAR(jskey);
  }
  FAIL_IF_ERR_OCCURRED();

  success = true;
finally:
  Py_CLEAR(pykey);
  hiwire_CLEAR(jskey);
  if (!success) {
    hiwire_CLEAR(jsset);
  }
  return jsset;
}

#define RETURN_IF_SUCCEEDS(x)                                                  \
  do {                                                                         \
    JsRef _fresh_result = x;                                                   \
    if (_fresh_result != NULL) {                                               \
      return _fresh_result;                                                    \
    }                                                                          \
  } while (0)

static inline JsRef
_python2js_immutable(PyObject* x)
{
  if (x == Py_None) {
    return Js_undefined;
  } else if (x == Py_True) {
    return Js_true;
  } else if (x == Py_False) {
    return Js_false;
  } else if (PyLong_Check(x)) {
    return _python2js_long(x);
  } else if (PyFloat_Check(x)) {
    return _python2js_float(x);
  } else if (PyUnicode_Check(x)) {
    return _python2js_unicode(x);
  }
  return NULL;
}

static inline JsRef
_python2js_proxy(PyObject* x)
{
  if (JsProxy_Check(x)) {
    return JsProxy_AsJs(x);
  } else if (JsException_Check(x)) {
    return JsException_AsJs(x);
  }
  return NULL;
}

static JsRef
_python2js_deep(PyObject* x, PyObject* map, int depth)
{
  RETURN_IF_SUCCEEDS(_python2js_immutable(x));
  FAIL_IF_ERR_OCCURRED();
  RETURN_IF_SUCCEEDS(_python2js_proxy(x));
  FAIL_IF_ERR_OCCURRED();

  if (PyList_Check(x) || PyTuple_Check(x)) {
    return _python2js_sequence(x, map, depth);
  }
  if (PyDict_Check(x)) {
    return _python2js_dict(x, map, depth);
  }
  if (PySet_Check(x)) {
    return _python2js_set(x, map, depth);
  }
  RETURN_IF_SUCCEEDS(_python2js_buffer(x));
  PyErr_Clear();
  return pyproxy_new(x);
finally:
  return NULL;
}

static JsRef
_python2js(PyObject* x, PyObject* map, int depth)
{
  if (depth == 0) {
    return python2js(x);
  } else {
    return _python2js_deep(x, map, depth - 1);
  }
}

/* During conversion of collection types (lists and dicts) from Python to
 * Javascript, we need to make sure that those collections don't include
 * themselves, otherwise infinite recursion occurs. We also want to make sure
 * that if the list contains multiple copies of the same list that they point to
 * the same place. For after:
 *
 * a = list(range(10))
 * b = [a, a, a, a]
 *
 * We want to ensure that b.toJs()[0] is the same list as b.toJs()[1].
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
  int result = -1;
  PyObject* pyparentid = NULL;
  PyObject* jsparentid = NULL;

  pyparentid = PyLong_FromSize_t((size_t)pyparent);
  FAIL_IF_NULL(pyparentid);
  jsparent = hiwire_incref(jsparent);
  jsparentid = PyLong_FromLong((int)jsparent);
  FAIL_IF_NULL(jsparentid);
  result = PyDict_SetItem(map, pyparentid, jsparentid);

finally:
  Py_CLEAR(pyparentid);
  Py_CLEAR(jsparentid);
  return result;
}

int
_python2js_remove_from_cache(PyObject* map, PyObject* pyparent)
{
  int result = -1;
  PyObject* pyparentid = NULL;

  pyparentid = PyLong_FromSize_t((size_t)pyparent);
  FAIL_IF_NULL(pyparentid);
  result = PyDict_DelItem(map, pyparentid);

finally:
  Py_CLEAR(pyparentid);
  return result;
}

JsRef
_python2js_cache(PyObject* x, PyObject* map, int depth)
{
  PyObject* id = PyLong_FromSize_t((size_t)x);
  FAIL_IF_NULL(id);
  PyObject* val = PyDict_GetItem(map, id);
  Py_CLEAR(id);
  JsRef result;
  if (val) {
    result = (JsRef)PyLong_AsLong(val);
    if (result != NULL) {
      result = hiwire_incref(result);
    }
  } else {
    result = _python2js(x, map, depth);
  }
  return result;
finally:
  return NULL;
}

JsRef
python2js(PyObject* x)
{
  RETURN_IF_SUCCEEDS(_python2js_immutable(x));
  FAIL_IF_ERR_OCCURRED();
  RETURN_IF_SUCCEEDS(_python2js_proxy(x));
  FAIL_IF_ERR_OCCURRED();
  RETURN_IF_SUCCEEDS(pyproxy_new(x));
finally:
  if (PyErr_Occurred()) {
    if (!PyErr_ExceptionMatches(conversion_error)) {
      _PyErr_FormatFromCause(conversion_error,
                             "Conversion from python to javascript failed");
    }
  } else {
    PyErr_SetString(internal_error,
                    "Internal error occurred in python2js_with_depth");
  }
  return NULL;
}

JsRef
python2js_with_depth(PyObject* x, int depth)
{
  PyObject* map = PyDict_New();
  if (map == NULL) {
    return NULL;
  }
  JsRef result = _python2js_cache(x, map, depth);
  PyObject *pykey, *pyval;
  Py_ssize_t pos = 0;
  while (PyDict_Next(map, &pos, &pykey, &pyval)) {
    JsRef obj = (JsRef)PyLong_AsLong(pyval);
    hiwire_decref(obj);
  }
  Py_DECREF(map);
  if (result == NULL) {
    if (PyErr_Occurred()) {
      if (!PyErr_ExceptionMatches(conversion_error)) {
        _PyErr_FormatFromCause(conversion_error,
                               "Conversion from python to javascript failed");
      }
    } else {
      PyErr_SetString(internal_error,
                      "Internal error occurred in python2js_with_depth");
    }
  }
  return result;
}

int
python2js_init()
{
  bool success = false;
  EM_ASM({
    class PythonError extends Error
    {
      constructor(pythonError)
      {
        let message = "Python Error";
        super(message);
        this.name = this.constructor.name;
        this.pythonError = pythonError;
      }
    };
    Module.PythonError = PythonError;
  });

  tbmod = PyImport_ImportModule("traceback");
  FAIL_IF_NULL(tbmod);
  success = true;
finally:
  return success ? 0 : -1;
}
