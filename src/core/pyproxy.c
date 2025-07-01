#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "error_handling.h"
#include "python_unexposed.h"
#include <emscripten.h>

#include "docstring.h"
#include "js2python.h"
#include "jsbind.h"
#include "jslib.h"
#include "jsmemops.h" // for pyproxy.js
#include "jsproxy.h"
#include "pyproxy.h"
#include "python2js.h"

#define Py_ENTER()                                                             \
  _check_gil();                                                                \
  const $$s = validSuspender.value;                                            \
  validSuspender.value = false;

#define Py_EXIT() validSuspender.value = $$s;

EM_JS(void, throw_no_gil, (), {
  throw new API.NoGilError("Attempted to use PyProxy when Python GIL not held");
});

EMSCRIPTEN_KEEPALIVE void
check_gil()
{
  if (!PyGILState_Check()) {
    throw_no_gil();
  }
}

static PyObject* Generator;
static PyObject* AsyncGenerator;
static PyObject* Sequence;
static PyObject* MutableSequence;
static PyObject* iscoroutinefunction;

_Py_IDENTIFIER(result);
_Py_IDENTIFIER(pop);
_Py_IDENTIFIER(ensure_future);
_Py_IDENTIFIER(add_done_callback);
_Py_IDENTIFIER(asend);
_Py_IDENTIFIER(throw);
_Py_IDENTIFIER(athrow);

// Use raw EM_JS for the next five commands. We intend to signal a fatal error
// if a JavaScript error is thrown.

EM_JS(int, pyproxy_Check, (JsVal val), { return API.isPyProxy(val); });

EM_JS(PyObject*, pyproxy_AsPyObject, (JsVal val), {
  if (!API.isPyProxy(val) || !pyproxyIsAlive(val)) {
    return 0;
  }
  return Module.PyProxy_getPtr(val);
});

EM_JS(void, destroy_proxies, (JsVal proxies, Js_Identifier* msg_ptr), {
  let msg = undefined;
  if (msg_ptr) {
    msg = _JsvString_FromId(msg_ptr);
  }
  for (let px of proxies) {
    Module.pyproxy_destroy(px, msg, false);
  }
});

EM_JS(void, gc_register_proxies, (JsVal proxies), {
  for (let px of proxies) {
    Module.gc_register_proxy(Module.PyProxy_getAttrs(px).shared);
  }
});

EM_JS(void, destroy_proxy, (JsVal px, Js_Identifier* msg_ptr), {
  const { shared, props } = Module.PyProxy_getAttrsQuiet(px);
  if (!shared.ptr) {
    // already destroyed
    return;
  }
  if (props.roundtrip) {
    // Don't destroy roundtrip proxies!
    return;
  }
  let msg = undefined;
  if (msg_ptr) {
    msg = _JsvString_FromId(msg_ptr);
  }
  Module.pyproxy_destroy(px, msg, false);
});

static PyObject* asyncio;

// Flags controlling presence or absence of many small mixins depending on which
// abstract protocols the Python object supports.
// clang-format off
#define HAS_LENGTH   (1 << 0)
#define HAS_GET      (1 << 1)
#define HAS_SET      (1 << 2)
#define HAS_CONTAINS (1 << 3)
#define IS_ITERABLE  (1 << 4)
#define IS_ITERATOR  (1 << 5)
#define IS_AWAITABLE (1 << 6)
#define IS_BUFFER    (1 << 7)
#define IS_CALLABLE  (1 << 8)
#define IS_ASYNC_ITERABLE (1 << 9)
#define IS_ASYNC_ITERATOR (1 << 10)
#define IS_GENERATOR (1 << 11)
#define IS_ASYNC_GENERATOR (1 << 12)
#define IS_SEQUENCE (1 << 13)
#define IS_MUTABLE_SEQUENCE (1 << 14)
#define IS_JSON_ADAPTOR_DICT (1 << 15)
#define IS_JSON_ADAPTOR_SEQUENCE (1 << 16)
#define IS_DICT (1 << 17)
// clang-format on

// _PyGen_GetCode is static, and PyGen_GetCode is a public wrapper around it
// which increfs the return value. We wrap the wrapper back into _PyGen_GetCode
// which returns a borrowed reference so we can use the exact upstream
// implementation of gen_is_coroutine
static inline PyCodeObject*
_PyGen_GetCode(PyGenObject* o)
{
  PyCodeObject* code = PyGen_GetCode((PyGenObject*)o);
  Py_DECREF(code);
  return code;
}

// Taken from genobject.c
// For checking whether an object is awaitable.
static int
gen_is_coroutine(PyObject* o)
{
  if (PyGen_CheckExact(o)) {
    PyCodeObject* code = _PyGen_GetCode((PyGenObject*)o);
    if (code->co_flags & CO_ITERABLE_COROUTINE) {
      return 1;
    }
  }
  return 0;
}

bool
py_is_awaitable(PyObject* o)
{
  if (PyCoro_CheckExact(o) || gen_is_coroutine(o)) {
    /* 'o' is a coroutine. */
    return true;
  }

  PyTypeObject* type = Py_TYPE(o);
  return !!(type->tp_as_async && type->tp_as_async->am_await);
}

/**
 * Do introspection on the python object to work out which abstract protocols it
 * supports. Most of these tests are taken from a corresponding abstract Object
 * protocol API defined in `abstract.c`. We wrote these tests to check whether
 * the corresponding CPython APIs are likely to work without actually creating
 * any temporary objects.
 *
 * Note: PyObject_IsInstance is expensive, avoid if possible!
 */
