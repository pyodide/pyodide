#define PY_SSIZE_T_CLEAN
#include "python2js.h"
#include "Python.h"
#include "docstring.h"
#include "error_handling.h"
#include "js2python.h"
#include "jslib.h"
#include "jsmemops.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include "python_unexposed.h"
#include <emscripten.h>

#include "python2js_buffer.h"

static JsVal
_python2js_unicode(PyObject* x);

static inline JsVal
_python2js_immutable(PyObject* x);

int
_python2js_add_to_cache(JsVal cache, PyObject* pyparent, JsVal jsparent);

struct ConversionContext_s;

typedef struct ConversionContext_s
{
  JsRef cache;
  int depth;
  JsRef proxies;
  JsRef jscontext;
  JsVal (*dict_new)(struct ConversionContext_s* context);
  int (*dict_add_keyvalue)(struct ConversionContext_s* context,
                           JsVal target,
                           JsVal key,
                           JsVal value);
  JsVal (*dict_postprocess)(struct ConversionContext_s* context, JsVal dict);
  JsRef jspostprocess_list;
  bool default_converter;
  bool eager_converter;
} ConversionContext;

JsVal
_python2js(ConversionContext* context, PyObject* x);

// clang-format off
EM_JS(void,
_python2js_addto_postprocess_list,
(JsVal list, JsVal parent, JsVal key, PyObject* value), {
  list.push([ parent, key, value ]);
});

EM_JS(void, _python2js_handle_postprocess_list, (JsVal list, JsVal cache), {
  for (const [parent, key, ptr] of list) {
    let val = cache.get(ptr);
    if (parent.constructor.name === "LiteralMap") {
      parent.set(key, val)
    } else {
      // This is unfortunately a bit of a hack, if user does something weird
      // enough in dict_converter then it won't work.
      parent[key] = val;
    }
    // clang-format on
  }
});
// clang-format on

///////////////////////////////////////////////////////////////////////////////
//
// Simple Converters
//
// These convert float, int, and unicode types. Used by python2js_immutable
// (which also handles bool and None).

static JsVal
_python2js_float(PyObject* x)
{
  double x_double = PyFloat_AsDouble(x);
  if (x_double == -1.0 && PyErr_Occurred()) {
    return JS_ERROR;
  }
  return JsvNum_fromDouble(x_double);
}

#if PYLONG_BITS_IN_DIGIT == 15
#error "Expected PYLONG_BITS_IN_DIGIT == 30"
#endif

static JsVal
_python2js_long(PyObject* x)
{
  int overflow;
  long x_long = PyLong_AsLongAndOverflow(x, &overflow);
  if (x_long == -1) {
    if (!overflow) {
      FAIL_IF_ERR_OCCURRED();
    } else {
      // We want to group into u32 chunks for convenience of
      // JsvNum_fromDigits. If the number of bits is evenly divisible by
      // 32, we overestimate the number of needed u32s by one.
      size_t nbits = _PyLong_NumBits(x);
      size_t ndigits = (nbits >> 5) + 1;
      unsigned int digits[ndigits];
      FAIL_IF_MINUS_ONE(_PyLong_AsByteArray((PyLongObject*)x,
                                            (unsigned char*)digits,
                                            4 * ndigits,
                                            true /* little endian */,
                                            true /* signed */,
                                            true /* with_exceptions */));
      return JsvNum_fromDigits(digits, ndigits);
    }
  }
  return JsvNum_fromInt(x_long);
finally:
  return JS_ERROR;
}

// python2js string conversion
//
// FAQs:
//
// Q: Why do we use this approach rather than TextDecoder?
//
// A: TextDecoder does have an 'ascii' encoding and a 'ucs2' encoding which
// sound promising. They work in many cases but not in all cases, particularly
// when strings contain weird unprintable bytes. I suspect these conversion
// functions are also considerably faster than TextDecoder because it takes
// complicated extra code to cause the problematic edge case behavior of
// TextDecoder.
//
//
// Q: Is it okay to use str += more_str in a loop? Does this perform a lot of
// copies?
//
// A: We haven't profiled this but I suspect that the JS VM understands this
// code quite well and can git it into very performant code.
// TODO: someone should compare += in a loop to building a list and using
// list.join("") and see if one is faster than the other.

EM_JS_VAL(JsVal, _python2js_ucs1, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(DEREF_U8(ptr, i));
  }
  return jsstr;
});

