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

JsRef
_pyproxy_has(PyObject* pyobj, JsRef idkey)
{
  PyObject* pykey = js2python(idkey);
  JsRef result = hiwire_bool(PyObject_HasAttr(pyobj, pykey));
  Py_DECREF(pykey);
  return result;
}

JsRef
_pyproxy_get(PyObject* pyobj, JsRef idkey)
{
  PyObject* pykey = js2python(idkey);
  PyObject* pyattr;
  // HC: HACK until my more thorough rework of pyproxy goes through.
  // We need globals to work, I want it to be proxied, but we also need
  // indexing in js to do GetItem, SetItem, and DelItem.
  // This is harmless though because currently dicts will not get proxied at
  // all, aside from globals which I specifically hand proxy in runpython.c.
  if (PyDict_Check(pyobj)) {
    pyattr = PyObject_GetItem(pyobj, pykey);
  } else {
    pyattr = PyObject_GetAttr(pyobj, pykey);
  }

  Py_DECREF(pykey);
  if (pyattr == NULL) {
    PyErr_Clear();
    return Js_undefined;
  }

  JsRef idattr = python2js(pyattr);
  Py_DECREF(pyattr);
  return idattr;
};

JsRef
_pyproxy_set(PyObject* pyobj, JsRef idkey, JsRef idval)
{
  PyObject* pykey = js2python(idkey);
  PyObject* pyval = js2python(idval);
  // HC: HACK see comment in _pyproxy_get.
  int result;
  if (PyDict_Check(pyobj)) {
    result = PyObject_SetItem(pyobj, pykey, pyval);
  } else {
    result = PyObject_SetAttr(pyobj, pykey, pyval);
  }
  Py_DECREF(pykey);
  Py_DECREF(pyval);

  if (result) {
    return NULL;
  }
  return hiwire_incref(idval);
}

JsRef
_pyproxy_deleteProperty(PyObject* pyobj, JsRef idkey)
{
  PyObject* pykey = js2python(idkey);
  int ret;
  // HC: HACK see comment in _pyproxy_get.
  if (PyDict_Check(pyobj)) {
    ret = PyObject_DelItem(pyobj, pykey);
  } else {
    ret = PyObject_DelAttr(pyobj, pykey);
  }
  Py_DECREF(pykey);

  if (ret) {
    return NULL;
  }

  return Js_undefined;
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
  let proxy = new Proxy(target, Module.PyProxyHandlers);
  let itertype = __pyproxy_iterator_type(ptrobj);
  // clang-format off
  if (itertype === 2) {
    Object.assign(target, Module.PyProxyIteratorMethods);
  }
  if (itertype === 1) {
    Object.assign(target, Module.PyProxyIterableMethods);
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
    let ptr = jsobj['$$']['ptr'];
    if (ptr === null) {
      throw new Error("Object has already been destroyed");
    }
    return ptr;
  }
  // Static methods
  Module.PyProxy = {
    _getPtr,
    isPyProxy: function(jsobj) {
      return jsobj && jsobj['$$'] !== undefined && jsobj['$$']['type'] === 'PyProxy';
    },
  };

  Module.PyProxyClass = class extends Function {
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
      this['$$']['ptr'] = null;
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

  let ignoredTargetFields = ["name", "length"];

  // See explanation of which methods should be defined here and what they do here:
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy
  Module.PyProxyHandlers = {
    isExtensible: function() { return true },
    has: function (jsobj, jskey) {
      if(Reflect.has(jsobj, jskey) && !ignoredTargetFields.includes(jskey)){
        return true;
      }
      let ptrobj = _getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let result;
      try {
        result = __pyproxy_has(ptrobj, idkey);
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
      let ptrobj = _getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let idresult;
      try {
        idresult = __pyproxy_get(ptrobj, idkey);
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
      if(Reflect.has(jsobj, jskey) && !ignoredTargetFields.includes(jskey)){
        throw new Error(`Cannot set read only field ${jskey}`);
      }
      let ptrobj = _getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let idval = Module.hiwire.new_value(jsval);
      let idresult;
      try {
        idresult = __pyproxy_set(ptrobj, idkey, idval);
      } catch(e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
        Module.hiwire.decref(idval);
      }
      if(idresult === 0){
        _pythonexc2js();
      }
      return Module.hiwire.pop_value(idresult);
    },
    deleteProperty: function (jsobj, jskey) {
      if(Reflect.has(jsobj, jskey) && !ignoredTargetFields.includes(jskey)){
        throw new Error(`Cannot delete read only field ${jskey}`);
      }
      let ptrobj = _getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let idresult;
      try {
        idresult = __pyproxy_deleteProperty(ptrobj, idkey);
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
