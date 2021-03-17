#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "hiwire.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include "python2js.h"
#include <emscripten.h>

#include "python2js_buffer.h"

static JsRef
_python2js_unicode(PyObject* x);

static inline JsRef
_python2js_immutable(PyObject* x);

int
_python2js_add_to_cache(PyObject* cache, PyObject* pyparent, JsRef jsparent);

JsRef
_python2js(PyObject* x, PyObject* cache, int depth);

///////////////////////////////////////////////////////////////////////////////
//
// Simple Converters
//
// These convert float, int, and unicode types. Used by python2js_immutable
// (which also handles bool and None).

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

// TODO: Should we use this in explicit conversions?
static JsRef
_python2js_bytes(PyObject* x)
{
  char* x_buff;
  Py_ssize_t length;
  if (PyBytes_AsStringAndSize(x, &x_buff, &length)) {
    return NULL;
  }
  return (JsRef)EM_ASM_INT(
    { return Module.hiwire.new_value(HEAP8.slice($0, $0 + $1)) }, x, length);
}

///////////////////////////////////////////////////////////////////////////////
//
// Container Converters
//
// These convert list, dict, and set types. We only convert objects that
// subclass list, dict, or set.
//
// One might consider trying to convert things that satisfy PyMapping_Check to
// maps and things that satisfy PySequence_Check to lists. However
// PyMapping_Check "returns 1 for Python classes with a __getitem__() method"
// and PySequence_Check returns 1 for classes with a __getitem__ method that
// don't subclass dict. For this reason, I think we should stick to subclasses.

/**
 * WARNING: This function is not suitable for fallbacks. If this function
 * returns NULL, we must assume that the cache has been corrupted and bail out.
 */
