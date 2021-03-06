#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

_Py_IDENTIFIER(result);
_Py_IDENTIFIER(ensure_future);
_Py_IDENTIFIER(add_done_callback);

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

  int result = 0;
  // PyObject_Size
  if (seq_proto->sq_length || map_proto->mp_length) {
    result |= HAS_LENGTH;
  }
  // PyObject_GetItem
  if (map_proto->mp_subscript || seq_proto->sq_item) {
    result |= HAS_GET;
  } else if (PyType_Check(pyobj)) {
    _Py_IDENTIFIER(__class_getitem__);
    if (_PyObject_HasAttrId(pyobj, &PyId___class_getitem__)) {
      result |= HAS_GET;
    }
  }
  // PyObject_SetItem
  if (map_proto->mp_ass_subscript || seq_proto->sq_ass_item) {
    result |= HAS_SET;
  }
  // PySequence_Contains
  if (seq_proto->sq_contains) {
    result |= HAS_CONTAINS;
  }
  // PyObject_GetIter
  if (obj_type->tp_iter || PySequence_Check(pyobj)) {
    result |= IS_ITERABLE;
  }
  if (PyIter_Check(pyobj)) {
    result &= ~IS_ITERABLE;
    result |= IS_ITERATOR;
  }
  // There's no CPython API that corresponds directly to the "await" keyword.
  // Looking at disassembly, "await" translates into opcodes GET_AWAITABLE and
  // YIELD_FROM. GET_AWAITABLE uses _PyCoro_GetAwaitableIter defined in
  // genobject.c. This tests whether _PyCoro_GetAwaitableIter is likely to
  // succeed.
  if (async_proto->am_await || gen_is_coroutine(pyobj)) {
    result |= IS_AWAITABLE;
  }
  if (buffer_proto->bf_getbuffer) {
    result |= IS_BUFFER;
  }
  // PyObject_Call (from call.c)
  if (_PyVectorcall_Function(pyobj) || PyCFunction_Check(pyobj) ||
      obj_type->tp_call) {
    result |= IS_CALLABLE;
  }
  return result;
}

///////////////////////////////////////////////////////////////////////////////
//
// Object protocol wrappers
//
// This section defines wrappers for Python Object protocol API calls that we
// are planning to offer on the PyProxy. Much of this could be written in
// Javascript instead. Some reasons to do it in C:
//  1. Some CPython APIs are actually secretly macros which cannot be used from
//     Javascript.
//  2. The code is a bit more concise in C.
//  3. It may be preferable to minimize the number of times we cross between
//     wasm and javascript for performance reasons
//  4. Better separation of functionality: Most of the Javascript code is
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
  PyObject* repr_py = PyObject_Repr(pyobj);
  const char* repr_utf8 = PyUnicode_AsUTF8(repr_py);
  JsRef repr_js = hiwire_string_utf8(repr_utf8);
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
  return hiwire_string_ascii(ptrobj->ob_type->tp_name);
}

void
_pyproxy_destroy(PyObject* ptrobj)
{ // See bug #1049
  Py_DECREF(ptrobj);
  EM_ASM({ delete Module.PyProxies[$0]; }, ptrobj);
}

int
_pyproxy_hasattr(PyObject* pyobj, JsRef idkey)
{
  bool success = false;
  PyObject* pykey = NULL;
  int result = -1;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  result = PyObject_HasAttr(pyobj, pykey);

  success = true;
finally:
  Py_CLEAR(pykey);
  return result;
}

JsRef
_pyproxy_getattr(PyObject* pyobj, JsRef idkey)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pyresult = NULL;
  JsRef idresult = NULL;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  pyresult = PyObject_GetAttr(pyobj, pykey);
  FAIL_IF_NULL(pyresult);
  idresult = python2js(pyresult);
  FAIL_IF_NULL(idresult);

  success = true;