static int
type_getflags(PyTypeObject* obj_type)
{
  // Reduce casework by ensuring that protos aren't NULL.
  PySequenceMethods null_seq_proto = { 0 };
  PySequenceMethods* seq_proto =
    obj_type->tp_as_sequence ? obj_type->tp_as_sequence : &null_seq_proto;

  PyMappingMethods null_map_proto = { 0 };
  PyMappingMethods* map_proto =
    obj_type->tp_as_mapping ? obj_type->tp_as_mapping : &null_map_proto;

  PyAsyncMethods null_async_proto = { 0 };
  PyAsyncMethods* async_proto =
    obj_type->tp_as_async ? obj_type->tp_as_async : &null_async_proto;

  PyBufferProcs null_buffer_proto = { 0 };
  PyBufferProcs* buffer_proto =
    obj_type->tp_as_buffer ? obj_type->tp_as_buffer : &null_buffer_proto;

  bool success = false;
  int result = 0;
#define SET_FLAG_IF(flag, cond)                                                \
  if (cond) {                                                                  \
    result |= flag;                                                            \
  }
  // PyObject_Size
  SET_FLAG_IF(HAS_LENGTH, seq_proto->sq_length || map_proto->mp_length);
  // PyObject_GetItem
  if (map_proto->mp_subscript || seq_proto->sq_item) {
    result |= HAS_GET;
  }
  // PyObject_SetItem
  SET_FLAG_IF(HAS_SET, map_proto->mp_ass_subscript || seq_proto->sq_ass_item);
  // PySequence_Contains
  SET_FLAG_IF(HAS_CONTAINS, seq_proto->sq_contains);
  // PyObject_GetIter
  SET_FLAG_IF(IS_ITERABLE, obj_type->tp_iter || seq_proto->sq_item);
  SET_FLAG_IF(IS_ASYNC_ITERABLE, async_proto->am_aiter);
  if (obj_type->tp_iternext != NULL &&
      obj_type->tp_iternext != &_PyObject_NextNotImplemented) {
    result &= ~IS_ITERABLE;
    result |= IS_ITERATOR;
  }
  if (async_proto->am_anext) {
    result &= ~IS_ASYNC_ITERABLE;
    result |= IS_ASYNC_ITERATOR;
  }

  int isgen = PyObject_IsSubclass((PyObject*)obj_type, Generator);
  FAIL_IF_MINUS_ONE(isgen);
  int isasyncgen = PyObject_IsSubclass((PyObject*)obj_type, AsyncGenerator);
  FAIL_IF_MINUS_ONE(isasyncgen);
  SET_FLAG_IF(IS_GENERATOR, isgen);
  SET_FLAG_IF(IS_ASYNC_GENERATOR, isasyncgen);

  // There's no CPython API that corresponds directly to the "await" keyword.
  // Looking at disassembly, "await" translates into the GET_AWAITABLE opcode.
  // GET_AWAITABLE uses _PyCoro_GetAwaitableIter defined in genobject.c.
  // _PyCoro_GetAwaitableIter(obj) succeeds if one of the following conditions
  // are met:
  //
  //   1. obj is of exact type Coroutine (not a subtype),
  //   2. obj is of exact type Generator and the CO_ITERABLE_COROUTINE flag is
  //      set on the code object, or
  //   3. obj_type->tp_as_async->am_await is not NULL and calling it returns an
  //      iterator
  //
  // Here we check if the object has exact type Coroutine or if
  // `obj_type->tp_as_async->am_await` is defined. we can't check here if the
  // return value is an iterator (and if it's not the object is still awaitable
  // just with a wrong definition). we also can't tell here if condition 2 is
  // met, we check for this in pyproxy_getflags.

  SET_FLAG_IF(IS_AWAITABLE,
              Py_Is(obj_type, &PyCoro_Type) || async_proto->am_await);
  SET_FLAG_IF(IS_BUFFER, buffer_proto->bf_getbuffer);
  // PyObject_Call (from call.c)
  SET_FLAG_IF(IS_CALLABLE, obj_type->tp_call);
  // A sequence has __len__, __getitem__, __contains__, and __iter__ so if any
  // of these settings is missing, can skip the IsInstance check.
  if (((~result) & (HAS_LENGTH | HAS_GET | HAS_CONTAINS | IS_ITERABLE)) == 0) {
    int is_sequence = PyObject_IsSubclass((PyObject*)obj_type, Sequence);
    FAIL_IF_MINUS_ONE(is_sequence);
    // Only need to check Sequences for MutableSequence.
    int is_mutable_sequence =
      is_sequence ? PyObject_IsSubclass((PyObject*)obj_type, MutableSequence)
                  : 0;
    FAIL_IF_MINUS_ONE(is_mutable_sequence);
    SET_FLAG_IF(IS_SEQUENCE, is_sequence);
    SET_FLAG_IF(IS_MUTABLE_SEQUENCE, is_mutable_sequence);
  }
  SET_FLAG_IF(IS_DICT, Py_Is(obj_type, &PyDict_Type));
#undef SET_FLAG_IF

  success = true;
finally:
  return success ? result : -1;
}

static int dict_flags;
static int tuple_flags;
static int list_flags;

EMSCRIPTEN_KEEPALIVE int
pyproxy_getflags(PyObject* pyobj, bool is_json_adaptor)
{
  // Fast paths for some common cases
  if (PyDict_CheckExact(pyobj)) {
    int result = dict_flags;
    if (is_json_adaptor) {
      result |= IS_JSON_ADAPTOR_DICT;
    }
    return result;
  }
  if (PyTuple_CheckExact(pyobj)) {
    int result = tuple_flags;
    if (is_json_adaptor) {
      result |= IS_JSON_ADAPTOR_SEQUENCE;
    }
    return result;
  }
  if (PyList_CheckExact(pyobj)) {
    int result = list_flags;
    if (is_json_adaptor) {
      result |= IS_JSON_ADAPTOR_SEQUENCE;
    }
    return result;
  }
  PyTypeObject* obj_type = Py_TYPE(pyobj);
  int result = type_getflags(obj_type);
  FAIL_IF_MINUS_ONE(result);
  // Check for some flags that depend on the object itself and not just the
  // type.
  if (PyType_Check(pyobj)) {
    // If it's a type with a __class_getitem__, then this makes it indexable.
    // Nobody is very likely to want to index such a class from JavaScript, but
    // we try to be comprehensive.
    _Py_IDENTIFIER(__class_getitem__);
    PyObject* oname = _PyUnicode_FromId(&PyId___class_getitem__); /* borrowed */
    if (PyObject_HasAttr(pyobj, oname)) {
      result |= HAS_GET;
    }
  }
  // More importantly, if the result is a coroutine generator we can't tell just
  // by looking at the type...
  if (!(result & IS_AWAITABLE) && (result & IS_GENERATOR) &&
      gen_is_coroutine(pyobj)) {
    result |= IS_AWAITABLE;
  }
  if (is_json_adaptor) {
    if (result & IS_SEQUENCE) {
      result |= IS_JSON_ADAPTOR_SEQUENCE;
    } else if (result & HAS_GET) {
      result |= IS_JSON_ADAPTOR_DICT;
    }
  }
finally:
  return result;
}

///////////////////////////////////////////////////////////////////////////////
//
// Object protocol wrappers
//
// This section defines wrappers for Python Object protocol API calls that we
// are planning to offer on the PyProxy. Much of this could be written in
// JavaScript instead. Some reasons to do it in C:
//  1. Some CPython APIs are actually secretly macros which cannot be used from
//     JavaScript.
//  2. The code is a bit more concise in C.
//  3. It may be preferable to minimize the number of times we cross between
//     wasm and javascript for performance reasons
//  4. Better separation of functionality: Most of the JavaScript code is
//     boilerpalte. Most of this code here is boilerplate. However, the
//     boilerplate in these C API wwrappers is a bit different than the
//     boilerplate in the javascript wrappers, so we've factored it into two
//     distinct layers of boilerplate.
//
//  Item 1 makes it technically necessary to use these wrappers once in a while.
//  I think all of these advantages outweigh the cost of splitting up the
//  implementation of each feature like this, especially because most of the
//  logic is very boilerplatey, so there isn't much surprising code hidden
//  somewhere else.

EMSCRIPTEN_KEEPALIVE
bool compat_to_string_repr = false;

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_repr(PyObject* pyobj)
{
  PyObject* pyrepr = NULL;
  JsVal jsrepr = JS_ERROR;

  if (compat_to_string_repr) {
    pyrepr = PyObject_Repr(pyobj);
  } else {
    pyrepr = PyObject_Str(pyobj);
  }
  FAIL_IF_NULL(pyrepr);
  jsrepr = python2js(pyrepr);

finally:
  Py_CLEAR(pyrepr);
  return jsrepr;
}

