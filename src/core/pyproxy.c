#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "error_handling.h"
#include <emscripten.h>

#include "docstring.h"
#include "hiwire.h"
#include "js2python.h"
#include "jsmemops.h" // for pyproxy.js
#include "jsproxy.h"
#include "pyproxy.h"
#include "python2js.h"

#define Py_ENTER() _check_gil()
#define Py_EXIT()

EM_JS(void, throw_no_gil, (), {
  throw new API.NoGilError("Attempted to use PyProxy when Python GIL not held");
});

void
check_gil()
{
  if (!PyGILState_Check()) {
    throw_no_gil();
  }
}

PyObject* Generator;
PyObject* AsyncGenerator;

_Py_IDENTIFIER(result);
_Py_IDENTIFIER(ensure_future);
_Py_IDENTIFIER(add_done_callback);
_Py_IDENTIFIER(asend);
_Py_IDENTIFIER(throw);
_Py_IDENTIFIER(athrow);

// Use raw EM_JS for the next five commands. We intend to signal a fatal error
// if a JavaScript error is thrown.

EM_JS(int, pyproxy_Check, (JsRef x), {
  if (x == 0) {
    return false;
  }
  let val = Hiwire.get_value(x);
  return API.isPyProxy(val);
});

EM_JS(PyObject*, pyproxy_AsPyObject, (JsRef x), {
  if (x == 0) {
    return 0;
  }
  let val = Hiwire.get_value(x);
  if (!API.isPyProxy(val)) {
    return 0;
  }
  return Module.PyProxy_getPtr(val);
});

EM_JS(void, destroy_proxies, (JsRef proxies_id, char* msg_ptr), {
  let msg = undefined;
  if (msg_ptr) {
    msg = UTF8ToString(msg_ptr);
  }
  let proxies = Hiwire.get_value(proxies_id);
  for (let px of proxies) {
    Module.pyproxy_destroy(px, msg, false);
  }
});

