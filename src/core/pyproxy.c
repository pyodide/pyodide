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

JsRef
_pyproxy_repr(PyObject* pyobj)
{
  PyObject* repr_py = PyObject_Repr(pyobj);
  const char* repr_utf8 = PyUnicode_AsUTF8(repr_py);
  JsRef repr_js = hiwire_string_utf8(repr_utf8);
  Py_CLEAR(repr_py);
  return repr_js;
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

// Return 2 if obj is iterator
// Return 1 if iterable but not iterator
// Return 0 if not iterable
int
_pyproxy_iterator_type(PyObject* obj)
{
  if (PyIter_Check(obj)) {
    return 2;
  }
  PyObject* iter = PyObject_GetIter(obj);
  int result = iter != NULL;
  Py_CLEAR(iter);
  PyErr_Clear();
  return result;
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

JsRef
_pyproxy_iter_send(PyObject* receiver, JsRef jsval)
{
  bool success = false;
  PyObject* v = NULL;
  PyObject* retval = NULL;
  JsRef jsresult = NULL;

  // cf implementation of YIELD_FROM opcode in ceval.c
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

JsRef
_pyproxy_iter_fetch_stopiteration()
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

size_t py_buffer_len_offset = offsetof(Py_buffer, len);
size_t py_buffer_shape_offset = offsetof(Py_buffer, shape);

bool
_pyproxy_is_buffer(PyObject* ptrobj)
{
  return PyObject_CheckBuffer(ptrobj);
}

JsRef
array_to_js(Py_ssize_t* array, int len)
{
  JsRef result = hiwire_array();
  for (int i = 0; i < len; i++) {
    JsRef val = hiwire_int(array[i]);
    hiwire_push_array(result, val);
    hiwire_decref(val);
  }
  return result;
}

// The order of these fields has to match the code in getRawBuffer
typedef struct
{
  void* start_ptr;
  void* smallest_ptr;
  void* largest_ptr;
  JsRef shape;
  JsRef strides;
  Py_buffer* view;
} buffer_struct;

buffer_struct*
_pyproxy_memoryview_get_buffer(PyObject* ptrobj)
{
  if (!PyObject_CheckBuffer(ptrobj)) {
    return NULL;
  }
  Py_buffer view;
  if (PyObject_GetBuffer(ptrobj, &view, PyBUF_RECORDS_RO) == -1) {
    PyErr_Clear();
    return NULL;
  }

  bool success = false;
  if (view.ndim == 0) {
    FAIL();
  }
  buffer_struct result = { 0 };
  result.shape = array_to_js(view.shape, view.ndim);

  result.start_ptr = result.smallest_ptr = result.largest_ptr = view.buf;

  if (view.strides == NULL) {
    result.largest_ptr += view.len;
    Py_ssize_t strides[view.ndim];
    PyBuffer_FillContiguousStrides(
      view.ndim, view.shape, strides, view.itemsize, 'C');
    result.strides = array_to_js(strides, view.ndim);
    goto success;
  }

  for (int i = 0; i < view.ndim; i++) {
    if (view.shape[i] == 0) {
      FAIL();
    }
    if (view.strides[i] > 0) {
      result.largest_ptr += view.strides[i] * (view.shape[i] - 1);
    } else {
      result.smallest_ptr += view.strides[i] * (view.shape[i] - 1);
    }
  }
  result.largest_ptr += view.itemsize;
  result.strides = array_to_js(view.strides, view.ndim);

success:
  success = true;
finally:
  if (success) {
    result.view = (Py_buffer*)PyMem_Malloc(sizeof(Py_buffer));
    *result.view = view;
    buffer_struct* result_heap =
      (buffer_struct*)PyMem_Malloc(sizeof(buffer_struct));
    *result_heap = result;
    return result_heap;
  } else {
    hiwire_CLEAR(result.shape);
    hiwire_CLEAR(result.strides);
    PyBuffer_Release(&view);
    return NULL;
  }
}
/**
 * Test if a PyObject is awaitable.
 * Uses _PyCoro_GetAwaitableIter like in the implementation of the GET_AWAITABLE
 * opcode (see ceval.c). Unfortunately this is not a public API (see issue
 * https://bugs.python.org/issue24510) so it could be a source of instability.
 *
 * :param pyobject: The Python object.
 * :return: 1 if the python code "await obj" would succeed, 0 otherwise. Never
 * fails.
 */
bool
_pyproxy_is_awaitable(PyObject* pyobject)
{
  PyObject* awaitable = _PyCoro_GetAwaitableIter(pyobject);
  PyErr_Clear();
  bool result = awaitable != NULL;
  Py_CLEAR(awaitable);
  return result;
}

// clang-format off
/**
 * A simple Callable python object. Intended to be called with a single argument
 * which is the future that was resolved.
 */
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

EM_JS_REF(JsRef, pyproxy_new, (PyObject * ptrobj), {
  // Technically, this leaks memory, since we're holding on to a reference
  // to the proxy forever.  But we have that problem anyway since we don't
  // have a destructor in Javascript to free the Python object.
  // _pyproxy_destroy, which is a way for users to manually delete the proxy,
  // also deletes the proxy from this set.
  if (Module.PyProxies.hasOwnProperty(ptrobj)) {
    return Module.hiwire.new_value(Module.PyProxies[ptrobj]);
  }

  _Py_IncRef(ptrobj);

  let target = new Module.PyProxyClass();
  target['$$'] = { ptr : ptrobj, type : 'PyProxy' };

  // clang-format off
  if (_PyMapping_Check(ptrobj) === 1) {
    // clang-format on
    // Note: this applies to lists and tuples and sequence-like things
    // _PyMapping_Check returns true on a superset of things _PySequence_Check
    // accepts.
    Object.assign(target, Module.PyProxyMappingMethods);
  }

  let proxy = new Proxy(target, Module.PyProxyHandlers);
  let itertype = __pyproxy_iterator_type(ptrobj);
  // clang-format off
  if (itertype === 2) {
    Object.assign(target, Module.PyProxyIteratorMethods);
  }
  if (itertype === 1) {
    Object.assign(target, Module.PyProxyIterableMethods);
  }
  if(__pyproxy_is_buffer(ptrobj)){
    Object.assign(target, Module.PyProxyBufferMethods);
  }
  // clang-format on
  Module.PyProxies[ptrobj] = proxy;
  let is_awaitable = __pyproxy_is_awaitable(ptrobj);
  if (is_awaitable) {
    Object.assign(target, Module.PyProxyAwaitableMethods);
  }

  return Module.hiwire.new_value(proxy);
});

EM_JS_NUM(int, pyproxy_init_js, (), {
  // clang-format off
  Module.PyProxies = {};
  function _getPtr(jsobj) {
    let ptr = jsobj.$$.ptr;
    if (ptr === null) {
      throw new Error("Object has already been destroyed");
    }
    return ptr;
  }
  
  // Static methods
  Module.PyProxy = {
    _getPtr,
    isPyProxy: function(jsobj) {
      return jsobj && jsobj.$$ !== undefined && jsobj.$$.type === 'PyProxy';
    },
  };

  // We inherit from Function so that we can be callable. 
  Module.PyProxyClass = class extends Function {
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
    apply(jsthis, jsargs) {
      let ptrobj = _getPtr(this);
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
    }
    toJs(depth = -1){
      let idresult = _python2js_with_depth(_getPtr(this), depth);
      let result = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      return result;
    }
  };

  // These methods appear for lists and tuples and sequence-like things
  // _PyMapping_Check returns true on a superset of things _PySequence_Check accepts.
  Module.PyProxyMappingMethods = {
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
    has : function(key) {
      return this.get(key) !== undefined;
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
        idresult = __pyproxy_iter_send(_getPtr(this), idarg);
      } catch(e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idarg);
      }

      let done = false;
      if(idresult === 0){
        idresult = __pyproxy_iter_fetch_stopiteration();
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

  let type_to_array_map = new Map(
    [
      ["i8", Int8Array],
      ["u8", Uint8Array],
      ["i16", Int16Array],
      ["u16", Uint16Array],
      ["i32", Int32Array],
      ["u32", Uint32Array],
      ["i32", Int32Array],
      ["u32", Uint32Array],      
      ["f32", Float32Array],      
      ["f64", Float64Array],      
    ]
  );
  if(globalThis.BigInt64Array){
      type_to_array_map.set("i64", BigInt64Array);
      type_to_array_map.set("u64", BigUint64Array);
  }

  class PyBuffer {
    constructor({ offset, shape, strides, buffer, view_ptr }){
      this._released = false;
      this.offset = offset;
      this.shape = shape;
      this.strides = strides;
      this.buffer = buffer;
      this._view_ptr = view_ptr;
    }

    release(){
      if(this._released){
        return;
      }
      _PyBuffer_Release(this._view_ptr);
      _PyMem_Free(this._view_ptr);
      this._released = true;
    }
  }

  Module.PyProxyBufferMethods = {
    getRawBuffer : function(type = "u8"){
      let ArrayType = type_to_array_map.get(type);
      if(ArrayType === undefined){
        throw new Error(`Unknown type ${type}`);
      }
      let this_ptr = _getPtr(this);
      let buffer_struct_ptr = __pyproxy_memoryview_get_buffer(this_ptr);
      if(buffer_struct_ptr === 0){
        throw new Error("Failed");
      }

      // This has to match the order of the fields in buffer_struct
      let cur_ptr = buffer_struct_ptr/4;
      let start = HEAP32[cur_ptr++];
      let smallest = HEAP32[cur_ptr++];
      let largest = HEAP32[cur_ptr++];
      let shape = Module.hiwire.pop_value(HEAP32[cur_ptr++]);
      let strides = Module.hiwire.pop_value(HEAP32[cur_ptr++]);
      let view_ptr = HEAP32[cur_ptr++];
      _PyMem_Free(buffer_struct_ptr);


      let alignment = parseInt(type.slice(1))/8;
      if(start % alignment !== 0 || smallest % alignment !== 0 || largest % alignment !== 0){
        _PyBuffer_Release(view_ptr);
        _PyMem_Free(view_ptr);
        throw new Error(`Buffer does not have valid alignment for type ${type}`);
      }
      
      let length = (largest - smallest) / alignment;
      let offset = (start - smallest) / alignment;

      let buffer = new ArrayType(HEAP8.buffer, smallest, length);
      for(let i of strides.keys()){
        strides[i] /= alignment;
      }
      return new PyBuffer({ offset, shape, strides, buffer, view_ptr });
    }
  };

  // These fields appear in the target by default because the target is a function.
  // we want to filter them out.
  let ignoredTargetFields = ["name", "length"];

  // See explanation of which methods should be defined here and what they do here:
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy
  Module.PyProxyHandlers = {
    isExtensible: function() { return true },
    has: function (jsobj, jskey) {
      if(Reflect.has(jsobj, jskey) && !ignoredTargetFields.includes(jskey)){
        return true;
      }
      if(typeof(jskey) === "symbol"){
        return false;
      }
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
    },
    get: function (jsobj, jskey) {
      if(Reflect.has(jsobj, jskey) && !ignoredTargetFields.includes(jskey)){
        return Reflect.get(jsobj, jskey);
      }
      if(typeof(jskey) === "symbol"){
        return undefined;
      }
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
        _pythonexc2js();
      }
      return Module.hiwire.pop_value(idresult);
    },
    set: function (jsobj, jskey, jsval) {
      if(
        Reflect.has(jsobj, jskey) && !ignoredTargetFields.includes(jskey)
        || typeof(jskey) === "symbol"
      ){
        if(typeof(jskey) === "symbol"){
          jskey = jskey.description;
        }
        throw new Error(`Cannot set read only field ${jskey}`);
      }
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
      return true;
    },
    deleteProperty: function (jsobj, jskey) {
      if(
        Reflect.has(jsobj, jskey) && !ignoredTargetFields.includes(jskey)
        || typeof(jskey) === "symbol"
      ){
        if(typeof(jskey) === "symbol"){
          jskey = jskey.description;
        }        
        throw new Error(`Cannot delete read only field ${jskey}`);
      }
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
      return true;
    },
    ownKeys: function (jsobj) {
      let result = new Set(Reflect.ownKeys(jsobj));
      for(let key of ignoredTargetFields){
        result.delete(key);
      }
      let ptrobj = _getPtr(jsobj);
      let idresult;
      try {
        idresult = __pyproxy_ownKeys(ptrobj);
      } catch(e) {
        Module.fatal_error(e);
      }
      let jsresult = Module.hiwire.pop_value(idresult);
      for(let key of jsresult){
        result.add(key);
      }
      return Array.from(result);
    },
    apply: function (jsobj, jsthis, jsargs) {
      return jsobj.apply(jsthis, jsargs);
    },
  };
  
  Module.PyProxyAwaitableMethods = {
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


  // A special proxy that we use to wrap pyodide.globals to allow property access
  // like `pyodide.globals.x`.
  // TODO: Should we have this?
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
// clang-format on
});

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