/**
 * Wrapper for the "proxy.type" getter, which behaves a little bit like
 * `type(obj)`, but instead of returning the class we just return the name of
 * the class. The exact behavior is that this usually gives "module.name" but
 * for builtins just gives "name". So in particular, usually it is equivalent
 * to:
 *
 * `type(x).__module__ + "." + type(x).__name__`
 *
 * But other times it behaves like:
 *
 * `type(x).__name__`
 */
EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_type(PyObject* ptrobj)
{
  return JsvUTF8ToString(Py_TYPE(ptrobj)->tp_name);
}

EMSCRIPTEN_KEEPALIVE int
_pyproxy_hasattr(PyObject* pyobj, JsVal jskey)
{
  PyObject* pykey = NULL;
  int result = -1;

  pykey = js2python(jskey);
  FAIL_IF_NULL(pykey);
  result = PyObject_HasAttr(pyobj, pykey);

finally:
  Py_CLEAR(pykey);
  return result;
}

/* Specialized version of _PyObject_GenericGetAttrWithDict
   specifically for the LOAD_METHOD opcode.

   Return 1 if a method is found, 0 if it's a regular attribute
   from __dict__ or something returned by using a descriptor
   protocol.

   `method` will point to the resolved attribute or NULL.  In the
   latter case, an error will be set.
*/
int
_PyObject_GetMethod(PyObject* obj, PyObject* name, PyObject** method);

EM_JS(JsVal, proxy_cache_get, (JsVal proxyCache, PyObject* descr), {
  const proxy = proxyCache.get(descr);
  if (!proxy) {
    return Module.error;
  }
  // Okay found a proxy. Is it alive?
  if (pyproxyIsAlive(proxy)) {
    return proxy;
  } else {
    // It's dead, tidy up
    proxyCache.delete(descr);
    return Module.error;
  }
})

// clang-format off
EM_JS(void,
proxy_cache_set,
(JsVal proxyCache, PyObject* descr, JsVal proxy), {
  proxyCache.set(descr, proxy);
})
// clang-format on

/**
 * Used by pyproxy_iter_next and pyproxy_get_item for handling json adaptors.
 *
 * If is_json_adaptor,
 *  1. check json adaptor cache for x, if it's already there get existing value
 *  2. If it's not already there, convert x. Add an appropriate json adaptor
 *     type flag if x needs it.
 *  3. Add result to proxy cache.
 */
JsVal
python2js_json_adaptor(PyObject* x, JsVal proxyCache, bool is_json_adaptor)
{
  if (!is_json_adaptor) {
    return python2js(x);
  }
  JsVal cached_proxy = proxy_cache_get(proxyCache, x); /* borrowed */
  if (!JsvError_Check(cached_proxy)) {
    return cached_proxy;
  }
  JsVal result = python2js_inner(x, JS_ERROR, false, true, is_json_adaptor);
  if (pyproxy_Check(result)) {
    proxy_cache_set(proxyCache, x, result);
  }
  return result;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_getattr(PyObject* pyobj, JsVal key, JsVal proxyCache)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pydescr = NULL;
  PyObject* pyresult = NULL;
  JsVal result = JS_ERROR;

  pykey = js2python(key);
  FAIL_IF_NULL(pykey);
  // If it's a method, we use the descriptor pointer as the cache key rather
  // than the actual bound method. This allows us to reuse bound methods from
  // the cache.
  // _PyObject_GetMethod will return true and store a descriptor into pydescr if
  // the attribute we are looking up is a method, otherwise it will return false
  // and set pydescr to the actual attribute (in particular, I believe that it
  // will resolve other types of getter descriptors automatically).
  int is_method = _PyObject_GetMethod(pyobj, pykey, &pydescr);
  FAIL_IF_NULL(pydescr);
  JsVal cached_proxy = proxy_cache_get(proxyCache, pydescr); /* borrowed */
  if (!JsvError_Check(cached_proxy)) {
    result = cached_proxy;
    goto success;
  }
  if (PyErr_Occurred()) {
    FAIL();
  }
  if (is_method) {
    pyresult =
      Py_TYPE(pydescr)->tp_descr_get(pydescr, pyobj, (PyObject*)Py_TYPE(pyobj));
    FAIL_IF_NULL(pyresult);
  } else {
    pyresult = pydescr;
    Py_INCREF(pydescr);
  }
  result = python2js(pyresult);
  if (pyproxy_Check(result)) {
    // If a getter returns a different object every time, this could potentially
    // fill up the cache with a lot of junk. If this is a problem, the user will
    // have to manually destroy the attributes.
    proxy_cache_set(proxyCache, pydescr, result);
  }

success:
  success = true;
finally:
  Py_CLEAR(pykey);
  Py_CLEAR(pydescr);
  Py_CLEAR(pyresult);
  if (!success) {
    if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
      PyErr_Clear();
    }
  }
  return result;
};

EMSCRIPTEN_KEEPALIVE int
_pyproxy_setattr(PyObject* pyobj, JsVal key, JsVal value)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pyval = NULL;

  pykey = js2python(key);
  FAIL_IF_NULL(pykey);
  pyval = js2python(value);
  FAIL_IF_NULL(pyval);
  FAIL_IF_MINUS_ONE(PyObject_SetAttr(pyobj, pykey, pyval));

  success = true;
finally:
  Py_CLEAR(pykey);
  Py_CLEAR(pyval);
  return success ? 0 : -1;
}

EMSCRIPTEN_KEEPALIVE int
_pyproxy_delattr(PyObject* pyobj, JsVal idkey)
{
  bool success = false;
  PyObject* pykey = NULL;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  FAIL_IF_MINUS_ONE(PyObject_DelAttr(pyobj, pykey));

  success = true;
finally:
  Py_CLEAR(pykey);
  return success ? 0 : -1;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_getitem(PyObject* pyobj,
                 JsVal jskey,
                 JsVal proxyCache,
                 bool is_json_adaptor)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pyresult = NULL;
  JsVal result;

  pykey = js2python(jskey);
  FAIL_IF_NULL(pykey);
  pyresult = PyObject_GetItem(pyobj, pykey);
  FAIL_IF_NULL(pyresult);
  result = python2js_json_adaptor(pyresult, proxyCache, is_json_adaptor);
  FAIL_IF_JS_ERROR(result);

  success = true;
finally:
  if (!success && (PyErr_ExceptionMatches(PyExc_KeyError) ||
                   PyErr_ExceptionMatches(PyExc_IndexError))) {
    PyErr_Clear();
  }
  Py_CLEAR(pykey);
  Py_CLEAR(pyresult);
  if (!success) {
    return JS_ERROR;
  }
  return result;
};

EMSCRIPTEN_KEEPALIVE int
_pyproxy_setitem(PyObject* pyobj, JsVal jskey, JsVal jsval)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pyval = NULL;

  pykey = js2python(jskey);
  FAIL_IF_NULL(pykey);
  pyval = js2python(jsval);
  FAIL_IF_NULL(pyval);
  FAIL_IF_MINUS_ONE(PyObject_SetItem(pyobj, pykey, pyval));

  success = true;
finally:
  Py_CLEAR(pykey);
  Py_CLEAR(pyval);
  return success ? 0 : -1;
}