EM_JS(void, destroy_proxy, (JsRef proxy_id, char* msg_ptr), {
  let px = Module.hiwire.get_value(proxy_id);
  if (px.$$props.roundtrip) {
    // Don't destroy roundtrip proxies!
    return;
  }
  let msg = undefined;
  if (msg_ptr) {
    msg = UTF8ToString(msg_ptr);
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
// clang-format on

// Taken from genobject.c
// For checking whether an object is awaitable.
static int
gen_is_coroutine(PyObject* o)
{
  if (PyGen_CheckExact(o)) {
    PyCodeObject* code = (PyCodeObject*)((PyGenObject*)o)->gi_code;
    if (code->co_flags & CO_ITERABLE_COROUTINE) {
      return 1;
    }
  }
  return 0;
}

/**
 * Do introspection on the python object to work out which abstract protocols it
 * supports. Most of these tests are taken from a corresponding abstract Object
 * protocol API defined in `abstract.c`. We wrote these tests to check whether
 * the corresponding CPython APIs are likely to work without actually creating
 * any temporary objects.
 */
int
pyproxy_getflags(PyObject* pyobj)
{
  // Reduce casework by ensuring that protos aren't NULL.
  PyTypeObject* obj_type = pyobj->ob_type;

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
  } else if (PyType_Check(pyobj)) {
    _Py_IDENTIFIER(__class_getitem__);
    PyObject* oname = _PyUnicode_FromId(&PyId___class_getitem__); /* borrowed */
    if (PyObject_HasAttr(pyobj, oname)) {
      result |= HAS_GET;
    }
  }
  // PyObject_SetItem
  SET_FLAG_IF(HAS_SET, map_proto->mp_ass_subscript || seq_proto->sq_ass_item);
  // PySequence_Contains
  SET_FLAG_IF(HAS_CONTAINS, seq_proto->sq_contains);
  // PyObject_GetIter
  SET_FLAG_IF(IS_ITERABLE, obj_type->tp_iter || PySequence_Check(pyobj));
  SET_FLAG_IF(IS_ASYNC_ITERABLE, async_proto->am_aiter);
  if (PyIter_Check(pyobj)) {
    result &= ~IS_ITERABLE;
    result |= IS_ITERATOR;
  }
  if (async_proto->am_anext) {
    result &= ~IS_ASYNC_ITERABLE;
    result |= IS_ASYNC_ITERATOR;
  }

  int isgen = PyObject_IsInstance(pyobj, Generator);
  FAIL_IF_MINUS_ONE(isgen);
  int isasyncgen = PyObject_IsInstance(pyobj, AsyncGenerator);
  FAIL_IF_MINUS_ONE(isasyncgen);
  SET_FLAG_IF(IS_GENERATOR, isgen);
  SET_FLAG_IF(IS_ASYNC_GENERATOR, isasyncgen);

  // There's no CPython API that corresponds directly to the "await" keyword.
  // Looking at disassembly, "await" translates into opcodes GET_AWAITABLE and
  // YIELD_FROM. GET_AWAITABLE uses _PyCoro_GetAwaitableIter defined in
  // genobject.c. This tests whether _PyCoro_GetAwaitableIter is likely to
  // succeed.
  SET_FLAG_IF(IS_AWAITABLE, async_proto->am_await || gen_is_coroutine(pyobj));
  SET_FLAG_IF(IS_BUFFER, buffer_proto->bf_getbuffer);
  // PyObject_Call (from call.c)
  SET_FLAG_IF(IS_CALLABLE,
              _PyVectorcall_Function(pyobj) || PyCFunction_Check(pyobj) ||
                obj_type->tp_call);

#undef SET_FLAG_IF

  success = true;
finally:
  return success ? result : -1;
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

JsRef
_pyproxy_repr(PyObject* pyobj)
{
  PyObject* repr_py = NULL;
  JsRef repr_js = NULL;

  repr_py = PyObject_Repr(pyobj);
  FAIL_IF_NULL(repr_py);
  repr_js = python2js(repr_py);

finally:
  Py_CLEAR(repr_py);
  return repr_js;
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
JsRef
_pyproxy_type(PyObject* ptrobj)
{
  return hiwire_string_utf8(ptrobj->ob_type->tp_name);
}

int
_pyproxy_hasattr(PyObject* pyobj, JsRef idkey)
{
  PyObject* pykey = NULL;
  int result = -1;

  pykey = js2python(idkey);
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

EM_JS(JsRef, proxy_cache_get, (JsRef proxyCacheId, PyObject* descr), {
  let proxyCache = Hiwire.get_value(proxyCacheId);
  let proxyId = proxyCache.get(descr);
  if (!proxyId) {
    return undefined;
  }
  // Okay found a proxy. Is it alive?
  if (Hiwire.get_value(proxyId).$$.ptr) {
    return proxyId;
  } else {
    // It's dead, tidy up
    proxyCache.delete(descr);
    Hiwire.decref(proxyId);
    return undefined;
  }
})

// clang-format off
EM_JS(void,
proxy_cache_set,
(JsRef proxyCacheId, PyObject* descr, JsRef proxy), {
  let proxyCache = Hiwire.get_value(proxyCacheId);
  proxyCache.set(descr, proxy);
})
// clang-format on

JsRef
_pyproxy_getattr(PyObject* pyobj, JsRef idkey, JsRef proxyCache)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pydescr = NULL;
  PyObject* pyresult = NULL;
  JsRef idresult = NULL;

  pykey = js2python(idkey);
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
  JsRef cached_proxy = proxy_cache_get(proxyCache, pydescr); /* borrowed */
  if (cached_proxy) {
    idresult = hiwire_incref(cached_proxy);
    goto success;
  }
  if (PyErr_Occurred()) {
    FAIL();
  }
  if (is_method) {
    pyresult =
      Py_TYPE(pydescr)->tp_descr_get(pydescr, pyobj, (PyObject*)pyobj->ob_type);
    FAIL_IF_NULL(pyresult);
  } else {
    pyresult = pydescr;
    Py_INCREF(pydescr);
  }
  idresult = python2js(pyresult);
  FAIL_IF_NULL(idresult);
  if (pyproxy_Check(idresult)) {
    // If a getter returns a different object every time, this could potentially
    // fill up the cache with a lot of junk. If this is a problem, the user will
    // have to manually destroy the attributes.
    proxy_cache_set(proxyCache, pydescr, hiwire_incref(idresult));
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
    hiwire_CLEAR(idresult);
  }
  return idresult;
};

int
_pyproxy_setattr(PyObject* pyobj, JsRef idkey, JsRef idval)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pyval = NULL;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  pyval = js2python(idval);
  FAIL_IF_NULL(pyval);
  FAIL_IF_MINUS_ONE(PyObject_SetAttr(pyobj, pykey, pyval));

  success = true;
finally:
  Py_CLEAR(pykey);
  Py_CLEAR(pyval);
  return success ? 0 : -1;
}

int
_pyproxy_delattr(PyObject* pyobj, JsRef idkey)
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

JsRef
_pyproxy_getitem(PyObject* pyobj, JsRef idkey)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pyresult = NULL;
  JsRef result = NULL;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  pyresult = PyObject_GetItem(pyobj, pykey);
  FAIL_IF_NULL(pyresult);
  result = python2js(pyresult);
  FAIL_IF_NULL(result);

  success = true;
finally:
  if (!success && (PyErr_ExceptionMatches(PyExc_KeyError) ||
                   PyErr_ExceptionMatches(PyExc_IndexError))) {
    PyErr_Clear();
  }
  Py_CLEAR(pykey);
  Py_CLEAR(pyresult);
  if (!success) {
    hiwire_CLEAR(result);
  }
  return result;
};

int
_pyproxy_setitem(PyObject* pyobj, JsRef idkey, JsRef idval)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pyval = NULL;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  pyval = js2python(idval);
  FAIL_IF_NULL(pyval);
  FAIL_IF_MINUS_ONE(PyObject_SetItem(pyobj, pykey, pyval));

  success = true;
finally:
  Py_CLEAR(pykey);
  Py_CLEAR(pyval);
  return success ? 0 : -1;
}

int
_pyproxy_delitem(PyObject* pyobj, JsRef idkey)
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

int
_pyproxy_contains(PyObject* pyobj, JsRef idkey)
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

JsRef
_pyproxy_ownKeys(PyObject* pyobj)
{
  bool success = false;
  PyObject* pydir = NULL;
  JsRef iddir = NULL;
  JsRef identry = NULL;

  pydir = PyObject_Dir(pyobj);
  FAIL_IF_NULL(pydir);

  iddir = JsArray_New();
  FAIL_IF_NULL(iddir);
  Py_ssize_t n = PyList_Size(pydir);
  FAIL_IF_MINUS_ONE(n);
  for (Py_ssize_t i = 0; i < n; ++i) {
    PyObject* pyentry = PyList_GetItem(pydir, i); /* borrowed */
    identry = python2js(pyentry);
    FAIL_IF_NULL(identry);
    FAIL_IF_MINUS_ONE(JsArray_Push(iddir, identry));
    hiwire_CLEAR(identry);
  }

  success = true;
finally:
  Py_CLEAR(pydir);
  hiwire_CLEAR(identry);
  if (!success) {
    hiwire_CLEAR(iddir);
  }
  return iddir;
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
JsRef
_pyproxy_apply(PyObject* callable,
               JsRef jsargs,
               size_t numposargs,
               JsRef jskwnames,
               size_t numkwargs)
{
  size_t total_args = numposargs + numkwargs;
  size_t last_converted_arg = total_args;
  JsRef jsitem = NULL;
  PyObject* pyargs_array[total_args + 1];
  PyObject** pyargs = pyargs_array;
  pyargs++; // leave a space for self argument in case callable is a bound
            // method
  PyObject* pykwnames = NULL;
  PyObject* pyresult = NULL;
  JsRef idresult = NULL;

  // Put both arguments and keyword arguments into pyargs
  for (Py_ssize_t i = 0; i < total_args; ++i) {
    jsitem = JsArray_Get(jsargs, i);
    // pyitem is moved into pyargs so we don't need to clear it later.
    PyObject* pyitem = js2python(jsitem);
    if (pyitem == NULL) {
      last_converted_arg = i;
      FAIL();
    }
    pyargs[i] = pyitem; // pyitem is moved into pyargs.
    hiwire_CLEAR(jsitem);
  }
  if (numkwargs > 0) {
    // Put names of keyword arguments into a tuple
    pykwnames = PyTuple_New(numkwargs);
    for (Py_ssize_t i = 0; i < numkwargs; i++) {
      jsitem = JsArray_Get(jskwnames, i);
      // pyitem is moved into pykwargs so we don't need to clear it later.
      PyObject* pyitem = js2python(jsitem);
      PyTuple_SET_ITEM(pykwnames, i, pyitem);
      hiwire_CLEAR(jsitem);
    }
  }
  // Tell callee that we left space for a self argument
  size_t nargs_with_flag = numposargs | PY_VECTORCALL_ARGUMENTS_OFFSET;
  pyresult = _PyObject_Vectorcall(callable, pyargs, nargs_with_flag, pykwnames);
  FAIL_IF_NULL(pyresult);
  idresult = python2js(pyresult);
  FAIL_IF_NULL(idresult);

finally:
  hiwire_CLEAR(jsitem);
  // If we failed to convert one of the arguments, then pyargs is partially
  // uninitialized. Only clear the part that actually has stuff in it.
  for (Py_ssize_t i = 0; i < last_converted_arg; i++) {
    Py_CLEAR(pyargs[i]);
  }
  Py_CLEAR(pyresult);
  Py_CLEAR(pykwnames);
  return idresult;
}

JsRef
_pyproxy_iter_next(PyObject* iterator)
{
  PyObject* item = PyIter_Next(iterator);
  if (item == NULL) {
    return NULL;
  }
  JsRef result = python2js(item);
  Py_CLEAR(item);
  return result;
}

PySendResult
_pyproxyGen_Send(PyObject* receiver, JsRef jsval, JsRef* result)
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
  *result = python2js(retval);
  FAIL_IF_NULL(*result);

  success = true;
finally:
  Py_CLEAR(v);
  Py_CLEAR(retval);
  if (!success) {
    status = PYGEN_ERROR;
  }
  return status;
}

PySendResult
_pyproxyGen_return(PyObject* receiver, JsRef jsval, JsRef* result)
{
  bool success = false;
  PySendResult status = PYGEN_ERROR;
  PyObject* pyresult;

  // Throw GeneratorExit into generator
  pyresult =
    _PyObject_CallMethodIdOneArg(receiver, &PyId_throw, PyExc_GeneratorExit);
  if (pyresult == NULL) {
    if (PyErr_ExceptionMatches(PyExc_GeneratorExit)) {
      // If GeneratorExit comes back out, return original value.
      PyErr_Clear();
      status = PYGEN_RETURN;
      hiwire_incref(jsval);
      *result = jsval;
      success = true;
      goto finally;
    }
    //
    FAIL_IF_MINUS_ONE(_PyGen_FetchStopIterationValue(&pyresult));
    status = PYGEN_RETURN;
  } else {
    status = PYGEN_NEXT;
  }
  *result = python2js(pyresult);
  FAIL_IF_NULL(*result);
  success = true;
finally:
  if (!success) {
    status = PYGEN_ERROR;
  }
  Py_CLEAR(pyresult);
  return status;
}

PySendResult
_pyproxyGen_throw(PyObject* receiver, JsRef jsval, JsRef* result)
{
  bool success = false;
  PyObject* pyvalue = NULL;
  PyObject* pyresult = NULL;
  PySendResult status = PYGEN_ERROR;

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
  *result = python2js(pyresult);
  FAIL_IF_NULL(*result);
  success = true;
finally:
  if (!success) {
    status = PYGEN_ERROR;
  }
  Py_CLEAR(pyresult);
  Py_CLEAR(pyvalue);
  return status;
}

JsRef
_pyproxyGen_asend(PyObject* receiver, JsRef jsval)
{
  PyObject* v = NULL;
  PyObject* asend = NULL;
  PyObject* pyresult = NULL;
  JsRef jsresult = NULL;

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
      return NULL;
    }
    pyresult = (*t->tp_as_async->am_anext)(receiver);
  }
  FAIL_IF_NULL(pyresult);

  jsresult = python2js(pyresult);
  FAIL_IF_NULL(jsresult);