finally:
  Py_CLEAR(pykey);
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
  PyErr_Clear();
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
  PyObject* pydir = PyObject_Dir(pyobj);

  if (pydir == NULL) {
    return NULL;
  }

  JsRef iddir = hiwire_array();
  Py_ssize_t n = PyList_Size(pydir);
  for (Py_ssize_t i = 0; i < n; ++i) {
    PyObject* pyentry = PyList_GetItem(pydir, i);
    JsRef identry = python2js(pyentry);
    hiwire_push_array(iddir, identry);
    hiwire_decref(identry);
  }
  Py_DECREF(pydir);

  return iddir;
}

JsRef
_pyproxy_apply(PyObject* pyobj, JsRef idargs)
{
  Py_ssize_t length = hiwire_get_length(idargs);
  PyObject* pyargs = PyTuple_New(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    JsRef iditem = hiwire_get_member_int(idargs, i);
    PyObject* pyitem = js2python(iditem);
    PyTuple_SET_ITEM(pyargs, i, pyitem);
    hiwire_decref(iditem);
  }
  PyObject* pyresult = PyObject_Call(pyobj, pyargs, NULL);
  if (pyresult == NULL) {
    Py_DECREF(pyargs);
    return NULL;
  }
  JsRef idresult = python2js(pyresult);
  Py_DECREF(pyresult);
  Py_DECREF(pyargs);
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

/**
 * In Python 3.10, they have added the PyIter_Send API (and removed _PyGen_Send)
 * so in v3.10 this would be a simple API call wrapper like the rest of the code
 * here. For now, we're just copying the YIELD_FROM opcode (see ceval.c).
 *
 * When the iterator is done, it returns NULL and sets StopIteration. We'll use
 * _pyproxyGen_FetchStopIterationValue below to get the return value of the
 * generator (again copying from YIELD_FROM).
 */
JsRef
_pyproxyGen_Send(PyObject* receiver, JsRef jsval)
{
  bool success = false;
  PyObject* v = NULL;
  PyObject* retval = NULL;
  JsRef jsresult = NULL;

  v = js2python(jsval);
  FAIL_IF_NULL(v);
  if (PyGen_CheckExact(receiver) || PyCoro_CheckExact(receiver)) {
    retval = _PyGen_Send((PyGenObject*)receiver, v);
  } else if (v == Py_None) {
    retval = Py_TYPE(receiver)->tp_iternext(receiver);
  } else {
    _Py_IDENTIFIER(send);
    retval = _PyObject_CallMethodIdObjArgs(receiver, &PyId_send, v, NULL);
  }
  FAIL_IF_NULL(retval);

  jsresult = python2js(retval);
  FAIL_IF_NULL(jsresult);

  success = true;
finally:
  Py_CLEAR(v);
  Py_CLEAR(retval);
  if (!success) {
    hiwire_CLEAR(jsresult);
  }
  return jsresult;
}

/**
 * If StopIteration was set, return the value it was set with. Otherwise, return
 * NULL.
 */
JsRef
_pyproxyGen_FetchStopIterationValue()
{
  PyObject* val = NULL;
  // cf implementation of YIELD_FROM opcode in ceval.c
  // _PyGen_FetchStopIterationValue returns an error code, but it seems
  // redundant
  _PyGen_FetchStopIterationValue(&val);
  if (val == NULL) {
    return NULL;
  }
  JsRef result = python2js(val);
  Py_CLEAR(val);
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
// From Javascript we will use the single function _pyproxy_ensure_future, the
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
  bool success = false;
  JsRef result_js = NULL;
  JsRef output = NULL;
  result_js = python2js(result);
  output = hiwire_call_OneArg(self->resolve_handle, result_js);

  success = true;
finally:
  hiwire_CLEAR(result_js);
  hiwire_CLEAR(output);
  return success ? 0 : -1;
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
  excval = wrap_exception(false);
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
  PyObject* result = _PyObject_CallMethodIdObjArgs(fut, &PyId_result, NULL);
  int errcode;
  if (result != NULL) {
    errcode = FutureDoneCallback_call_resolve(self, result);
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
  future =
    _PyObject_CallMethodIdObjArgs(asyncio, &PyId_ensure_future, pyobject, NULL);
  FAIL_IF_NULL(future);
  callback = FutureDoneCallback_cnew(resolve_handle, reject_handle);
  retval = _PyObject_CallMethodIdObjArgs(
    future, &PyId_add_done_callback, callback, NULL);
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
// Javascript code
//
// The rest of the file is in Javascript. It would probably be better to move it
// into a .js file.
//

/**
 * In the case that the Python object is callable, PyProxyClass inherits from
 * Function so that PyProxy objects can be callable.
 *
 * The following properties on a Python object will be shadowed in the proxy in
 * the case that the Python object is callable:
 *  - "arguments" and
 *  - "caller"
 *
 * Inheriting from Function has the unfortunate side effect that we MUST expose
 * the members "proxy.arguments" and "proxy.caller" because they are
 * nonconfigurable, nonwritable, nonenumerable own properties. They are just
 * always `null`.
 *
 * We also get the properties "length" and "name" which are configurable so we
 * delete them in the constructor. "prototype" is not configurable so we can't
 * delete it, however it *is* writable so we set it to be undefined. We must
 * still make "prototype in proxy" be true though.
 */
EM_JS_REF(JsRef, pyproxy_new, (PyObject * ptrobj), {
  // Technically, this leaks memory, since we're holding on to a reference
  // to the proxy forever.  But we have that problem anyway since we don't
  // have a destructor in Javascript to free the Python object.
  // _pyproxy_destroy, which is a way for users to manually delete the proxy,
  // also deletes the proxy from this set.
  if (Module.PyProxies.hasOwnProperty(ptrobj)) {
    return Module.hiwire.new_value(Module.PyProxies[ptrobj]);
  }
  let flags = _pyproxy_getflags(ptrobj);
  let cls = Module.getPyProxyClass(flags);
  // Reflect.construct calls the constructor of Module.PyProxyClass but sets the
  // prototype as cls.prototype. This gives us a way to dynamically create
  // subclasses of PyProxyClass (as long as we don't need to use the "new
  // cls(ptrobj)" syntax).
  let target;
  if (flags & IS_CALLABLE) {
    // To make a callable proxy, we must call the Function constructor.
    // In this case we are effectively subclassing Function.
    target = Reflect.construct(Function, [], cls);
    // Remove undesireable properties added by Function constructor. Note: we
    // can't remove "arguments" or "caller" because they are not configurable
    // and not writable
    delete target.length;
    delete target.name;
    // prototype isn't configurable so we can't delete it but it's writable.
    target.prototype = undefined;
  } else {
    target = Object.create(cls.prototype);
  }
  Object.defineProperty(
    target, "$$", { value : { ptr : ptrobj, type : 'PyProxy' } });
  _Py_IncRef(ptrobj);
  let proxy = new Proxy(target, Module.PyProxyHandlers);
  Module.PyProxies[ptrobj] = proxy;
  return Module.hiwire.new_value(proxy);
});

// clang-format off
EM_JS_NUM(int, pyproxy_init_js, (), {
  Module.PyProxies = {};

  function _getPtr(jsobj) {
    let ptr = jsobj.$$.ptr;
    if (ptr === null) {
      throw new Error("Object has already been destroyed");
    }
    return ptr;
  }

  let _pyproxyClassMap = new Map();
  /** 
   * Retreive the appropriate mixins based on the features requested in flags.
   * Used by pyproxy_new. The "flags" variable is produced by the C function
   * pyproxy_getflags. Multiple PyProxies with the same set of feature flags
   * will share the same prototype, so the memory footprint of each individual
   * PyProxy is minimal.
   */
  Module.getPyProxyClass = function(flags){
    let result = _pyproxyClassMap.get(flags);
    if(result){
      return result;
    }
    let descriptors = {};
    for(let [feature_flag, methods] of [
      [HAS_LENGTH, Module.PyProxyLengthMethods],
      [HAS_GET, Module.PyProxyGetItemMethods],
      [HAS_SET, Module.PyProxySetItemMethods],
      [HAS_CONTAINS, Module.PyProxyContainsMethods],
      [IS_ITERABLE, Module.PyProxyIterableMethods],
      [IS_ITERATOR, Module.PyProxyIteratorMethods],
      [IS_AWAITABLE, Module.PyProxyAwaitableMethods],
      [IS_BUFFER, Module.PyProxyBufferMethods],
      [IS_CALLABLE, Module.PyProxyCallableMethods],
    ]){
      if(flags & feature_flag){
        Object.assign(descriptors,
          Object.getOwnPropertyDescriptors(methods)
        );
      }
    }
    let new_proto = Object.create(Module.PyProxyClass.prototype, descriptors);
    function PyProxy(){};
    PyProxy.prototype = new_proto;
    _pyproxyClassMap.set(flags, PyProxy);
    return PyProxy;
  };

  // Static methods
  Module.PyProxy = {
    _getPtr,
    isPyProxy: function(jsobj) {
      return jsobj && jsobj.$$ !== undefined && jsobj.$$.type === 'PyProxy';
    },
  };

  // Now a lot of boilerplate to wrap the abstract Object protocol wrappers
  // above in Javascript functions.

  Module.PyProxyClass = class {
    constructor(){
      throw new TypeError('PyProxy is not a constructor');
    }

    get [Symbol.toStringTag] (){
        return "PyProxy";
    }
    get type() {
      let ptrobj = _getPtr(this);
      return Module.hiwire.pop_value(__pyproxy_type(ptrobj));
    }
    toString() {
      let ptrobj = _getPtr(this);
      let jsref_repr;
      try {
        jsref_repr = __pyproxy_repr(ptrobj);
      } catch(e){
        Module.fatal_error(e);
      }
      if(jsref_repr === 0){
        _pythonexc2js();
      }
      return Module.hiwire.pop_value(jsref_repr);
    }
    destroy() {
      let ptrobj = _getPtr(this);
      __pyproxy_destroy(ptrobj);
      this.$$.ptr = null;
    }
    /** 
      * This one doesn't follow the pattern: the inner function
      * _python2js_with_depth is defined in python2js.c and is not a Python
      * Object Protocol wrapper.
      */
    toJs(depth = -1){
      let idresult = _python2js_with_depth(_getPtr(this), depth);
      let result = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      return result;
    }
  };

  // Controlled by HAS_LENGTH, appears for any object with __len__ or sq_length
  // or mp_length methods
  Module.PyProxyLengthMethods = {
    get length(){
      let ptrobj = _getPtr(this);
      let length;
      try {
        length = _PyObject_Size(ptrobj);
      } catch(e) {
        Module.fatal_error(e);
      }
      if(length === -1){
        _pythonexc2js();
      }
      return length;
    }
  };

  // Controlled by HAS_GET, appears for any class with __getitem__,
  // mp_subscript, or sq_item methods
  Module.PyProxyGetItemMethods = {
    get : function(key){
      let ptrobj = _getPtr(this);
      let idkey = Module.hiwire.new_value(key);
      let idresult;
      try {
        idresult = __pyproxy_getitem(ptrobj, idkey);
      } catch(e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
      }
      if(idresult === 0){
        if(Module._PyErr_Occurred()){
          _pythonexc2js();
        } else {
          return undefined;
        }
      }
      return Module.hiwire.pop_value(idresult);
    },
  };

  // Controlled by HAS_SET, appears for any class with __setitem__, __delitem__,
  // mp_ass_subscript,  or sq_ass_item.
  Module.PyProxySetItemMethods = {
    set : function(key, value){
      let ptrobj = _getPtr(this);
      let idkey = Module.hiwire.new_value(key);
      let idval = Module.hiwire.new_value(value);
      let errcode;
      try {
        errcode = __pyproxy_setitem(ptrobj, idkey, idval);
      } catch(e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
        Module.hiwire.decref(idval);
      }
      if(errcode === -1){
        _pythonexc2js();
      }
    },
    delete : function(key) {
      let ptrobj = _getPtr(this);
      let idkey = Module.hiwire.new_value(key);
      let errcode;
      try {
        errcode = __pyproxy_delitem(ptrobj, idkey);
      } catch(e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
      }
      if(errcode === -1){
        _pythonexc2js();
      }
    }
  };

  // Controlled by HAS_CONTAINS flag, appears for any class with __contains__ or
  // sq_contains
  Module.PyProxyContainsMethods = {
    has : function(key) {
      let ptrobj = _getPtr(this);
      let idkey = Module.hiwire.new_value(key);
      let result;
      try {
        result = __pyproxy_contains(ptrobj, idkey);
      } catch(e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
      }
      if(result === -1){
        _pythonexc2js();
      }
      return result === 1;
    },
  };

  // Controlled by IS_ITERABLE, appears for any object with __iter__ or tp_iter, unless
  // they are iterators.
  // See:
  // https://docs.python.org/3/c-api/iter.html
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Iteration_protocols
  // This avoids allocating a PyProxy wrapper for the temporary iterator.
  Module.PyProxyIterableMethods = {
    [Symbol.iterator] : function*() {
      let iterptr = _PyObject_GetIter(_getPtr(this));
      if(iterptr === 0){
        pythonexc2js();
      }
      let item;
      while((item = __pyproxy_iter_next(iterptr))){
        yield Module.hiwire.pop_value(item);
      }
      if(_PyErr_Occurred()){
        pythonexc2js();
      }
      _Py_DecRef(iterptr);
    }
  };

  // Controlled by IS_ITERATOR, appears for any object with a __next__ or
  // tp_iternext method.
  Module.PyProxyIteratorMethods = {
    [Symbol.iterator] : function() {
      return this;
    },
    next : function(arg) {
      let idresult;
      // Note: arg is optional, if arg is not supplied, it will be undefined
      // which gets converted to "Py_None". This is as intended.
      let idarg = Module.hiwire.new_value(arg);
      try {
        idresult = __pyproxyGen_Send(_getPtr(this), idarg);
      } catch(e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idarg);
      }

      let done = false;
      if(idresult === 0){
        idresult = __pyproxyGen_FetchStopIterationValue();
        if (idresult){
          done = true;
        } else {
          _pythonexc2js();
        }
      }
      let value = Module.hiwire.pop_value(idresult);
      return { done, value };
    },
  };

  // Another layer of boilerplate. The PyProxyHandlers have some annoying logic
  // to deal with straining out the spurious "Function" properties "prototype",
  // "arguments", and "length", to deal with correctly satisfying the Proxy
  // invariants, and to deal with the mro
  function python_hasattr(jsobj, jskey){
      let ptrobj = _getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let result;
      try {
        result = __pyproxy_hasattr(ptrobj, idkey);
      } catch(e){
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
      }
      if(result === -1){
        _pythonexc2js();
      }
      return result !== 0;
  }

  // Returns a JsRef in order to allow us to differentiate between "not found"
  // (in which case we return 0) and "found 'None'" (in which case we return
  // Js_undefined).
  function python_getattr(jsobj, jskey){
    let ptrobj = _getPtr(jsobj);
    let idkey = Module.hiwire.new_value(jskey);
    let idresult;
    try {
      idresult = __pyproxy_getattr(ptrobj, idkey);
    } catch(e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
    }
    if(idresult === 0){
      if(_PyErr_Occurred()){
        _pythonexc2js();
      }
    }
    return idresult;
  }

  function python_setattr(jsobj, jskey, jsval){
    let ptrobj = _getPtr(jsobj);
    let idkey = Module.hiwire.new_value(jskey);
    let idval = Module.hiwire.new_value(jsval);
    let errcode;
    try {
      errcode = __pyproxy_setattr(ptrobj, idkey, idval);
    } catch(e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idval);
    }
    if(errcode === -1){
      _pythonexc2js();
    }
  }

  function python_delattr(jsobj, jskey){
    let ptrobj = _getPtr(jsobj);
    let idkey = Module.hiwire.new_value(jskey);
    let errcode;
    try {
      errcode = __pyproxy_delattr(ptrobj, idkey);
    } catch(e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
    }
    if(errcode === -1){
      _pythonexc2js();
    }
  }

  // See explanation of which methods should be defined here and what they do here:
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy
  Module.PyProxyHandlers = {
    isExtensible: function() { return true },
    has: function (jsobj, jskey) {
      // Note: must report "prototype" in proxy when we are callable.
      // (We can return the wrong value from "get" handler though.)
      let objHasKey = Reflect.has(jsobj, jskey);
      if(objHasKey){
        return true;
      }
      // python_hasattr will crash when given a Symbol.
      if(typeof(jskey) === "symbol"){
        return false;
      }
      return python_hasattr(jsobj, jskey);
    },
    get: function (jsobj, jskey) {
      // Preference order:
      // 1. things we have to return to avoid making Javascript angry
      // 2. the result of Python getattr
      // 3. stuff from the prototype chain

      // 1. things we have to return to avoid making Javascript angry
      // This conditional looks funky but it's the only thing I found that
      // worked right in all cases.
      if((jskey in jsobj) && !(jskey in Object.getPrototypeOf(jsobj)) ){
        return Reflect.get(jsobj, jskey);
      }
      // python_getattr will crash when given a Symbol
      if(typeof(jskey) === "symbol"){
        return Reflect.get(jsobj, jskey);
      }
      // 2. The result of getattr
      let idresult = python_getattr(jsobj, jskey);
      if(idresult !== 0){
        return Module.hiwire.pop_value(idresult);
      }
      // 3. stuff from the prototype chain.
      return Reflect.get(jsobj, jskey);
    },
    set: function (jsobj, jskey, jsval) {
      // We're only willing to set properties on the python object, throw an
      // error if user tries to write over any key of type 1. things we have to
      // return to avoid making Javascript angry
      if(typeof(jskey) === "symbol"){
        throw new TypeError(`Cannot set read only field '${jskey.description}'`);
      }
      // Again this is a funny looking conditional, I found it as the result of
      // a lengthy search for something that worked right.
      let descr = Object.getOwnPropertyDescriptor(jsobj, jskey);
      if(descr && !descr.writable){
        throw new TypeError(`Cannot set read only field '${jskey}'`);
      }
      python_setattr(jsobj, jskey, jsval);
      return true;
    },
    deleteProperty: function (jsobj, jskey) {
      // We're only willing to delete properties on the python object, throw an
      // error if user tries to write over any key of type 1. things we have to
      // return to avoid making Javascript angry
      if(typeof(jskey) === "symbol"){
        throw new TypeError(`Cannot delete read only field '${jskey.description}'`);
      }
      let descr = Object.getOwnPropertyDescriptor(jsobj, jskey);
      if(descr && !descr.writable){
        throw new TypeError(`Cannot delete read only field '${jskey}'`);
      }
      python_delattr(jsobj, jskey);
      // Must return "false" if "jskey" is a nonconfigurable own property.
      // Otherwise Javascript will throw a TypeError.
      return !descr || descr.configurable;
    },
    ownKeys: function (jsobj) {
      let ptrobj = _getPtr(jsobj);
      let idresult;
      try {
        idresult = __pyproxy_ownKeys(ptrobj);
      } catch(e) {
        Module.fatal_error(e);
      }
      let result = Module.hiwire.pop_value(idresult);
      result.push(...Reflect.ownKeys(jsobj));
      return result;
    },
    apply: function (jsobj, jsthis, jsargs) {
      let ptrobj = _getPtr(jsobj);
      let idargs = Module.hiwire.new_value(jsargs);
      let idresult;
      try {
        idresult = __pyproxy_apply(ptrobj, idargs);
      } catch(e){
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idargs);
      }
      if(idresult === 0){
        _pythonexc2js();
      }
      return Module.hiwire.pop_value(idresult);
    },
  };
  
  /** 
   * The Promise / javascript awaitable API.
   */
  Module.PyProxyAwaitableMethods = {
    /** 
     * This wraps __pyproxy_ensure_future and makes a function that converts a
     * Python awaitable to a promise, scheduling the awaitable on the Python
     * event loop if necessary.
     */
    _ensure_future : function(){
      let resolve_handle_id = 0;
      let reject_handle_id = 0;
      let resolveHandle;
      let rejectHandle;
      let promise;
      try {
        promise = new Promise((resolve, reject) => {
          resolveHandle = resolve;
          rejectHandle = reject;
        });
        resolve_handle_id = Module.hiwire.new_value(resolveHandle);
        reject_handle_id = Module.hiwire.new_value(rejectHandle);
        let ptrobj = _getPtr(this);
        let errcode = __pyproxy_ensure_future(ptrobj, resolve_handle_id, reject_handle_id);
        if(errcode === -1){
          _pythonexc2js();
        }
      } finally {
        Module.hiwire.decref(resolve_handle_id);
        Module.hiwire.decref(reject_handle_id);
      }
      return promise;
    },
    then : function(onFulfilled, onRejected){
      let promise = this._ensure_future();
      return promise.then(onFulfilled, onRejected);
    },
    catch : function(onRejected){
      let promise = this._ensure_future();
      return promise.catch(onRejected);
    },
    finally : function(onFinally){
      let promise = this._ensure_future();
      return promise.finally(onFinally);
    }
  };

  Module.PyProxyCallableMethods = { prototype : Function.prototype };
  Module.PyProxyBufferMethods = {};

  // A special proxy that we use to wrap pyodide.globals to allow property access
  // like `pyodide.globals.x`.
  let globalsPropertyAccessWarned = false;
  let globalsPropertyAccessWarningMsg =
    "Access to pyodide.globals via pyodide.globals.key is deprecated and " +
    "will be removed in version 0.18.0. Use pyodide.globals.get('key'), " +
    "pyodide.globals.set('key', value), pyodide.globals.delete('key') instead.";
  let NamespaceProxyHandlers = {
    has : function(obj, key){
      return Reflect.has(obj, key) || obj.has(key);
    },
    get : function(obj, key){
      if(Reflect.has(obj, key)){
        return Reflect.get(obj, key);
      }
      let result = obj.get(key);
      if(!globalsPropertyAccessWarned && result !== undefined){
        console.warn(globalsPropertyAccessWarningMsg);
        globalsPropertyAccessWarned = true;
      }
      return result;
    },
    set : function(obj, key, value){
      if(Reflect.has(obj, key)){
        throw new Error(`Cannot set read only field ${key}`);
      }
      if(!globalsPropertyAccessWarned){
        globalsPropertyAccessWarned = true;
        console.warn(globalsPropertyAccessWarningMsg);
      }
      obj.set(key, value);
    },
    ownKeys: function (obj) {
      let result = new Set(Reflect.ownKeys(obj));
      let iter = obj.keys();
      for(let key of iter){
        result.add(key);
      }
      iter.destroy();
      return Array.from(result);
    }
  };
  
  Module.wrapNamespace = function wrapNamespace(ns){
    return new Proxy(ns, NamespaceProxyHandlers);
  };

  return 0;
});
// clang-format on

int
pyproxy_init()
{
  asyncio = PyImport_ImportModule("asyncio");
  if (asyncio == NULL) {
    return -1;
  }
  if (PyType_Ready(&FutureDoneCallbackType)) {
    return -1;
  }
  if (pyproxy_init_js()) {
    return -1;
  }
  return 0;
}
