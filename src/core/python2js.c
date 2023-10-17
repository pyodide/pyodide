#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "docstring.h"
#include "hiwire.h"
#include "js2python.h"
#include "jslib.h"
#include "jsmemops.h"
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
_python2js_add_to_cache(JsRef cache, PyObject* pyparent, JsRef jsparent);

struct ConversionContext_s;

typedef struct ConversionContext_s
{
  JsRef cache;
  int depth;
  JsRef proxies;
  JsRef jscontext;
  JsRef (*dict_new)(struct ConversionContext_s context);
  int (*dict_add_keyvalue)(struct ConversionContext_s context,
                           JsRef target,
                           JsRef key,
                           JsRef value);
  JsRef (*dict_postprocess)(struct ConversionContext_s context, JsRef dict);
  JsRef jspostprocess_list;
  bool default_converter;
} ConversionContext;

JsRef
_python2js(ConversionContext context, PyObject* x);

EM_JS(void,
      _python2js_addto_postprocess_list,
      (JsRef idlist, JsRef idparent, JsRef idkey, PyObject* value),
      {
        const list = Hiwire.get_value(idlist);
        const parent = Hiwire.get_value(idparent);
        const key = Hiwire.get_value(idkey);
        list.push([ parent, key, value ]);
      });

EM_JS(void, _python2js_handle_postprocess_list, (JsRef idlist, JsRef idcache), {
  const list = Hiwire.get_value(idlist);
  const cache = Hiwire.get_value(idcache);
  for (const[parent, key, value] of list) {
    let out_value = Hiwire.get_value(cache.get(value));
    // clang-format off
    if(parent.constructor.name === "Map"){
      parent.set(key, out_value)
    } else {
      // This is unfortunately a bit of a hack, if user does something weird
      // enough in dict_converter then it won't work.
      parent[key] = out_value;
    }
    // clang-format on
  }
});

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

#if PYLONG_BITS_IN_DIGIT == 15
#error "Expected PYLONG_BITS_IN_DIGIT == 30"
#endif

static JsRef
_python2js_long(PyObject* x)
{
  int overflow;
  long x_long = PyLong_AsLongAndOverflow(x, &overflow);
  if (x_long == -1) {
    if (!overflow) {
      FAIL_IF_ERR_OCCURRED();
    } else {
      // We want to group into u32 chunks for convenience of
      // hiwire_int_from_digits. If the number of bits is evenly divisible by
      // 32, we overestimate the number of needed u32s by one.
      size_t nbits = _PyLong_NumBits(x);
      size_t ndigits = (nbits >> 5) + 1;
      unsigned int digits[ndigits];
      FAIL_IF_MINUS_ONE(_PyLong_AsByteArray((PyLongObject*)x,
                                            (unsigned char*)digits,
                                            4 * ndigits,
                                            true /* little endian */,
                                            true /* signed */));
      return hiwire_int_from_digits(digits, ndigits);
    }
  }
  return hiwire_int(x_long);
finally:
  return NULL;
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

EM_JS_REF(JsRef, _python2js_ucs1, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(DEREF_U8(ptr, i));
  }
  return Hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, _python2js_ucs2, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(DEREF_U16(ptr, i));
  }
  return Hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, _python2js_ucs4, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(DEREF_U32(ptr, i));
  }
  return Hiwire.new_value(jsstr);
});