finally:
  Py_CLEAR(v);
  Py_CLEAR(asend);
  Py_CLEAR(pyresult);
  return jsresult;
}

JsRef
_pyproxyGen_areturn(PyObject* receiver)
{
  PyObject* v = NULL;
  PyObject* asend = NULL;
  PyObject* pyresult = NULL;
  JsRef jsresult = NULL;

  pyresult =
    _PyObject_CallMethodIdOneArg(receiver, &PyId_athrow, PyExc_GeneratorExit);
  FAIL_IF_NULL(pyresult);

  jsresult = python2js(pyresult);
  FAIL_IF_NULL(jsresult);

finally:
  Py_CLEAR(v);
  Py_CLEAR(asend);
  Py_CLEAR(pyresult);
  return jsresult;
}

JsRef
_pyproxyGen_athrow(PyObject* receiver, JsRef jsval)
{
  PyObject* v = NULL;
  PyObject* asend = NULL;
  PyObject* pyresult = NULL;
  JsRef jsresult = NULL;

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
  FAIL_IF_NULL(jsresult);

finally:
  Py_CLEAR(v);
  Py_CLEAR(asend);
  Py_CLEAR(pyresult);
  return jsresult;
}

JsRef
_pyproxy_aiter_next(PyObject* aiterator)
{
  PyTypeObject* t;
  PyObject* awaitable;

  t = Py_TYPE(aiterator);
  if (t->tp_as_async == NULL || t->tp_as_async->am_anext == NULL) {
    PyErr_Format(
      PyExc_TypeError, "'%.200s' object is not an async iterator", t->tp_name);
    return NULL;
  }

  awaitable = (*t->tp_as_async->am_anext)(aiterator);
  if (awaitable == NULL) {
    return NULL;
  }
  JsRef result = python2js(awaitable);
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
  JsRef result_js = NULL;
  JsRef output = NULL;
  result_js = python2js(result);
  output = hiwire_call_OneArg(self->resolve_handle, result_js);

  hiwire_CLEAR(result_js);
  hiwire_CLEAR(output);
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
  JsRef excval = NULL;
  JsRef result = NULL;
  // wrap_exception looks up the current exception and wraps it in a Js error.
  excval = wrap_exception();
  FAIL_IF_NULL(excval);
  result = hiwire_call_OneArg(self->reject_handle, excval);

  success = true;
finally:
  hiwire_CLEAR(excval);
  hiwire_CLEAR(result);
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
  int errcode;
  if (result != NULL) {
    errcode = FutureDoneCallback_call_resolve(self, result);
    Py_DECREF(result);
  } else {
    errcode = FutureDoneCallback_call_reject(self);
  }
  if (errcode == 0) {
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
FutureDoneCallback_cnew(JsRef resolve_handle, JsRef reject_handle)
{
  FutureDoneCallback* self =
    (FutureDoneCallback*)FutureDoneCallbackType.tp_alloc(
      &FutureDoneCallbackType, 0);
  self->resolve_handle = hiwire_incref(resolve_handle);
  self->reject_handle = hiwire_incref(reject_handle);
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
int
_pyproxy_ensure_future(PyObject* pyobject,
                       JsRef resolve_handle,
                       JsRef reject_handle)
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
EM_JS(JsRef, array_to_js, (Py_ssize_t * array, int len), {
  return Hiwire.new_value(
    Array.from(HEAP32.subarray(array / 4, array / 4 + len)));
})

// The order of these fields has to match the code in getBuffer
typedef struct
{
  // where is the first entry buffer[0]...[0] (ndim times)?
  void* start_ptr;
  // Where is the earliest location in buffer? (If all strides are positive,
  // this equals start_ptr)
  void* smallest_ptr;
  // What is the last location in the buffer (plus one)
  void* largest_ptr;

  int readonly;
  char* format;
  int itemsize;
  JsRef shape;
  JsRef strides;

  Py_buffer* view;
  int c_contiguous;
  int f_contiguous;
} buffer_struct;

size_t buffer_struct_size = sizeof(buffer_struct);

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
 * We also put the various other metadata about the buffer that we want to share
 * into buffer_struct.
 */
int
_pyproxy_get_buffer(buffer_struct* target, PyObject* ptrobj)
{
  Py_buffer view;
  // PyBUF_RECORDS_RO requires that suboffsets be NULL but otherwise is the most
  // permissive possible request.
  if (PyObject_GetBuffer(ptrobj, &view, PyBUF_RECORDS_RO) == -1) {
    // Buffer cannot be represented without suboffsets. The bf_getbuffer method
    // should have set a PyExc_BufferError saying something to this effect.
    return -1;
  }

  buffer_struct result = { 0 };
  result.start_ptr = result.smallest_ptr = result.largest_ptr = view.buf;
  result.readonly = view.readonly;

  result.format = view.format;
  result.itemsize = view.itemsize;

  if (view.ndim == 0) {
    // "If ndim is 0, buf points to a single item representing a scalar. In this
    // case, shape, strides and suboffsets MUST be NULL."
    // https://docs.python.org/3/c-api/buffer.html#c.Py_buffer.ndim
    result.largest_ptr += view.itemsize;
    result.shape = JsArray_New();
    result.strides = JsArray_New();
    result.c_contiguous = true;
    result.f_contiguous = true;
    goto success;
  }

  // Because we requested PyBUF_RECORDS_RO I think we can assume that
  // view.shape != NULL.
  result.shape = array_to_js(view.shape, view.ndim);

  if (view.strides == NULL) {
    // In this case we are a C contiguous buffer
    result.largest_ptr += view.len;
    Py_ssize_t strides[view.ndim];
    PyBuffer_FillContiguousStrides(
      view.ndim, view.shape, strides, view.itemsize, 'C');
    result.strides = array_to_js(strides, view.ndim);
    goto success;
  }

  if (view.len != 0) {
    // Have to be careful to ensure that we handle negative strides correctly.
    for (int i = 0; i < view.ndim; i++) {
      // view.strides[i] != 0
      if (view.strides[i] > 0) {
        // add positive strides to largest_ptr
        result.largest_ptr += view.strides[i] * (view.shape[i] - 1);
      } else {
        // subtract negative strides from smallest_ptr
        result.smallest_ptr += view.strides[i] * (view.shape[i] - 1);
      }
    }
    result.largest_ptr += view.itemsize;
  }

  result.strides = array_to_js(view.strides, view.ndim);
  result.c_contiguous = PyBuffer_IsContiguous(&view, 'C');
  result.f_contiguous = PyBuffer_IsContiguous(&view, 'F');

success:
  // The result.view memory will be freed when (if?) the user calls
  // Py_Buffer.release().
  result.view = (Py_buffer*)PyMem_Malloc(sizeof(Py_buffer));
  *result.view = view;
  *target = result;
  return 0;
}

EM_JS_REF(JsRef,
          pyproxy_new_ex,
          (PyObject * ptrobj, bool capture_this, bool roundtrip),
          {
            return Hiwire.new_value(Module.pyproxy_new(ptrobj, {
              props : { captureThis : !!capture_this, roundtrip : !!roundtrip }
            }));
          });

EM_JS_REF(JsRef, pyproxy_new, (PyObject * ptrobj), {
  return Hiwire.new_value(Module.pyproxy_new(ptrobj));
});

/**
 * Create a JsRef which can be called once, wrapping a Python callable. The
 * JsRef owns a reference to the Python callable until it is called, then
 * releases it. Useful for the "finally" wrapper on a JsProxy of a promise, and
 * also exposed in the pyodide Python module.
 */
EM_JS_REF(JsRef, create_once_callable, (PyObject * obj), {
  _Py_IncRef(obj);
  let alreadyCalled = false;
  function wrapper(... args)
  {
    if (alreadyCalled) {
      throw new Error("OnceProxy can only be called once");
    }
    try {
      return Module.callPyObject(obj, args);
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
  return Hiwire.new_value(wrapper);
});

static PyObject*
create_once_callable_py(PyObject* _mod, PyObject* obj)
{
  JsRef ref = create_once_callable(obj);
  PyObject* result = JsProxy_create(ref);
  hiwire_decref(ref);
  return result;
}

// clang-format off

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
EM_JS_REF(JsRef, create_promise_handles, (
  PyObject* handle_result, PyObject* handle_exception, JsRef done_callback_id
), {
  // At some point it would be nice to use FinalizationRegistry with these, but
  // it's a bit tricky.
  if (handle_result) {
    _Py_IncRef(handle_result);
  }
  if (handle_exception) {
    _Py_IncRef(handle_exception);
  }
  let done_callback = (x) => {};
  if(done_callback_id){
    done_callback = Hiwire.get_value(done_callback_id);
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
      _Py_DecRef(handle_exception)
    }
  }
  function onFulfilled(res) {
    checkUsed();
    try {
      if(handle_result){
        return Module.callPyObject(handle_result, [res]);
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
        return Module.callPyObject(handle_exception, [err]);
      }
    } finally {
      done_callback(undefined);
      destroy();
    }
  }
  onFulfilled.destroy = destroy;
  onRejected.destroy = destroy;
  return Hiwire.new_value(
    [onFulfilled, onRejected]
  );
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
  static struct _PyArg_Parser _parser = { "O|$pp:create_proxy", _keywords, 0 };
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &obj, &capture_this, &roundtrip)) {
    return NULL;
  }

  JsRef ref = pyproxy_new_ex(obj, capture_this, roundtrip);
  PyObject* result = JsProxy_create(ref);
  hiwire_decref(ref);
  return result;
}

static PyMethodDef methods[] = {
  {
    "create_once_callable",
    create_once_callable_py,
    METH_O,
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

  collections_abc = PyImport_ImportModule("collections.abc");
  FAIL_IF_NULL(collections_abc);
  Generator = PyObject_GetAttrString(collections_abc, "Generator");
  FAIL_IF_NULL(Generator);
  AsyncGenerator = PyObject_GetAttrString(collections_abc, "AsyncGenerator");
  FAIL_IF_NULL(AsyncGenerator);

  docstring_source = PyImport_ImportModule("_pyodide._core_docs");
  FAIL_IF_NULL(docstring_source);
  FAIL_IF_MINUS_ONE(
    add_methods_and_set_docstrings(core, methods, docstring_source));
  asyncio = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio);
  FAIL_IF_MINUS_ONE(PyType_Ready(&FutureDoneCallbackType));

  success = true;
finally:
  Py_CLEAR(docstring_source);
  Py_CLEAR(collections_abc);
  return success ? 0 : -1;
}