static JsRef
_python2js_sequence(PyObject* x, PyObject* cache, int depth)
{
  bool success = false;
  PyObject* pyitem = NULL;
  JsRef jsitem = NULL;
  // result:
  JsRef jsarray = NULL;

  jsarray = hiwire_array();
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(cache, x, jsarray));
  Py_ssize_t length = PySequence_Size(x);
  FAIL_IF_MINUS_ONE(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    PyObject* pyitem = PySequence_GetItem(x, i);
    FAIL_IF_NULL(pyitem);
    jsitem = _python2js(pyitem, cache, depth);
    FAIL_IF_NULL(jsitem);
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

/**
 * WARNING: This function is not suitable for fallbacks. If this function
 * returns NULL, we must assume that the cache has been corrupted and bail out.
 */
static JsRef
_python2js_dict(PyObject* x, PyObject* cache, int depth)
{
  bool success = false;
  JsRef jskey = NULL;
  JsRef jsval = NULL;
  // result:
  JsRef jsdict = NULL;

  jsdict = JsMap_New();
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(cache, x, jsdict));
  PyObject *pykey, *pyval;
  Py_ssize_t pos = 0;
  while (PyDict_Next(x, &pos, &pykey, &pyval)) {
    jskey = _python2js_immutable(pykey);
    if (jskey == NULL) {
      FAIL_IF_ERR_OCCURRED();
      PyErr_Format(
        conversion_error, "Cannot use %R as a key for a Javascript Map", pykey);
      FAIL();
    }
    jsval = _python2js(pyval, cache, depth);
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

/**
 * Note that this is not really a deep conversion because we refuse to convert
 * sets that contain e.g., tuples. This will only succeed if the sets only
 * contain basic types. This is a bit restrictive, but hopefully will be useful
 * anyways.
 *
 * This function can be used with fallbacks but currently isn't (we
 * just abort the entire conversion and throw an error if we encounter a set we
 * can't convert).
 */
static JsRef
_python2js_set(PyObject* x, PyObject* cache, int depth)
{
  bool success = false;
  PyObject* iter = NULL;
  PyObject* pykey = NULL;
  JsRef jskey = NULL;
  // result:
  JsRef jsset = NULL;

  jsset = JsSet_New();
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
  // Because we only convert immutable keys, we can do this here.
  // Otherwise, we'd fail on the set that contains itself.
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(cache, x, jsset));
  success = true;
finally:
  Py_CLEAR(pykey);
  hiwire_CLEAR(jskey);
  if (!success) {
    hiwire_CLEAR(jsset);
  }
  return jsset;
}

/**
 * Return x if x is not NULL.
 */
#define RETURN_IF_SUCCEEDS(x)                                                  \
  do {                                                                         \
    JsRef _fresh_result = x;                                                   \
    if (_fresh_result != NULL) {                                               \
      return _fresh_result;                                                    \
    }                                                                          \
  } while (0)

/**
 * Convert x if x is an immutable python type for which there exists an
 * equivalent immutable Javascript type. Otherwise return NULL.
 */
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

/**
 * If x is a wrapper around a Javascript object, unwrap the Javascript object
 * and return it. Otherwise, return NULL.
 */
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

/**
 * This function is a helper function for _python2js which handles the case when
 * we want to convert at least the outermost layer.
 */
static JsRef
_python2js_deep(PyObject* x, PyObject* cache, int depth)
{
  RETURN_IF_SUCCEEDS(_python2js_immutable(x));
  FAIL_IF_ERR_OCCURRED();
  RETURN_IF_SUCCEEDS(_python2js_proxy(x));
  FAIL_IF_ERR_OCCURRED();

  if (PyList_Check(x) || PyTuple_Check(x)) {
    return _python2js_sequence(x, cache, depth);
  }
  if (PyDict_Check(x)) {
    return _python2js_dict(x, cache, depth);
  }
  if (PySet_Check(x)) {
    return _python2js_set(x, cache, depth);
  }
  RETURN_IF_SUCCEEDS(_python2js_buffer(x));
  PyErr_Clear();
  return pyproxy_new(x);
finally:
  return NULL;
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
_python2js_add_to_cache(PyObject* cache, PyObject* pyparent, JsRef jsparent)
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
  result = PyDict_SetItem(cache, pyparentid, jsparentid);

finally:
  Py_CLEAR(pyparentid);
  Py_CLEAR(jsparentid);
  return result;
}

/**
 * This is a helper for python2js_with_depth. We need to create a cache for the
 * conversion, so we can't use the entry point as the root of the recursion.
 * Instead python2js_with_depth makes a cache and then calls this helper.
 *
 * This checks if the object x is already in the cache and if so returns it from
 * the cache. It leaves any real work to python2js or _python2js_deep.
 */
JsRef
_python2js(PyObject* x, PyObject* cache, int depth)
{
  PyObject* id = PyLong_FromSize_t((size_t)x);
  FAIL_IF_NULL(id);
  PyObject* val = PyDict_GetItemWithError(cache, id); /* borrowed */
  Py_CLEAR(id);
  if (val != NULL) {
    return hiwire_incref((JsRef)PyLong_AsLong(val));
  }
  FAIL_IF_ERR_OCCURRED();
  if (depth == 0) {
    return python2js(x);
  } else {
    return _python2js_deep(x, cache, depth - 1);
  }
finally:
  return NULL;
}

/**
 * Do a shallow conversion from python2js. Convert immutable types with
 * equivalent Javascript immutable types, but all other types are proxied.
 */
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

/**
 * Do a deep conversion from Python to Javascript, converting lists, dicts, and
 * sets down to depth "depth".
 */
JsRef
python2js_with_depth(PyObject* x, int depth)
{
  PyObject* cache = PyDict_New();
  if (cache == NULL) {
    return NULL;
  }
  JsRef result = _python2js(x, cache, depth);
  // Destroy the cache. Because the cache has raw JsRefs inside, we need to
  // manually dealloc them.
  PyObject *pykey, *pyval;
  Py_ssize_t pos = 0;
  while (PyDict_Next(cache, &pos, &pykey, &pyval)) {
    JsRef obj = (JsRef)PyLong_AsLong(pyval);
    hiwire_decref(obj);
  }
  Py_DECREF(cache);
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