EMSCRIPTEN_KEEPALIVE int
_pyproxy_delitem(PyObject* pyobj, JsVal idkey)
{
  bool success = false;
  PyObject* pykey = NULL;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  FAIL_IF_MINUS_ONE(PyObject_DelItem(pyobj, pykey));

  success = true;
finally:
  Py_CLEAR(pykey);
  return success ? 0 : -1;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_slice_assign(PyObject* pyobj,
                      Py_ssize_t start,
                      Py_ssize_t stop,
                      JsVal val)
{
  PyObject* pyval = NULL;
  PyObject* pyresult = NULL;
  JsVal jsresult = JS_ERROR;

  pyval = js2python(val);

  Py_ssize_t len = PySequence_Length(pyobj);
  if (len <= stop) {
    stop = len;
  }
  pyresult = PySequence_GetSlice(pyobj, start, stop);
  FAIL_IF_NULL(pyresult);
  FAIL_IF_MINUS_ONE(PySequence_SetSlice(pyobj, start, stop, pyval));
  JsVal proxies = JsvArray_New();
  jsresult = python2js_with_depth(pyresult, 1, proxies);

finally:
  Py_CLEAR(pyresult);
  Py_CLEAR(pyval);
  return jsresult;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_pop(PyObject* pyobj, bool pop_start)
{
  PyObject* idx = NULL;
  PyObject* pyresult = NULL;
  JsVal jsresult = JS_ERROR;
  if (pop_start) {
    idx = PyLong_FromLong(0);
    FAIL_IF_NULL(idx);
    pyresult = _PyObject_CallMethodIdOneArg(pyobj, &PyId_pop, idx);
  } else {
    pyresult = _PyObject_CallMethodIdNoArgs(pyobj, &PyId_pop);
  }
  if (pyresult != NULL) {
    jsresult = python2js(pyresult);
    FAIL_IF_JS_ERROR(jsresult);
  } else {
    if (PyErr_ExceptionMatches(PyExc_IndexError)) {
      PyErr_Clear();
      jsresult = Jsv_undefined;
    } else {
      FAIL();
    }
  }
finally:
  Py_CLEAR(idx);
  Py_CLEAR(pyresult);
  return jsresult;
}

EMSCRIPTEN_KEEPALIVE int
_pyproxy_contains(PyObject* pyobj, JsVal idkey)
{
  PyObject* pykey = NULL;
  int result = -1;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  result = PySequence_Contains(pyobj, pykey);

finally:
  Py_CLEAR(pykey);
  return result;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_ownKeys(PyObject* pyobj)
{
  bool success = false;
  PyObject* pydir = NULL;

  pydir = PyObject_Dir(pyobj);
  FAIL_IF_NULL(pydir);

  JsVal dir = JsvArray_New();
  Py_ssize_t n = PyList_Size(pydir);
  FAIL_IF_MINUS_ONE(n);
  for (Py_ssize_t i = 0; i < n; ++i) {
    PyObject* pyentry = PyList_GetItem(pydir, i); /* borrowed */
    JsVal entry = python2js(pyentry);
    FAIL_IF_JS_ERROR(entry);
    JsvArray_Push(dir, entry);
  }

  success = true;
finally:
  Py_CLEAR(pydir);
  if (!success) {
    return JS_ERROR;
  }
  return dir;
}

/**
 * This sets up a call to _PyObject_Vectorcall. It's a helper function for
 * callPyObjectKwargs. This is the primary entrypoint from JavaScript into
 * Python code.
 *
 * Vectorcall expects the arguments to be communicated as:
 *
 *  PyObject*const *args: the positional arguments and followed by the keyword
 *    arguments
 *
 *  size_t nargs_with_flag : the number of arguments plus a flag
 *      PY_VECTORCALL_ARGUMENTS_OFFSET. The flag PY_VECTORCALL_ARGUMENTS_OFFSET
 *      indicates that we left an initial entry in the array to be used as a
 *      self argument in case the callee is a bound method.
 *
 *  PyObject* kwnames : a tuple of the keyword argument names. The length of
 *      this tuple tells CPython how many key word arguments there are.
 *
 * Our arguments are:
 *
 *   callable : The object to call.
 *   args : The list of JavaScript arguments, both positional and kwargs.
 *   numposargs : The number of positional arguments.
 *   kwnames : List of names of the keyword arguments
 *   numkwargs : The length of kwargs
 *
 *   Returns: The return value translated to JavaScript.
 */
EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_apply(PyObject* callable,
               JsVal jsargs,
               size_t numposargs,
               JsVal jskwnames,
               size_t numkwargs)
{
  size_t total_args = numposargs + numkwargs;
  size_t last_converted_arg = total_args;
  PyObject* pyargs_array[total_args + 1];
  PyObject** pyargs = pyargs_array;
  pyargs++; // leave a space for self argument in case callable is a bound
            // method
  PyObject* pykwnames = NULL;
  PyObject* pyresult = NULL;
  JsVal result = JS_ERROR;

  // Put both arguments and keyword arguments into pyargs
  for (Py_ssize_t i = 0; i < total_args; ++i) {
    JsVal jsitem = JsvArray_Get(jsargs, i);
    // pyitem is moved into pyargs so we don't need to clear it later.
    PyObject* pyitem = js2python(jsitem);
    if (pyitem == NULL) {
      last_converted_arg = i;
      FAIL();
    }
    pyargs[i] = pyitem; // pyitem is moved into pyargs.
  }
  if (numkwargs > 0) {
    // Put names of keyword arguments into a tuple
    pykwnames = PyTuple_New(numkwargs);
    for (Py_ssize_t i = 0; i < numkwargs; i++) {
      JsVal jsitem = JsvArray_Get(jskwnames, i);
      // pyitem is moved into pykwargs so we don't need to clear it later.
      PyObject* pyitem = js2python(jsitem);
      PyTuple_SET_ITEM(pykwnames, i, pyitem);
    }
  }
  // Tell callee that we left space for a self argument
  size_t nargs_with_flag = numposargs | PY_VECTORCALL_ARGUMENTS_OFFSET;
  pyresult = _PyObject_Vectorcall(callable, pyargs, nargs_with_flag, pykwnames);
  FAIL_IF_NULL(pyresult);
  result = python2js(pyresult);

finally:
  // If we failed to convert one of the arguments, then pyargs is partially
  // uninitialized. Only clear the part that actually has stuff in it.
  for (Py_ssize_t i = 0; i < last_converted_arg; i++) {
    Py_CLEAR(pyargs[i]);
  }
  Py_CLEAR(pyresult);
  Py_CLEAR(pykwnames);
  return result;
}

void
set_suspender(JsVal suspender);

/**
 * call _pyproxy_apply but save the error flag into the argument so it can't be
 * observed by unrelated Python callframes. callPyObjectKwargsSuspending will
 * restore the error flag before calling pythonexc2js(). See
 * test_stack_switching.test_throw_from_switcher for a detailed explanation.
 */
EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_apply_promising(JsVal suspender,
                         PyObject* callable,
                         JsVal jsargs,
                         size_t numposargs,
                         JsVal jskwnames,
                         size_t numkwargs,
                         PyObject** exc)
{
  set_suspender(suspender);
  JsVal res =
    _pyproxy_apply(callable, jsargs, numposargs, jskwnames, numkwargs);
  *exc = PyErr_GetRaisedException();
  // In case the result is a thenable, in callPromisingKwargs we only want to
  // await the stack switch not the thenable that Python returned. So we wrap
  // the result in a one-entry list. We'll unwrap it in callPromisingKwargs
  // after awaiting the callable. If there was a synchronous error, we'll wrap
  // the "null" in a list anyways. This simplifies the code a bit.
  JsVal wrap = JsvArray_New();
  JsvArray_Push(wrap, res);
  return wrap;
}

EMSCRIPTEN_KEEPALIVE bool
_iscoroutinefunction(PyObject* f)
{
  _Py_IDENTIFIER(_is_coroutine_marker);

  // Some fast paths for common cases to avoid calling into Python
  if (PyMethod_Check(f)) {
    f = PyMethod_GET_FUNCTION(f);
  }

  // _is_coroutine_marker is added to Python stdlib in 3.12. Check for it here
  // to make sure we don't accidentally return false negatives when we update to
  // 3.12.
  if (PyFunction_Check(f) &&
      !PyObject_HasAttr(f, _PyUnicode_FromId(&PyId__is_coroutine_marker))) {
    PyFunctionObject* func = (PyFunctionObject*)f;
    PyCodeObject* code = (PyCodeObject*)PyFunction_GET_CODE(func);
    return (code->co_flags) & CO_COROUTINE;
  }

  // Wasn't a basic callable, call into inspect.iscoroutinefunction
  PyObject* result = PyObject_CallOneArg(iscoroutinefunction, f);
  if (!result) {
    PyErr_Clear();
  }
  bool ret = Py_IsTrue(result);
  Py_CLEAR(result);
  return ret;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_iter_next(PyObject* iterator, JsVal proxyCache, bool is_json_adaptor)
{
  PyObject* item = PyIter_Next(iterator);
  if (item == NULL) {
    return JS_ERROR;
  }
  JsVal result = python2js_json_adaptor(item, proxyCache, is_json_adaptor);
  Py_CLEAR(item);
  return result;
}

EM_JS(JsVal, _pyproxyGen_make_result, (bool done, JsVal value), {
  return { done : !!done, value };
})

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxyGen_Send(PyObject* receiver, JsVal jsval)
{
  bool success = false;
  PyObject* v = NULL;
  PyObject* retval = NULL;

  v = js2python(jsval);
  FAIL_IF_NULL(v);
  PySendResult status = PyIter_Send(receiver, v, &retval);
  if (status == PYGEN_ERROR) {
    FAIL();
  }
  JsVal result = python2js(retval);
  FAIL_IF_JS_ERROR(result);

  success = true;
finally:
  Py_CLEAR(v);
  Py_CLEAR(retval);
  if (!success) {
    return JS_ERROR;
  }
  return _pyproxyGen_make_result(status == PYGEN_RETURN, result);
}

EMSCRIPTEN_KEEPALIVE
JsVal
_pyproxyGen_return(PyObject* receiver, JsVal jsval)
{
  bool success = false;
  PySendResult status = PYGEN_ERROR;
  PyObject* pyresult;

  JsVal result;

  // Throw GeneratorExit into generator
  pyresult =
    _PyObject_CallMethodIdOneArg(receiver, &PyId_throw, PyExc_GeneratorExit);
  if (pyresult == NULL) {
    if (PyErr_ExceptionMatches(PyExc_GeneratorExit)) {
      // If GeneratorExit comes back out, return original value.
      PyErr_Clear();
      status = PYGEN_RETURN;
      result = jsval;
      success = true;
      goto finally;
    }
    //
    FAIL_IF_MINUS_ONE(_PyGen_FetchStopIterationValue(&pyresult));
    status = PYGEN_RETURN;
  } else {
    status = PYGEN_NEXT;
  }
  result = python2js(pyresult);
  FAIL_IF_JS_ERROR(result);
  success = true;
finally:
  if (!success) {
    return JS_ERROR;
  }
  Py_CLEAR(pyresult);
  return _pyproxyGen_make_result(status == PYGEN_RETURN, result);
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxyGen_throw(PyObject* receiver, JsVal jsval)
{
  bool success = false;
  PyObject* pyvalue = NULL;
  PyObject* pyresult = NULL;
  PySendResult status = PYGEN_ERROR;

  JsVal result;

  pyvalue = js2python(jsval);
  FAIL_IF_NULL(pyvalue);
  if (!PyExceptionInstance_Check(pyvalue)) {
    /* Not something you can raise.  throw() fails. */
    PyErr_Format(PyExc_TypeError,
                 "exceptions must be classes or instances "
                 "deriving from BaseException, not %s",
                 Py_TYPE(pyvalue)->tp_name);
    FAIL();
  }
  pyresult = _PyObject_CallMethodIdOneArg(receiver, &PyId_throw, pyvalue);
  if (pyresult == NULL) {
    FAIL_IF_MINUS_ONE(_PyGen_FetchStopIterationValue(&pyresult));
    status = PYGEN_RETURN;
  } else {
    status = PYGEN_NEXT;
  }
  result = python2js(pyresult);
  FAIL_IF_JS_ERROR(result);
  success = true;
finally:
  Py_CLEAR(pyresult);
  Py_CLEAR(pyvalue);
  if (!success) {
    return JS_ERROR;
  }
  return _pyproxyGen_make_result(status == PYGEN_RETURN, result);
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxyGen_asend(PyObject* receiver, JsVal jsval)
{
  PyObject* v = NULL;
  PyObject* asend = NULL;
  PyObject* pyresult = NULL;
  JsVal jsresult = JS_ERROR;

  v = js2python(jsval);
  FAIL_IF_NULL(v);
  asend = _PyObject_GetAttrId(receiver, &PyId_asend);
  if (asend) {
    pyresult = PyObject_CallOneArg(asend, v);
  } else {
    PyErr_Clear();
    PyTypeObject* t = Py_TYPE(receiver);
    if (t->tp_as_async == NULL || t->tp_as_async->am_anext == NULL) {
      PyErr_Format(PyExc_TypeError,
                   "'%.200s' object is not an async iterator",
                   t->tp_name);
      return JS_ERROR;
    }
    pyresult = (*t->tp_as_async->am_anext)(receiver);
  }
  FAIL_IF_NULL(pyresult);

  jsresult = python2js(pyresult);
  FAIL_IF_JS_ERROR(jsresult);

finally:
  Py_CLEAR(v);
  Py_CLEAR(asend);
  Py_CLEAR(pyresult);
  return jsresult;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxyGen_areturn(PyObject* receiver)
{
  PyObject* v = NULL;
  PyObject* asend = NULL;
  PyObject* pyresult = NULL;
  JsVal jsresult = JS_ERROR;

  pyresult =
    _PyObject_CallMethodIdOneArg(receiver, &PyId_athrow, PyExc_GeneratorExit);
  FAIL_IF_NULL(pyresult);

  jsresult = python2js(pyresult);
  FAIL_IF_JS_ERROR(jsresult);

finally:
  Py_CLEAR(v);
  Py_CLEAR(asend);
  Py_CLEAR(pyresult);
  return jsresult;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxyGen_athrow(PyObject* receiver, JsVal jsval)
{
  PyObject* v = NULL;
  PyObject* asend = NULL;
  PyObject* pyresult = NULL;
  JsVal jsresult = JS_ERROR;

  v = js2python(jsval);
  FAIL_IF_NULL(v);
  if (!PyExceptionInstance_Check(v)) {
    /* Not something you can raise.  throw() fails. */
    PyErr_Format(PyExc_TypeError,
                 "exceptions must be classes or instances "
                 "deriving from BaseException, not %s",
                 Py_TYPE(v)->tp_name);
    FAIL();
  }
  pyresult = _PyObject_CallMethodIdOneArg(receiver, &PyId_athrow, v);
  FAIL_IF_NULL(pyresult);

  jsresult = python2js(pyresult);
  FAIL_IF_JS_ERROR(jsresult);

finally:
  Py_CLEAR(v);
  Py_CLEAR(asend);
  Py_CLEAR(pyresult);
  return jsresult;
}

EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_aiter_next(PyObject* aiterator)
{
  PyTypeObject* t;
  PyObject* awaitable;

  t = Py_TYPE(aiterator);
  if (t->tp_as_async == NULL || t->tp_as_async->am_anext == NULL) {
    PyErr_Format(
      PyExc_TypeError, "'%.200s' object is not an async iterator", t->tp_name);
    return JS_ERROR;
  }

  awaitable = (*t->tp_as_async->am_anext)(aiterator);
  if (awaitable == NULL) {
    return JS_ERROR;
  }
  JsVal result = python2js(awaitable);
  Py_CLEAR(awaitable);
  return result;
}

///////////////////////////////////////////////////////////////////////////////
//
// Await / "then" Implementation
//
// We want convert the object to a future with `ensure_future` and then make a
// promise that resolves when the future does. We can add a callback to the
// future with future.add_done_callback but we need to make a little python
// closure "FutureDoneCallback" that remembers how to resolve the promise.
//
// From JavaScript we will use the single function _pyproxy_ensure_future, the
// rest of this segment is helper functions for _pyproxy_ensure_future. The
// FutureDoneCallback object is never exposed to the user.

/**
 * A simple Callable python object. Intended to be called with a single argument
 * which is the future that was resolved.
 */
// clang-format off
typedef struct {
    PyObject_HEAD
    /** Will call this function with the result if the future succeeded */
    JsRef resolve_handle;
    /** Will call this function with the error if the future succeeded */
    JsRef reject_handle;
} FutureDoneCallback;
// clang-format on

static void
FutureDoneCallback_dealloc(FutureDoneCallback* self)
{
  hiwire_CLEAR(self->resolve_handle);
  hiwire_CLEAR(self->reject_handle);
  Py_TYPE(self)->tp_free((PyObject*)self);
}

/**
 * Helper method: if the future resolved successfully, call resolve_handle on
 * the result.
 */
int
FutureDoneCallback_call_resolve(FutureDoneCallback* self, PyObject* result)
{
  JsVal result_js = python2js(result);
  JsvFunction_Call_OneArg(hiwire_get(self->resolve_handle), result_js);
  // TODO: Should we really be just ignoring errors here??
  return 0;
}

/**
 * Helper method: if the future threw an error, call reject_handle on a
 * converted exception. The caller leaves the python error indicator set.
 */
int
FutureDoneCallback_call_reject(FutureDoneCallback* self)
{
  bool success = false;
  // wrap_exception looks up the current exception and wraps it in a Js error.
  JsVal excval = wrap_exception();
  FAIL_IF_JS_ERROR(excval);
  JsvFunction_Call_OneArg(hiwire_get(self->reject_handle), excval);
  // TODO: Should we really be just ignoring errors here??

  success = true;
finally:
  return success ? 0 : -1;
}

/**
 * Intended to be called with a single argument which is the future that was
 * resolved. Resolves the promise as appropriate based on the result of the
 * future.
 */
PyObject*
FutureDoneCallback_call(FutureDoneCallback* self,
                        PyObject* args,
                        PyObject* kwargs)
{
  PyObject* fut;
  if (!PyArg_UnpackTuple(args, "future_done_callback", 1, 1, &fut)) {
    return NULL;
  }
  PyObject* result = _PyObject_CallMethodIdNoArgs(fut, &PyId_result);
  int err;
  if (result != NULL) {
    err = FutureDoneCallback_call_resolve(self, result);
    Py_DECREF(result);
  } else {
    err = FutureDoneCallback_call_reject(self);
  }
  if (err == 0) {
    Py_RETURN_NONE;
  } else {
    return NULL;
  }
}

// clang-format off
static PyTypeObject FutureDoneCallbackType = {
    .tp_name = "FutureDoneCallback",
    .tp_doc = "Callback for internal use to allow awaiting a future from javascript",
    .tp_basicsize = sizeof(FutureDoneCallback),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_dealloc = (destructor) FutureDoneCallback_dealloc,
    .tp_call = (ternaryfunc) FutureDoneCallback_call,
};
// clang-format on

static PyObject*
FutureDoneCallback_cnew(JsVal resolve_handle, JsVal reject_handle)
{
  FutureDoneCallback* self =
    (FutureDoneCallback*)FutureDoneCallbackType.tp_alloc(
      &FutureDoneCallbackType, 0);
  self->resolve_handle = hiwire_new(resolve_handle);
  self->reject_handle = hiwire_new(reject_handle);
  return (PyObject*)self;
}

/**
 * Intended to be called with a single argument which is the future that was
 * resolved. Resolves the promise as appropriate based on the result of the
 * future.
 *
 * :param pyobject: An awaitable python object
 * :param resolve_handle: The resolve javascript method for a promise
 * :param reject_handle: The reject javascript method for a promise
 * :return: 0 on success, -1 on failure
 */
EMSCRIPTEN_KEEPALIVE int
_pyproxy_ensure_future(PyObject* pyobject,
                       JsVal resolve_handle,
                       JsVal reject_handle)
{
  bool success = false;
  PyObject* future = NULL;
  PyObject* callback = NULL;
  PyObject* retval = NULL;
  future = _PyObject_CallMethodIdOneArg(asyncio, &PyId_ensure_future, pyobject);
  FAIL_IF_NULL(future);
  callback = FutureDoneCallback_cnew(resolve_handle, reject_handle);
  retval =
    _PyObject_CallMethodIdOneArg(future, &PyId_add_done_callback, callback);
  FAIL_IF_NULL(retval);

  success = true;
finally:
  Py_CLEAR(future);
  Py_CLEAR(callback);
  Py_CLEAR(retval);
  return success ? 0 : -1;
}

///////////////////////////////////////////////////////////////////////////////
//
// Buffers
//

// For debug
size_t py_buffer_len_offset = offsetof(Py_buffer, len);
size_t py_buffer_shape_offset = offsetof(Py_buffer, shape);

/**
 * Convert a C array of Py_ssize_t to JavaScript.
 */
EM_JS(JsVal, array_to_js, (Py_ssize_t * array, int len), {
  return Array.from(HEAP32.subarray(array / 4, array / 4 + len));
})

// A macro to help us keep track of the fields we want to produce for the buffer
// info. We want to return a JavaScript object with these fields.
// You might write similar macros if you were not allowed to use structs...

// _pyproxy_get_buffer_result takes this set of arguments (with an extra
// sentinel to deal with the trailing comma problem). We declare a variable for
// each of these fields in _pyproxy_get_buffer and then the RESULT macro
// generates the call to _pyproxy_get_buffer_result which builds the JS object.
// This object is then destructured and used in pyproxy.ts.
// clang-format off
#define FIELDS(x)                                                               \
  FIELD(x)(void*, start_ptr)                                                    \
  FIELD(x)(void*, smallest_ptr)                                                 \
  FIELD(x)(void*, largest_ptr)                                                  \
  FIELD(x)(int, readonly)                                                       \
  FIELD(x)(char*, format)                                                       \
  FIELD(x)(int, itemsize)                                                       \
  FIELD(x)(JsVal, shape)                                                        \
  FIELD(x)(JsVal, strides)                                                      \
  FIELD(x)(Py_buffer*, view)                                                    \
  FIELD(x)(int, c_contiguous)                                                   \
  FIELD(x)(int, f_contiguous)                                                   \

#define FIELD(x) FIELD_ ## x

#define FIELD_argspec(a, b) a b,
#define FIELD_comma_separated(a, b) b,
#define FIELD_declarations(a, b) a b;

// We have to add an extra sentinel argument because C doesn't like trailing
// commas
#define ARGSPEC FIELDS(argspec)         int sentinel
#define ARGS    FIELDS(comma_separated) 0

EM_JS_MACROS(
JsVal,
_pyproxy_get_buffer_result,
(ARGSPEC),
{
  format = UTF8ToString(format);
  return { FIELDS(comma_separated) };
})
// clang-format on

#define RESULT _pyproxy_get_buffer_result(ARGS)

/**
 * This is the C part of the getBuffer method.
 *
 * We use PyObject_GetBuffer to acquire a Py_buffer view to the object, then we
 * determine the locations of: the first element of the buffer, the earliest
 * element of the buffer in memory the latest element of the buffer in memory
 * (plus one itemsize).
 *
 * We will use this information to slice out a subarray of the wasm heap that
 * contains all the memory inside of the buffer.
 *
 * Special care must be taken for negative strides, this is why we need to keep
 * track separately of start_ptr (the location of the first element of the
 * array) and smallest_ptr (the location of the earliest element of the array in
 * memory). If strides are positive, these are the same but if some strides are
 * negative they will be different.
 *
 * We put all the metadata about the buffer that we want to share into a JS
 * object and return it. Syncing up the C variables with the eventual JS array
 * we want to make is accomplished with the FIELDS macros.
 */
EMSCRIPTEN_KEEPALIVE JsVal
_pyproxy_get_buffer(PyObject* ptrobj)
{
  Py_buffer v;
  // PyBUF_RECORDS_RO requires that suboffsets be NULL but otherwise is the most
  // permissive possible request.
  if (PyObject_GetBuffer(ptrobj, &v, PyBUF_RECORDS_RO) == -1) {
    // Buffer cannot be represented without suboffsets. The bf_getbuffer method
    // should have set a PyExc_BufferError saying something to this effect.
    return JS_ERROR;
  }

  // The following declares a bunch of local variables. We need to fill them in
  // and use return RESULT; to return a JS object with this info.
  FIELDS(declarations);

  start_ptr = smallest_ptr = largest_ptr = v.buf;

  readonly = v.readonly;
  format = v.format;
  itemsize = v.itemsize;

  view = (Py_buffer*)PyMem_Malloc(sizeof(Py_buffer));
  *view = v;

  if (v.ndim == 0) {
    // "If ndim is 0, buf points to a single item representing a scalar. In this
    // case, shape, strides and suboffsets MUST be NULL."
    // https://docs.python.org/3/c-api/buffer.html#c.Py_buffer.ndim
    // all zero-dimensional arrays are both c_contiguous and f_contiguous.
    largest_ptr += v.itemsize;
    shape = JsvArray_New();
    strides = JsvArray_New();
    c_contiguous = true;
    f_contiguous = true;
    return RESULT;
  }

  // Because we requested PyBUF_RECORDS_RO I think we can assume that
  // v.shape != NULL.
  shape = array_to_js(v.shape, v.ndim);

  if (v.strides == NULL) {
    // In this case we are a C contiguous buffer
    largest_ptr += v.len;
    Py_ssize_t cstrides[v.ndim];
    PyBuffer_FillContiguousStrides(v.ndim, v.shape, cstrides, v.itemsize, 'C');
    c_contiguous = true;
    // 1d c_contiguous arrays are also f_contiguous
    f_contiguous = (v.ndim == 1);
    strides = array_to_js(cstrides, v.ndim);
    return RESULT;
  }

  if (v.len != 0) {
    // Have to be careful to ensure that we handle negative strides correctly.
    for (int i = 0; i < v.ndim; i++) {
      // v.strides[i] != 0
      if (v.strides[i] > 0) {
        // add positive strides to largest_ptr
        largest_ptr += v.strides[i] * (v.shape[i] - 1);
      } else {
        // subtract negative strides from smallest_ptr
        smallest_ptr += v.strides[i] * (v.shape[i] - 1);
      }
    }
    largest_ptr += v.itemsize;
  }

  strides = array_to_js(v.strides, v.ndim);
  c_contiguous = PyBuffer_IsContiguous(&v, 'C');
  f_contiguous = PyBuffer_IsContiguous(&v, 'F');
  return RESULT;
}
#undef FIELDS
#undef FIELD
#undef ARGSPEC
#undef ARGS
#undef RESULT

// clang-format off
EM_JS_VAL(JsVal,
pyproxy_new_ex,
(PyObject * ptrobj, bool capture_this, bool roundtrip, bool gcRegister, bool jsonAdaptor),
{
  return Module.pyproxy_new(ptrobj, {
    props: { captureThis: !!capture_this, roundtrip: !!roundtrip },
    gcRegister,
    jsonAdaptor
  });
});
// clang-format on

EM_JS_VAL(JsVal, pyproxy_new, (PyObject * ptrobj), {
  return Module.pyproxy_new(ptrobj);
});

/**
 * Create a JsRef which can be called once, wrapping a Python callable. The
 * JsRef owns a reference to the Python callable until it is called, then
 * releases it. Useful for the "finally" wrapper on a JsProxy of a promise, and
 * also exposed in the pyodide Python module.
 */
EM_JS_VAL(JsVal, create_once_callable, (PyObject * obj, bool may_syncify), {
  _Py_IncRef(obj);
  let alreadyCalled = false;
  function wrapper(... args)
  {
    if (alreadyCalled) {
      throw new Error("OnceProxy can only be called once");
    }
    try {
      if (may_syncify) {
        return Module.callPyObjectMaybePromising(obj, args);
      } else {
        return Module.callPyObject(obj, args);
      }
    } finally {
      wrapper.destroy();
    }
  }
  wrapper.destroy = function()
  {
    if (alreadyCalled) {
      throw new Error("OnceProxy has already been destroyed");
    }
    alreadyCalled = true;
    Module.finalizationRegistry.unregister(wrapper);
    _Py_DecRef(obj);
  };
  Module.finalizationRegistry.register(wrapper, [ obj, undefined ], wrapper);
  return wrapper;
});

static PyObject*
create_once_callable_py(PyObject* _mod,
                        PyObject* const* args,
                        Py_ssize_t nargs,
                        PyObject* kwnames)
{
  static const char* const _keywords[] = { "", "_may_syncify", 0 };
  bool may_syncify = false;
  PyObject* obj;
  static struct _PyArg_Parser _parser = {
    .format = "O|$p:create_once_callable",
    .keywords = _keywords,
  };
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &obj, &may_syncify)) {
    return NULL;
  }
  JsVal v = create_once_callable(obj, may_syncify);
  return JsProxy_create(v);
}

// clang-format off

EMSCRIPTEN_KEEPALIVE int
create_promise_handles_result_helper(PyObject* handle_result, PyObject* converter, JsVal jsval) {
  bool success = false;
  PyObject* pyval = NULL;
  PyObject* result = NULL;

  if (converter == NULL || Py_IsNone(converter)) {
    pyval = js2python(jsval);
  } else {
    pyval = Js2PyConverter_convert(converter, jsval, JS_ERROR);
  }
  FAIL_IF_NULL(pyval);
  result = PyObject_CallOneArg(handle_result, pyval);
  FAIL_IF_NULL(result);

  success = true;
finally:
  Py_CLEAR(pyval);
  Py_CLEAR(result);
  if (!success) {
    // Not sure what we'll do if this function fails tbh...
    printf("Unexpected error:\n");
    PyErr_Print();
  }
  return success ? 0 : -1;
}

/**
 * Arguments:
 *  handle_result -- Python callable expecting one argument, called with the
 *  result if the promise is resolved. Can be NULL.
 *
 *  handle_exception -- Python callable expecting one argument, called with the
 *  exception if the promise is rejected. Can be NULL.
 *
 *  done_callback_id -- A JsRef to a JavaScript callback to be called when the
 *  promise is either resolved or rejected. Can be NULL.
 *
 * Returns: a JsRef to a pair [onResolved, onRejected].
 *
 * The purpose of this function is to handle memory management when attaching
 * Python functions to Promises. This function stores a reference to both
 * handle_result and handle_exception, and frees both when either onResolved or
 * onRejected is called. Of course if the Promise never resolves then the
 * handles will be leaked. We can't use create_once_callable because either
 * onResolved or onRejected is called but not both. In either case, we release
 * both functions.
 *
 * The return values are intended to be attached to a promise e.g.,
 * some_promise.then(onResolved, onRejected).
 */
EM_JS_VAL(JsVal, create_promise_handles, (
  PyObject* handle_result,
  PyObject* handle_exception,
  JsVal done_callback,
  PyObject* js2py_converter
), {
  // At some point it would be nice to use FinalizationRegistry with these, but
  // it's a bit tricky.
  if (handle_result) {
    _Py_IncRef(handle_result);
  }
  if (handle_exception) {
    _Py_IncRef(handle_exception);
  }
  if (js2py_converter) {
    _Py_IncRef(js2py_converter);
  }
  if (!done_callback) {
    done_callback = (x) => {};
  }
  let used = false;
  function checkUsed(){
    if (used) {
      throw new Error("One of the promise handles has already been called.");
    }
  }
  function destroy(){
    checkUsed();
    used = true;
    if(handle_result){
      _Py_DecRef(handle_result);
    }
    if(handle_exception){
      _Py_DecRef(handle_exception);
    }
    if (js2py_converter) {
      _Py_DecRef(js2py_converter);
    }
  }
  function onFulfilled(res) {
    checkUsed();
    try {
      if (handle_result) {
        // MaybePromising??
        return _create_promise_handles_result_helper(handle_result, js2py_converter, res);
      }
    } finally {
      done_callback(res);
      destroy();
    }
  }
  function onRejected(err) {
    checkUsed();
    try {
      if(handle_exception){
        return Module.callPyObjectMaybePromising(handle_exception, [err]);
      }
    } finally {
      done_callback(undefined);
      destroy();
    }
  }
  onFulfilled.destroy = destroy;
  onRejected.destroy = destroy;
  return [onFulfilled, onRejected];
})
// clang-format on

static PyObject*
create_proxy(PyObject* self,
             PyObject* const* args,
             Py_ssize_t nargs,
             PyObject* kwnames)
{
  static const char* const _keywords[] = { "", "capture_this", "roundtrip", 0 };
  bool capture_this = false;
  bool roundtrip = true;
  PyObject* obj;
  static struct _PyArg_Parser _parser = {
    .format = "O|$pp:create_proxy",
    .keywords = _keywords,
  };
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &obj, &capture_this, &roundtrip)) {
    return NULL;
  }
  return JsProxy_create(
    pyproxy_new_ex(obj, capture_this, roundtrip, true, false));
}

static PyMethodDef methods[] = {
  {
    "create_once_callable",
    (PyCFunction)create_once_callable_py,
    METH_FASTCALL | METH_KEYWORDS,
  },
  {
    "create_proxy",
    (PyCFunction)create_proxy,
    METH_FASTCALL | METH_KEYWORDS,
  },
  { NULL } /* Sentinel */
};

int
pyproxy_init(PyObject* core)
{
  bool success = false;

  PyObject* collections_abc = NULL;
  PyObject* docstring_source = NULL;
  PyObject* inspect = NULL;

  collections_abc = PyImport_ImportModule("collections.abc");
  FAIL_IF_NULL(collections_abc);
  Generator = PyObject_GetAttrString(collections_abc, "Generator");
  FAIL_IF_NULL(Generator);
  AsyncGenerator = PyObject_GetAttrString(collections_abc, "AsyncGenerator");
  FAIL_IF_NULL(AsyncGenerator);
  Sequence = PyObject_GetAttrString(collections_abc, "Sequence");
  FAIL_IF_NULL(Sequence);
  MutableSequence = PyObject_GetAttrString(collections_abc, "MutableSequence");
  FAIL_IF_NULL(MutableSequence);

  docstring_source = PyImport_ImportModule("_pyodide._core_docs");
  FAIL_IF_NULL(docstring_source);
  FAIL_IF_MINUS_ONE(
    add_methods_and_set_docstrings(core, methods, docstring_source));
  asyncio = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio);
  FAIL_IF_MINUS_ONE(PyType_Ready(&FutureDoneCallbackType));

  inspect = PyImport_ImportModule("inspect");
  FAIL_IF_NULL(inspect);
  iscoroutinefunction = PyObject_GetAttrString(inspect, "iscoroutinefunction");
  FAIL_IF_NULL(iscoroutinefunction);

  dict_flags = type_getflags(&PyDict_Type);
  tuple_flags = type_getflags(&PyTuple_Type);
  list_flags = type_getflags(&PyList_Type);

  success = true;
finally:
  Py_CLEAR(docstring_source);
  Py_CLEAR(collections_abc);
  Py_CLEAR(inspect);
  return success ? 0 : -1;
}