static JsRef
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
static JsRef
_python2js_sequence(ConversionContext context, PyObject* x)
{
  bool success = false;
  PyObject* pyitem = NULL;
  JsRef jsitem = NULL;
  // result:
  JsRef jsarray = NULL;

  jsarray = JsArray_New();
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(context.cache, x, jsarray));
  Py_ssize_t length = PySequence_Size(x);
  FAIL_IF_MINUS_ONE(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    PyObject* pyitem = PySequence_GetItem(x, i);
    FAIL_IF_NULL(pyitem);
    jsitem = _python2js(context, pyitem);
    FAIL_IF_NULL(jsitem);
    if (jsitem == Js_novalue) {
      JsRef index = hiwire_int(JsArray_Push_unchecked(jsarray, Js_null));
      _python2js_addto_postprocess_list(
        context.jspostprocess_list, jsarray, index, pyitem);
      hiwire_CLEAR(index);
    } else {
      JsArray_Push_unchecked(jsarray, jsitem);
    }
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
_python2js_dict(ConversionContext context, PyObject* x)
{
  bool success = false;
  JsRef jskey = NULL;
  JsRef jsval = NULL;
  // result:
  JsRef jsdict = NULL;

  jsdict = context.dict_new(context);
  FAIL_IF_NULL(jsdict);
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(context.cache, x, Js_novalue));
  PyObject *pykey, *pyval;
  Py_ssize_t pos = 0;
  while (PyDict_Next(x, &pos, &pykey, &pyval)) {
    jskey = _python2js_immutable(pykey);
    if (jskey == NULL || jskey == Js_novalue) {
      FAIL_IF_ERR_OCCURRED();
      PyErr_Format(
        conversion_error, "Cannot use %R as a key for a Javascript Map", pykey);
      FAIL();
    }
    jsval = _python2js(context, pyval);
    FAIL_IF_NULL(jsval);
    if (jsval == Js_novalue) {
      _python2js_addto_postprocess_list(
        context.jspostprocess_list, jsdict, jskey, pyval);
    } else {
      FAIL_IF_MINUS_ONE(
        context.dict_add_keyvalue(context, jsdict, jskey, jsval));
    }
    hiwire_CLEAR(jsval);
    hiwire_CLEAR(jskey);
  }
  if (context.dict_postprocess) {
    JsRef temp = context.dict_postprocess(context, jsdict);
    FAIL_IF_NULL(temp);
    hiwire_CLEAR(jsdict);
    jsdict = temp;
  }
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(context.cache, x, jsdict));
  success = true;
