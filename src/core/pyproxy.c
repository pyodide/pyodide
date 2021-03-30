#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "error_handling.h"
#include <emscripten.h>

#include "docstring.h"
#include "hiwire.h"
#include "js2python.h"
#include "jsproxy.h"
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
  output = hiwire_call_va(self->resolve_handle, result_js, NULL);

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
  result = hiwire_call_va(self->reject_handle, excval, NULL);

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
// Buffers
//

// For debug
size_t py_buffer_len_offset = offsetof(Py_buffer, len);
size_t py_buffer_shape_offset = offsetof(Py_buffer, shape);

/**
 * Convert a C array of Py_ssize_t to Javascript.
 */
EM_JS_REF(JsRef, array_to_js, (Py_ssize_t * array, int len), {
  return Module.hiwire.new_value(
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

/**
 * This is the C part of the getBuffer method.
 *
 * We use PyObject_GetBuffer to acquire a Py_buffer view to the object, then we
 * determine the locations of: the first element of the buffer, the earliest
 * element of the buffer in memory the lastest element of the buffer in memory
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
buffer_struct*
_pyproxy_get_buffer(PyObject* ptrobj)
{
  if (!PyObject_CheckBuffer(ptrobj)) {
    return NULL;
  }
  Py_buffer view;
  // PyBUF_RECORDS_RO requires that suboffsets be NULL but otherwise is the most
  // permissive possible request.
  if (PyObject_GetBuffer(ptrobj, &view, PyBUF_RECORDS_RO) == -1) {
    // Buffer cannot be represented without suboffsets. The bf_getbuffer method
    // should have set a PyExc_BufferError saying something to this effect.
    pythonexc2js();
  }

  bool success = false;
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
    result.shape = hiwire_array();
    result.strides = hiwire_array();
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
  success = true;
finally:
  if (success) {
    // The result.view memory will be freed when (if?) the user calls
    // Py_Buffer.release().
    result.view = (Py_buffer*)PyMem_Malloc(sizeof(Py_buffer));
    *result.view = view;
    // The result_heap memory will be freed by getBuffer
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

EM_JS_REF(JsRef, create_once_callable, (PyObject * obj), {
  _Py_IncRef(obj);
  let alreadyCalled = false;
  function wrapper(... args)
  {
    if (alreadyCalled) {
      throw new Error("OnceProxy can only be called once");
    }
    alreadyCalled = true;
    try {
      return Module.callPyObject(obj, ... args);
    } finally {
      _Py_DecRef(obj);
    }
  }
  wrapper.destroy = function()
  {
    if (alreadyCalled) {
      throw new Error("OnceProxy has already been destroyed");
    }
    alreadyCalled = true;
    _Py_DecRef(obj);
  };
  return Module.hiwire.new_value(wrapper);
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
EM_JS_REF(JsRef, create_promise_handles, (
  PyObject* handle_result, PyObject* handle_exception
), {
  if (handle_result) {
    _Py_IncRef(handle_result);
  }
  if (handle_exception) {
    _Py_IncRef(handle_exception);
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
        return Module.callPyObject(handle_result, res);
      }
    } finally {
      destroy();
    }
  }
  function onRejected(err) {
    checkUsed();
    try {
      if(handle_exception){
        return Module.callPyObject(handle_exception, err);
      }
    } finally {
      destroy();
    }
  }
  onFulfilled.destroy = destroy;
  onRejected.destroy = destroy;
  return Module.hiwire.new_value(
    [onFulfilled, onRejected]
  );
})
// clang-format on

static PyObject*
create_proxy(PyObject* _mod, PyObject* obj)
{
  JsRef ref = pyproxy_new(obj);
  PyObject* result = JsProxy_create(ref);
  hiwire_decref(ref);
  return result;
}

static PyMethodDef pyproxy_methods[] = {
  {
    "create_once_callable",
    create_once_callable_py,
    METH_O,
  },
  {
    "create_proxy",
    create_proxy,
    METH_O,
  },
  { NULL } /* Sentinel */
};

// Some special helper macros to hack it so that "pyproxy.js" parses as a
// javascript file for JsDoc. See comment with explanation there.
#define UNPAIRED_OPEN_BRACE {
#define UNPAIRED_CLOSE_BRACE } // Just here to help text editors pair braces up
#define TEMP_EMJS_HELPER(a, args...)                                           \
  EM_JS_NUM(int, pyproxy_init_js, (), UNPAIRED_OPEN_BRACE { args return 0; })

// A macro to allow us to add code that is only intended to influence JsDoc
// output, but shouldn't end up in generated code.
#define FOR_JSDOC_ONLY(x)

#include "pyproxy.js"

#undef TEMP_EMJS_HELPER
#undef UNPAIRED_OPEN_BRACE
#undef UNPAIRED_CLOSE_BRACE

int
pyproxy_init(PyObject* core)
{
  bool success = false;
  int i = 0;

  PyObject* _pyodide_core = NULL;
  _pyodide_core = PyImport_ImportModule("_pyodide._core");
  FAIL_IF_NULL(_pyodide_core);

  while (pyproxy_methods[i].ml_name != NULL) {
    FAIL_IF_MINUS_ONE(set_method_docstring(&pyproxy_methods[i], _pyodide_core));
    i++;
  }
  FAIL_IF_MINUS_ONE(PyModule_AddFunctions(core, pyproxy_methods));
  asyncio = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio);
  FAIL_IF_MINUS_ONE(PyType_Ready(&FutureDoneCallbackType));
  FAIL_IF_MINUS_ONE(pyproxy_init_js());

  success = true;
finally:
  Py_CLEAR(_pyodide_core);
  return 0;
}