EM_JS_VAL(JsVal, _python2js_ucs2, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(DEREF_U16(ptr, i));
  }
  return jsstr;
});

EM_JS_VAL(JsVal, _python2js_ucs4, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(DEREF_U32(ptr, i));
  }
  return jsstr;
});

static JsVal
_python2js_unicode(PyObject* x)
{
  int kind = PyUnicode_KIND(x);
  char* data = (char*)PyUnicode_DATA(x);
  int length = (int)PyUnicode_GET_LENGTH(x);
  switch (kind) {
    case PyUnicode_1BYTE_KIND:
      return _python2js_ucs1(data, length);
    case PyUnicode_2BYTE_KIND:
      return _python2js_ucs2(data, length);
    case PyUnicode_4BYTE_KIND:
      return _python2js_ucs4(data, length);
    default:
      assert(false /* invalid Unicode kind */);
  }
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
static JsVal
_python2js_sequence(ConversionContext* context, PyObject* x)
{
  bool success = false;
  PyObject* pyitem = NULL;

  JsVal jsarray = JsvArray_New();
  FAIL_IF_MINUS_ONE(
    _python2js_add_to_cache(hiwire_get(context->cache), x, jsarray));
  Py_ssize_t length = PySequence_Size(x);
  FAIL_IF_MINUS_ONE(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    PyObject* pyitem = PySequence_GetItem(x, i);
    FAIL_IF_NULL(pyitem);
    JsVal jsitem = _python2js(context, pyitem);
    FAIL_IF_JS_ERROR(jsitem);
    if (JsvNoValue_Check(jsitem)) {
      JsVal index = JsvNum_fromInt(JsvArray_Push(jsarray, JS_ERROR));
      _python2js_addto_postprocess_list(
        hiwire_get(context->jspostprocess_list), jsarray, index, pyitem);
    } else {
      JsvArray_Push(jsarray, jsitem);
    }
    Py_CLEAR(pyitem);
  }
  success = true;
finally:
  Py_CLEAR(pyitem);
  return success ? jsarray : JS_ERROR;
}

/**
 * WARNING: This function is not suitable for fallbacks. If this function
 * returns NULL, we must assume that the cache has been corrupted and bail out.
 */
static JsVal
_python2js_dict(ConversionContext* context, PyObject* x)
{
  bool success = false;
  PyObject* items = NULL;
  PyObject* iter = NULL;
  PyObject* item = NULL;

  _Py_IDENTIFIER(items);
  JsVal jsdict = context->dict_new(context);
  FAIL_IF_JS_ERROR(jsdict);
  FAIL_IF_MINUS_ONE(
    _python2js_add_to_cache(hiwire_get(context->cache), x, Jsv_novalue));

  // PyDict_Next may or may not work on dict subclasses, so get the `.items()`
  // and iterate that instead. See issue #4636.
  items = _PyObject_CallMethodIdNoArgs(x, &PyId_items);
  FAIL_IF_NULL(items);
  iter = PyObject_GetIter(items);
  FAIL_IF_NULL(iter);
  while ((item = PyIter_Next(iter))) {
    if (!PyTuple_Check(item)) {
      PyErr_SetString(PyExc_TypeError, "expected tuple");
      FAIL();
    }
    PyObject* pykey = PyTuple_GetItem(item, 0);
    FAIL_IF_NULL(pykey);
    PyObject* pyval = PyTuple_GetItem(item, 1);
    FAIL_IF_NULL(pyval);
    JsVal jskey = _python2js_immutable(pykey);
    if (JsvError_Check(jskey) || JsvNoValue_Check(jskey)) {
      FAIL_IF_ERR_OCCURRED();
      PyErr_Format(
        conversion_error, "Cannot use %R as a key for a Javascript Map", pykey);
      FAIL();
    }
    JsVal jsval = _python2js(context, pyval);
    FAIL_IF_JS_ERROR(jsval);
    if (JsvNoValue_Check(jsval)) {
      _python2js_addto_postprocess_list(
        hiwire_get(context->jspostprocess_list), jsdict, jskey, pyval);
    } else {
      FAIL_IF_MINUS_ONE(
        context->dict_add_keyvalue(context, jsdict, jskey, jsval));
    }
    Py_CLEAR(item);
  }
  FAIL_IF_ERR_OCCURRED();
  if (context->dict_postprocess) {
    jsdict = context->dict_postprocess(context, jsdict);
    FAIL_IF_JS_ERROR(jsdict);
  }
  FAIL_IF_MINUS_ONE(
    _python2js_add_to_cache(hiwire_get(context->cache), x, jsdict));
  success = true;
finally:
  Py_CLEAR(items);
  Py_CLEAR(iter);
  Py_CLEAR(item);
  return success ? jsdict : JS_ERROR;
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
static JsVal
_python2js_set(ConversionContext* context, PyObject* x)
{
  bool success = false;
  PyObject* iter = NULL;
  PyObject* pykey = NULL;
  // result:

  JsVal jsset = JsvSet_New();
  iter = PyObject_GetIter(x);
  FAIL_IF_NULL(iter);
  while ((pykey = PyIter_Next(iter))) {
    JsVal jskey = _python2js_immutable(pykey);
    if (JsvError_Check(jskey) || JsvNoValue_Check(jskey)) {
      FAIL_IF_ERR_OCCURRED();
      PyErr_Format(
        conversion_error, "Cannot use %R as a key for a Javascript Set", pykey);
      FAIL();
    }
    FAIL_IF_MINUS_ONE(JsvSet_Add(jsset, jskey));
    Py_CLEAR(pykey);
  }
  FAIL_IF_ERR_OCCURRED();
  // Because we only convert immutable keys, we can do this here.
  // Otherwise, we'd fail on the set that contains itself.
  FAIL_IF_MINUS_ONE(
    _python2js_add_to_cache(hiwire_get(context->cache), x, jsset));
  success = true;
finally:
  Py_CLEAR(pykey);
  return success ? jsset : JS_ERROR;
}

/**
 * if x is NULL, fail
 * if x is Js_novalue, do nothing
 * in any other case, return x
 */
#define RETURN_IF_HAS_VALUE(x)                                                 \
  do {                                                                         \
    JsVal _fresh_result = x;                                                   \
    FAIL_IF_JS_ERROR(_fresh_result);                                           \
    if (!JsvNoValue_Check(_fresh_result)) {                                    \
      return _fresh_result;                                                    \
    }                                                                          \
  } while (0)

/**
 * Convert x if x is an immutable python type for which there exists an
 * equivalent immutable JavaScript type. Otherwise return Js_novalue.
 *
 * Return type would be Option<JsRef>
 */
static inline JsVal
_python2js_immutable(PyObject* x)
{
  if (Py_IsNone(x)) {
    return Jsv_undefined;
  } else if (Py_IsTrue(x)) {
    return Jsv_true;
  } else if (Py_IsFalse(x)) {
    return Jsv_false;
  } else if (x == py_jsnull) {
    return Jsv_null;
  } else if (PyLong_Check(x)) {
    return _python2js_long(x);
  } else if (PyFloat_Check(x)) {
    return _python2js_float(x);
  } else if (PyUnicode_Check(x)) {
    return _python2js_unicode(x);
  }
  return Jsv_novalue;
}

/**
 * If x is a wrapper around a JavaScript object, unwrap the JavaScript object
 * and return it. Otherwise, return Js_novalue.
 *
 * Return type would be Option<JsRef>
 */
static inline JsVal
_python2js_proxy(PyObject* x)
{
  if (JsProxy_Check(x)) {
    return JsProxy_Val(x);
  }
  return Jsv_novalue;
}

JsVal
python2js__eager_converter(JsVal jscontext, PyObject* object);

JsVal
python2js__default_converter(JsVal jscontext, PyObject* object);

/**
 * This function is a helper function for _python2js which handles the case when
 * we want to convert at least the outermost layer.
 */
static JsVal
_python2js_deep(ConversionContext* context, PyObject* x)
{
  RETURN_IF_HAS_VALUE(_python2js_immutable(x));
  RETURN_IF_HAS_VALUE(_python2js_proxy(x));
  if (context->eager_converter) {
    RETURN_IF_HAS_VALUE(
      python2js__eager_converter(hiwire_get(context->jscontext), x));
  }
  if (PyList_Check(x) || PyTuple_Check(x)) {
    return _python2js_sequence(context, x);
  }
  if (PyDict_Check(x)) {
    return _python2js_dict(context, x);
  }
  if (PySet_Check(x)) {
    return _python2js_set(context, x);
  }
  if (PyObject_CheckBuffer(x)) {
    return _python2js_buffer(x);
  }
  if (context->default_converter) {
    return python2js__default_converter(hiwire_get(context->jscontext), x);
  }
  if (context->proxies) {
    return pyproxy_new(x);
  }
  PyErr_SetString(conversion_error, "No conversion known for x.");
finally:
  return JS_ERROR;
}

/**
 * During conversion of collection types (lists and dicts) from Python to
 * JavaScript, we need to make sure that those collections don't include
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
 * JavaScript object id for all collection objects. (One could do this for
 * scalars as well, but that would imply a larger cache, and identical scalars
 * are probably interned for deduplication on the JavaScript side anyway).
 *
 * This cache only lives for each invocation of python2js.
 */

// clang-format off
EM_JS_NUM(
int, _python2js_add_to_cache,
(JsVal cache, PyObject* pyparent, JsVal jsparent),
{
  cache.set(pyparent, jsparent);
});
// clang-format oh

EM_JS(JsVal, _python2js_cache_lookup, (JsVal cache, PyObject* pyparent), {
  return cache.get(pyparent) || Module.error;
});

/**
 * This is a helper for python2js_with_depth. We need to create a cache for the
 * conversion, so we can't use the entry point as the root of the recursion.
 * Instead python2js_with_depth makes a cache and then calls this helper.
 *
 * This checks if the object x is already in the cache and if so returns it from
 * the cache. It leaves any real work to python2js or _python2js_deep.
 */
EMSCRIPTEN_KEEPALIVE JsVal
_python2js(ConversionContext *context, PyObject* x)
{
  JsVal val = _python2js_cache_lookup(hiwire_get(context->cache), x);
  if (!JsvError_Check(val)) {
    return val;
  }
  FAIL_IF_ERR_OCCURRED();
  if (context->depth == 0) {
    RETURN_IF_HAS_VALUE(_python2js_immutable(x));
    RETURN_IF_HAS_VALUE(_python2js_proxy(x));
    if (context->default_converter) {
      return python2js__default_converter(hiwire_get(context->jscontext), x);
    }
    return python2js_track_proxies(x, hiwire_get(context->proxies), true);
  } else {
    context->depth--;
    JsVal result = _python2js_deep(context, x);
    if (context->proxies && pyproxy_Check(result)) {
      JsvArray_Push(hiwire_get(context->proxies), result);
    }
    context->depth++;
    return result;
  }
finally:
  return JS_ERROR;
}

/**
 * Do a shallow conversion from python2js. Convert immutable types with
 * equivalent JavaScript immutable types, but all other types are proxied.
 *
 */
JsVal
python2js_inner(PyObject* x, JsVal proxies, bool track_proxies, bool gc_register, bool is_json_adaptor)
{
  RETURN_IF_HAS_VALUE(_python2js_immutable(x));
  RETURN_IF_HAS_VALUE(_python2js_proxy(x));
  if (track_proxies && JsvError_Check(proxies)) {
    PyErr_SetString(conversion_error, "No conversion known for x.");
    FAIL();
  }
  JsVal proxy = pyproxy_new_ex(x, false, false, gc_register, is_json_adaptor);
  FAIL_IF_JS_ERROR(proxy);
  if (track_proxies) {
    JsvArray_Push(proxies, proxy);
  }
  return proxy;
finally:
  if (PyErr_Occurred()) {
    if (!PyErr_ExceptionMatches(conversion_error)) {
      _PyErr_FormatFromCause(conversion_error,
                             "Conversion from python to javascript failed");
    }
  } else {
    fail_test();
    PyErr_SetString(internal_error, "Internal error occurred in python2js");
  }
  return JS_ERROR;
}

/**
 * Do a shallow conversion from python2js. Convert immutable types with
 * equivalent JavaScript immutable types.
 *
 * Other types are proxied and added to the list proxies (to allow easy memory
 * management later). If proxies is NULL, python2js will raise an error instead
 * of creating a proxy.
 */
JsVal
python2js_track_proxies(PyObject* x, JsVal proxies, bool gc_register)
{
  return python2js_inner(x, proxies, true, gc_register, false);
}

/**
 * Do a translation from Python to JavaScript. Convert immutable types with
 * equivalent JavaScript immutable types, but all other types are proxied.
 */
EMSCRIPTEN_KEEPALIVE JsVal
python2js(PyObject* x)
{
  return python2js_inner(x, JS_ERROR, false, true, false);
}

// taking function pointers to EM_JS functions leads to linker errors.
static JsVal
_JsMap_New(ConversionContext *context)
{
  return JsvLiteralMap_New();
}

static int
_JsMap_Set(ConversionContext *context, JsVal map, JsVal key, JsVal value)
{
  return JsvMap_Set(map, key, value);
}

/**
 * Do a conversion from Python to JavaScript, converting lists, dicts, and sets
 * down to depth "depth".
 */
EMSCRIPTEN_KEEPALIVE JsVal
python2js_with_depth(PyObject* x, int depth, JsVal proxies)
{
  return python2js_custom(x, depth, proxies, JS_ERROR, JS_ERROR, JS_ERROR);
}

static JsVal
_JsArray_New(ConversionContext *context)
{
  return JsvArray_New();
}

// clang-format off
EM_JS_NUM(int,
_JsArray_PushEntry_helper,
(JsVal array, JsVal key, JsVal value),
{
  array.push([key, value ]);
})
// clang-format on

static int
_JsArray_PushEntry(ConversionContext* context,
                   JsVal array,
                   JsVal key,
                   JsVal value)
{
  return _JsArray_PushEntry_helper(array, key, value);
}

EM_JS_VAL(JsVal, _JsArray_PostProcess_helper, (JsVal jscontext, JsVal array), {
  return jscontext.dict_converter(array);
})

// clang-format off
EM_JS_VAL(
JsVal,
python2js__default_converter_js,
(JsVal jscontext, PyObject* object),
{
  let proxy = Module.pyproxy_new(object);
  try {
    return jscontext.default_converter(
      proxy,
      jscontext.converter,
      jscontext.cacheConversion
    );
  } finally {
    proxy.destroy();
  }
})
// clang-format on

JsVal
python2js__default_converter(JsVal jscontext, PyObject* object)
{
  return python2js__default_converter_js(jscontext, object);
}

// clang-format off
EM_JS_VAL(
JsVal,
python2js__eager_converter_js,
(JsVal jscontext, PyObject* object),
{
  // If the user calls `convert()`, we need to be careful to avoid recursion
  // error. They may be using it as a fallback, or to convert fields of an
  // object. If they are using it as a fallback, it shouldn't call the eager
  // converter again since that'd lead to infinite regress. If they are using it
  // to convert fields of an object, it should call back into the
  // eager_converter. To handle this, mark objects that we've seen once by
  // adding them to the visited set.
  //
  // This will cause weird behaviors on a self-referencing object when the cache
  // is not correctly used.
  if (jscontext.eager_visited.has(object)) {
    return Module.novalue;
  }
  jscontext.eager_visited.add(object);
  const proxy = Module.pyproxy_new(object);
  try {
    return jscontext.eager_converter(
      proxy,
      jscontext.converter,
      jscontext.cacheConversion
    );
  } finally {
    proxy.destroy();
  }
})
// clang-format on

JsVal
python2js__eager_converter(JsVal jscontext, PyObject* object)
{
  return python2js__eager_converter_js(jscontext, object);
}

static JsVal
_JsArray_PostProcess(ConversionContext* context, JsVal array)
{
  return _JsArray_PostProcess_helper(hiwire_get(context->jscontext), array);
}

// clang-format off
EM_JS_VAL(
JsVal,
python2js_custom__create_jscontext,
(ConversionContext *context,
  JsVal cache,
  JsVal dict_converter,
  JsVal default_converter,
  JsVal eager_converter),
{
  const jscontext = {};
  if (dict_converter) {
    jscontext.dict_converter = dict_converter;
  }
  if (default_converter) {
    jscontext.default_converter = default_converter;
    jscontext.cacheConversion = function (input, output) {
      // input should be a PyProxy, output should be a Javascript
      // object
      if (!API.isPyProxy(input)) {
        throw new TypeError("The first argument to cacheConversion must be a PyProxy.");
      }
      const input_ptr = Module.PyProxy_getPtr(input);
      cache.set(input_ptr, output);
    };
  }
  if (eager_converter) {
    jscontext.eager_converter = eager_converter;
    // See explanation in python2js__eager_converter_js
    jscontext.eager_visited = new Set();
  }
  if (default_converter || eager_converter) {
    jscontext.converter = function (x) {
      if (!API.isPyProxy(x)) {
        return x;
      }
      const ptr = Module.PyProxy_getPtr(x);
      let res;
      try {
        res = __python2js(context, ptr);
      } catch(e) {
        API.fatal_error(e);
      }
      if (res === Module.error) {
        _pythonexc2js();
      }
      return res;
    };
  }
  return jscontext;
})
// clang-format on

/**
 * dict_converter should be a JavaScript function that converts an Iterable of
 * pairs into the desired JavaScript object. If dict_converter is NULL, we use
 * python2js_with_depth which converts dicts to Map (the default)
 */
EMSCRIPTEN_KEEPALIVE JsVal
python2js_custom(PyObject* x,
                 int depth,
                 JsVal proxies,
                 JsVal dict_converter,
                 JsVal default_converter,
                 JsVal eager_converter)
{
  JsVal cache = JsvMap_New();
  ConversionContext context = { .cache = hiwire_new(cache),
                                .depth = depth,
                                .proxies = JsRef_new(proxies),
                                .jscontext = NULL,
                                .default_converter = false,
                                .eager_converter = false,
                                .jspostprocess_list =
                                  hiwire_new(JsvArray_New()) };
  if (JsvError_Check(dict_converter)) {
    // No custom converter provided, go back to default conversion to Map.
    context.dict_new = _JsMap_New;
    context.dict_add_keyvalue = _JsMap_Set;
    context.dict_postprocess = NULL;
  } else {
    context.dict_new = _JsArray_New;
    context.dict_add_keyvalue = _JsArray_PushEntry;
    context.dict_postprocess = _JsArray_PostProcess;
  }
  if (!JsvError_Check(default_converter)) {
    context.default_converter = true;
  }
  if (!JsvError_Check(eager_converter)) {
    context.eager_converter = true;
  }
  if (!JsvError_Check(dict_converter) || context.default_converter ||
      context.eager_converter) {
    context.jscontext = hiwire_new(python2js_custom__create_jscontext(
      &context, cache, dict_converter, default_converter, eager_converter));
  }
  JsVal result = _python2js(&context, x);
  _python2js_handle_postprocess_list(hiwire_get(context.jspostprocess_list),
                                     hiwire_get(context.cache));
  hiwire_CLEAR(context.jspostprocess_list);
  hiwire_CLEAR(context.jscontext);
  hiwire_CLEAR(context.proxies);
  hiwire_CLEAR(context.cache);
  if (JsvError_Check(result) || JsvNoValue_Check(result)) {
    result = JS_ERROR;
    if (PyErr_Occurred()) {
      if (!PyErr_ExceptionMatches(conversion_error)) {
        _PyErr_FormatFromCause(conversion_error,
                               "Conversion from python to javascript failed");
      }
    } else {
      fail_test();
      PyErr_SetString(internal_error,
                      "Internal error occurred in python2js_with_depth");
    }
  }
  return result;
}

static PyObject*
to_js(PyObject* self,
      PyObject* const* args,
      Py_ssize_t nargs,
      PyObject* kwnames)
{
  PyObject* obj = NULL;
  int depth = -1;
  PyObject* pyproxies = NULL;
  bool create_proxies = true;
  PyObject* py_dict_converter = NULL;
  PyObject* py_default_converter = NULL;
  PyObject* py_eager_converter = NULL;
  static const char* const _keywords[] = { "",
                                           "depth",
                                           "create_pyproxies",
                                           "pyproxies",
                                           "dict_converter",
                                           "default_converter",
                                           "eager_converter",
                                           0 };
  // See argparse docs on format strings:
  // https://docs.python.org/3/c-api/arg.html?highlight=pyarg_parse#parsing-arguments
  // O|$iOpOO:to_js
  // O              - self -- Object
  //  |             - start of optional args
  //   $            - start of kwonly args
  //    i           - depth -- signed integer
  //     p          - create_pyproxies -- predicate (ie bool)
  //      OOO       - PyObject* arguments for pyproxies, dict_converter, and
  //      default_converter.
  //         :to_js - name of this function for error messages
  static struct _PyArg_Parser _parser = { .format = "O|$ipOOOO:to_js",
                                          .keywords = _keywords };
  if (!_PyArg_ParseStackAndKeywords(args,
                                    nargs,
                                    kwnames,
                                    &_parser,
                                    &obj,
                                    &depth,
                                    &create_proxies,
                                    &pyproxies,
                                    &py_dict_converter,
                                    &py_default_converter,
                                    &py_eager_converter)) {
    return NULL;
  }

  if (Py_IsNone(obj) || PyBool_Check(obj) || PyLong_Check(obj) ||
      PyFloat_Check(obj) || PyUnicode_Check(obj) || JsProxy_Check(obj)) {
    // No point in converting these and it'd be useless to proxy them since
    // they'd just get converted back by `js2python` at the end
    Py_INCREF(obj);
    return obj;
  }
  PyObject* py_result = NULL;

  JsVal proxies;
  if (!create_proxies) {
    proxies = JS_ERROR;
  } else if (pyproxies) {
    if (!JsProxy_Check(pyproxies)) {
      PyErr_SetString(PyExc_TypeError,
                      "Expected a JsArray for the pyproxies argument");
      return NULL;
    }
    proxies = JsProxy_Val(pyproxies);
    if (!JsvArray_Check(proxies)) {
      PyErr_SetString(PyExc_TypeError,
                      "Expected a JsArray for the pyproxies argument");
      return NULL;
    }
  } else {
    proxies = JsvArray_New();
  }
  JsVal js_dict_converter = JS_ERROR;
  if (py_dict_converter) {
    js_dict_converter = python2js(py_dict_converter);
  }
  JsVal js_default_converter = JS_ERROR;
  if (py_default_converter) {
    js_default_converter = python2js(py_default_converter);
  }
  JsVal js_eager_converter = JS_ERROR;
  if (py_eager_converter) {
    js_eager_converter = python2js(py_eager_converter);
  }
  JsVal js_result = python2js_custom(obj,
                                     depth,
                                     proxies,
                                     js_dict_converter,
                                     js_default_converter,
                                     js_eager_converter);
  FAIL_IF_JS_ERROR(js_result);
  if (pyproxy_Check(js_result)) {
    // Oops, just created a PyProxy. Wrap it I guess?
    py_result = JsProxy_create(js_result);
  } else {
    py_result = js2python(js_result);
  }
finally:
  if (pyproxy_Check(js_dict_converter)) {
    destroy_proxy(js_dict_converter, NULL);
  }
  if (pyproxy_Check(js_default_converter)) {
    destroy_proxy(js_default_converter, NULL);
  }
  if (pyproxy_Check(js_eager_converter)) {
    destroy_proxy(js_eager_converter, NULL);
  }
  return py_result;
}

// As contrasts `destroy_proxies` defined in pyproxy.c and declared in
// pyproxy.h:
// 1. This handles JavaScript errors, for the other one JS errors are fatal.
// 2. This calls `proxy.destroy`, so if it is some other object with a `destroy`
//    method, that will get called (is this a good thing??)
// 3. destroy_proxies won't destroy proxies with roundtrip set to true, this
// will.
EM_JS_NUM(errcode, destroy_proxies_js, (JsVal proxies_id), {
  for (const proxy of proxies_id) {
    proxy.destroy();
  }
})

// We need to avoid a name clash with destroy_proxies defined in jsproxy.c
static PyObject*
destroy_proxies_(PyObject* self, PyObject* arg)
{
  if (!JsProxy_Check(arg)) {
    PyErr_SetString(PyExc_TypeError, "Expected a JsProxy for the argument");
    return NULL;
  }
  bool success = false;

  JsVal proxies = JsProxy_Val(arg);
  if (!JsvArray_Check(proxies)) {
    PyErr_SetString(PyExc_TypeError,
                    "Expected a Js Array for the pyproxies argument");
    FAIL();
  }
  FAIL_IF_MINUS_ONE(destroy_proxies_js(proxies));

  success = true;
finally:
  if (success) {
    Py_RETURN_NONE;
  } else {
    return NULL;
  }
}

static PyMethodDef methods[] = {
  {
    "to_js",
    (PyCFunction)to_js,
    METH_FASTCALL | METH_KEYWORDS,
  },
  {
    "destroy_proxies",
    (PyCFunction)destroy_proxies_,
    METH_O,
  },
  { NULL } /* Sentinel */
};

PyObject* py_jsnull = NULL;

int
python2js_init(PyObject* core)
{
  bool success = false;
  PyObject* docstring_source = PyImport_ImportModule("_pyodide._core_docs");
  FAIL_IF_NULL(docstring_source);
  FAIL_IF_MINUS_ONE(
    add_methods_and_set_docstrings(core, methods, docstring_source));
  py_jsnull = PyObject_GetAttrString(docstring_source, "jsnull");
  FAIL_IF_NULL(py_jsnull);

  success = true;
finally:
  Py_CLEAR(docstring_source);
  return success ? 0 : -1;
}