finally:
  hiwire_CLEAR(jsval);
  hiwire_CLEAR(jskey);
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
_python2js_set(ConversionContext context, PyObject* x)
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
    if (jskey == NULL || jskey == Js_novalue) {
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
  FAIL_IF_MINUS_ONE(_python2js_add_to_cache(context.cache, x, jsset));
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
 * if x is NULL, fail
 * if x is Js_novalue, do nothing
 * in any other case, return x
 */
#define RETURN_IF_HAS_VALUE(x)                                                 \
  do {                                                                         \
    JsRef _fresh_result = x;                                                   \
    FAIL_IF_NULL(_fresh_result);                                               \
    if (_fresh_result != Js_novalue) {                                         \
      return _fresh_result;                                                    \
    }                                                                          \
  } while (0)

/**
 * Convert x if x is an immutable python type for which there exists an
 * equivalent immutable JavaScript type. Otherwise return Js_novalue.
 *
 * Return type would be Option<JsRef>
 */
static inline JsRef
_python2js_immutable(PyObject* x)
{
  if (Py_IsNone(x)) {
    return Js_undefined;
  } else if (Py_IsTrue(x)) {
    return Js_true;
  } else if (Py_IsFalse(x)) {
    return Js_false;
  } else if (PyLong_Check(x)) {
    return _python2js_long(x);
  } else if (PyFloat_Check(x)) {
    return _python2js_float(x);
  } else if (PyUnicode_Check(x)) {
    return _python2js_unicode(x);
  }
  return Js_novalue;
}

/**
 * If x is a wrapper around a JavaScript object, unwrap the JavaScript object
 * and return it. Otherwise, return Js_novalue.
 *
 * Return type would be Option<JsRef>
 */
static inline JsRef
_python2js_proxy(PyObject* x)
{
  if (JsProxy_Check(x)) {
    return JsProxy_AsJs(x);
  }
  return Js_novalue;
}

JsRef
python2js__default_converter(JsRef jscontext, PyObject* object);

/**
 * This function is a helper function for _python2js which handles the case when
 * we want to convert at least the outermost layer.
 */
static JsRef
_python2js_deep(ConversionContext context, PyObject* x)
{
  RETURN_IF_HAS_VALUE(_python2js_immutable(x));
  RETURN_IF_HAS_VALUE(_python2js_proxy(x));
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
  if (context.default_converter) {
    return python2js__default_converter(context.jscontext, x);
  }
  if (context.proxies) {
    JsRef proxy = pyproxy_new(x);
    JsArray_Push_unchecked(context.proxies, proxy);
    return proxy;
  }
  PyErr_SetString(conversion_error, "No conversion known for x.");
finally:
  return NULL;
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
(JsRef cacheid, PyObject* pyparent, JsRef jsparent),
{
  const cache = Hiwire.get_value(cacheid);
  const old_value = cache.get(pyparent);
  if (old_value !== undefined) {
    Hiwire.decref(old_value);
  }
  cache.set(pyparent, Hiwire.incref(jsparent));
});
// clang-format oh

EM_JS(void, _python2js_destroy_cache, (JsRef cacheid), {
  const cache = Hiwire.get_value(cacheid);
  for (const[k, v] of cache.entries()) {
    Hiwire.decref(v);
  }
});

EM_JS(JsRef, _python2js_cache_lookup, (JsRef cacheid, PyObject* pyparent), {
  return Hiwire.get_value(cacheid).get(pyparent);
});

/**
 * This is a helper for python2js_with_depth. We need to create a cache for the
 * conversion, so we can't use the entry point as the root of the recursion.
 * Instead python2js_with_depth makes a cache and then calls this helper.
 *
 * This checks if the object x is already in the cache and if so returns it from
 * the cache. It leaves any real work to python2js or _python2js_deep.
 */
EMSCRIPTEN_KEEPALIVE JsRef
_python2js(ConversionContext context, PyObject* x)
{
  JsRef id = _python2js_cache_lookup(context.cache, x); /* borrowed */
  if (id != NULL) {
    return hiwire_incref(id);
  }
  FAIL_IF_ERR_OCCURRED();
  if (context.depth == 0) {
    RETURN_IF_HAS_VALUE(_python2js_immutable(x));
    RETURN_IF_HAS_VALUE(_python2js_proxy(x));
    if (context.default_converter) {
      return python2js__default_converter(context.jscontext, x);
    }
    return python2js_track_proxies(x, context.proxies, true);
  } else {
    context.depth--;
    return _python2js_deep(context, x);
  }
finally:
  return NULL;
}

/**
 * Do a shallow conversion from python2js. Convert immutable types with
 * equivalent JavaScript immutable types, but all other types are proxied.
 *
 */
JsRef
python2js_inner(PyObject* x, JsRef proxies, bool track_proxies, bool gc_register)
{
  RETURN_IF_HAS_VALUE(_python2js_immutable(x));
  RETURN_IF_HAS_VALUE(_python2js_proxy(x));
  if (track_proxies && proxies == NULL) {
    PyErr_SetString(conversion_error, "No conversion known for x.");
    FAIL();
  }
  JsRef proxy = pyproxy_new_ex(x, false, false, gc_register);
  FAIL_IF_NULL(proxy);
  if (track_proxies) {
    JsArray_Push_unchecked(proxies, proxy);
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
  return NULL;
}

/**
 * Do a shallow conversion from python2js. Convert immutable types with
 * equivalent JavaScript immutable types.
 *
 * Other types are proxied and added to the list proxies (to allow easy memory
 * management later). If proxies is NULL, python2js will raise an error instead
 * of creating a proxy.
 */
JsRef
python2js_track_proxies(PyObject* x, JsRef proxies, bool gc_register)
{
  return python2js_inner(x, proxies, true, gc_register);
}

/**
 * Do a translation from Python to JavaScript. Convert immutable types with
 * equivalent JavaScript immutable types, but all other types are proxied.
 */
EMSCRIPTEN_KEEPALIVE JsRef
python2js(PyObject* x)
{
  return python2js_inner(x, NULL, false, true);
}

EMSCRIPTEN_KEEPALIVE JsVal
python2js_val(PyObject* x)
{
  JsRef result = python2js(x);
  if (result == NULL) {
    return JS_NULL;
  }
  return hiwire_pop(result);
}

// taking function pointers to EM_JS functions leads to linker errors.
static JsRef
_JsMap_New(ConversionContext context)
{
  return JsMap_New();
}

static int
_JsMap_Set(ConversionContext context, JsRef map, JsRef key, JsRef value)
{
  return JsMap_Set(map, key, value);
}

/**
 * Do a conversion from Python to JavaScript, converting lists, dicts, and sets
 * down to depth "depth".
 */
EMSCRIPTEN_KEEPALIVE JsRef
python2js_with_depth(PyObject* x, int depth, JsRef proxies)
{
  return python2js_custom(x, depth, proxies, NULL, NULL);
}

static JsRef
_JsArray_New(ConversionContext context)
{
  return JsArray_New();
}

EM_JS_NUM(int,
          _JsArray_PushEntry_helper,
          (JsRef array, JsRef key, JsRef value),
          {
            Hiwire.get_value(array).push(
              [ Hiwire.get_value(key), Hiwire.get_value(value) ]);
          })

static int
_JsArray_PushEntry(ConversionContext context,
                   JsRef array,
                   JsRef key,
                   JsRef value)
{
  return _JsArray_PushEntry_helper(array, key, value);
}

EM_JS_REF(JsRef, _JsArray_PostProcess_helper, (JsRef jscontext, JsRef array), {
  return Hiwire.new_value(
    Hiwire.get_value(jscontext).dict_converter(Hiwire.get_value(array)));
})

// clang-format off
EM_JS_REF(
JsRef,
python2js__default_converter_js,
(JsRef jscontext, PyObject* object),
{
  let context = Hiwire.get_value(jscontext);
  let proxy = Module.pyproxy_new(object);
  let result = context.default_converter(
    proxy,
    context.converter,
    context.cacheConversion
  );
  proxy.destroy();
  return Hiwire.new_value(result);
})
// clang-format on

JsRef
python2js__default_converter(JsRef jscontext, PyObject* object)
{
  return python2js__default_converter_js(jscontext, object);
}

static JsRef
_JsArray_PostProcess(ConversionContext context, JsRef array)
{
  return _JsArray_PostProcess_helper(context.jscontext, array);
}

// clang-format off
EM_JS_REF(
JsRef,
python2js_custom__create_jscontext,
(ConversionContext context,
  JsRef idcache,
  JsRef dict_converter,
  JsRef default_converter),
{
  let jscontext = {};
  if (dict_converter !== 0) {
    jscontext.dict_converter = Hiwire.get_value(dict_converter);
  }
  if (default_converter !== 0) {
    jscontext.default_converter = Hiwire.get_value(default_converter);
    jscontext.cacheConversion = function (input, output) {
      // input should be a PyProxy, output should be a Javascript
      // object
      if (!API.isPyProxy(input)) {
        throw new TypeError("The first argument to cacheConversion must be a PyProxy.");
      }
      let input_ptr = Module.PyProxy_getPtr(input);
      let output_key = Hiwire.new_value(output);
      Hiwire.get_value(idcache).set(input_ptr, output_key);
    };
    jscontext.converter = function (x) {
      if (!API.isPyProxy(x)) {
        return x;
      }
      let ptr = Module.PyProxy_getPtr(x);
      let res = __python2js(context, ptr);
      return Hiwire.pop_value(res);
    };
  }
  return Hiwire.new_value(jscontext);
})
// clang-format on

/**
 * dict_converter should be a JavaScript function that converts an Iterable of
 * pairs into the desired JavaScript object. If dict_converter is NULL, we use
 * python2js_with_depth which converts dicts to Map (the default)
 */
EMSCRIPTEN_KEEPALIVE JsRef
python2js_custom(PyObject* x,
                 int depth,
                 JsRef proxies,
                 JsRef dict_converter,
                 JsRef default_converter)
{
  JsRef cache = JsMap_New();
  if (cache == NULL) {
    return NULL;
  }
  JsRef postprocess_list = JsArray_New();
  if (postprocess_list == NULL) {
    hiwire_CLEAR(cache);
    return NULL;
  }
  ConversionContext context = { .cache = cache,
                                .depth = depth,
                                .proxies = proxies,
                                .jscontext = NULL,
                                .default_converter = false,
                                .jspostprocess_list = postprocess_list };
  if (dict_converter == NULL) {
    // No custom converter provided, go back to default conversion to Map.
    context.dict_new = _JsMap_New;
    context.dict_add_keyvalue = _JsMap_Set;
    context.dict_postprocess = NULL;
  } else {
    context.dict_new = _JsArray_New;
    context.dict_add_keyvalue = _JsArray_PushEntry;
    context.dict_postprocess = _JsArray_PostProcess;
  }
  if (default_converter) {
    context.default_converter = true;
  }
  if (dict_converter || default_converter) {
    context.jscontext = python2js_custom__create_jscontext(
      context, cache, dict_converter, default_converter);
  }
  JsRef result = _python2js(context, x);
  _python2js_handle_postprocess_list(context.jspostprocess_list, context.cache);
  hiwire_CLEAR(context.jspostprocess_list);
  if (context.jscontext) {
    hiwire_CLEAR(context.jscontext);
  }
  // Destroy the cache. Because the cache has raw JsRefs inside, we need to
  // manually dealloc them.
  _python2js_destroy_cache(cache);
  hiwire_CLEAR(cache);
  if (result == NULL || result == Js_novalue) {
    result = NULL;
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
  static const char* const _keywords[] = { "",
                                           "depth",
                                           "create_pyproxies",
                                           "pyproxies",
                                           "dict_converter",
                                           "default_converter",
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
  static struct _PyArg_Parser _parser = { .format = "O|$ipOOO:to_js",
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
                                    &py_default_converter)) {
    return NULL;
  }

  if (Py_IsNone(obj) || PyBool_Check(obj) || PyLong_Check(obj) ||
      PyFloat_Check(obj) || PyUnicode_Check(obj) || JsProxy_Check(obj)) {
    // No point in converting these and it'd be useless to proxy them since
    // they'd just get converted back by `js2python` at the end
    Py_INCREF(obj);
    return obj;
  }
  JsRef proxies = NULL;
  JsRef js_dict_converter = NULL;
  JsRef js_default_converter = NULL;
  JsRef js_result = NULL;
  PyObject* py_result = NULL;

  if (!create_proxies) {
    proxies = NULL;
  } else if (pyproxies) {
    if (!JsProxy_Check(pyproxies)) {
      PyErr_SetString(PyExc_TypeError,
                      "Expected a JsProxy for the pyproxies argument");
      FAIL();
    }
    proxies = JsProxy_AsJs(pyproxies);
    if (!JsArray_Check(proxies)) {
      PyErr_SetString(PyExc_TypeError,
                      "Expected a Js Array for the pyproxies argument");
      FAIL();
    }
  } else {
    proxies = JsArray_New();
  }
  if (py_dict_converter) {
    js_dict_converter = python2js(py_dict_converter);
  }
  if (py_default_converter) {
    js_default_converter = python2js(py_default_converter);
  }
  js_result = python2js_custom(
    obj, depth, proxies, js_dict_converter, js_default_converter);
  FAIL_IF_NULL(js_result);
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
  hiwire_CLEAR(proxies);
  hiwire_CLEAR(js_dict_converter);
  hiwire_CLEAR(js_default_converter);
  hiwire_CLEAR(js_result);
  return py_result;
}

// As contrasts `destroy_proxies` defined in pyproxy.c and declared in
// pyproxy.h:
// 1. This handles JavaScript errors, for the other one JS errors are fatal.
// 2. This calls `proxy.destroy`, so if it is some other object with a `destroy`
//    method, that will get called (is this a good thing??)
// 3. destroy_proxies won't destroy proxies with roundtrip set to true, this
// will.
EM_JS_NUM(errcode, destroy_proxies_js, (JsRef proxies_id), {
  for (let proxy of Hiwire.get_value(proxies_id)) {
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
  JsRef proxies = NULL;

  proxies = JsProxy_AsJs(arg);
  if (!JsArray_Check(proxies)) {
    PyErr_SetString(PyExc_TypeError,
                    "Expected a Js Array for the pyproxies argument");
    FAIL();
  }
  FAIL_IF_MINUS_ONE(destroy_proxies_js(proxies));

  success = true;
finally:
  hiwire_CLEAR(proxies);
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

int
python2js_init(PyObject* core)
{
  bool success = false;
  PyObject* docstring_source = PyImport_ImportModule("_pyodide._core_docs");
  FAIL_IF_NULL(docstring_source);
  FAIL_IF_MINUS_ONE(
    add_methods_and_set_docstrings(core, methods, docstring_source));
  success = true;
finally:
  Py_CLEAR(docstring_source);
  return success ? 0 : -1;
}
