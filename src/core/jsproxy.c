#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "hiwire.h"
#include "js2python.h"
#include "jsproxy.h"
#include "python2js.h"

#include "structmember.h"

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(create_future);
_Py_IDENTIFIER(set_exception);
_Py_IDENTIFIER(set_result);
_Py_IDENTIFIER(__await__);

static PyObject* asyncio_get_event_loop;

static PyTypeObject* PyExc_BaseException_Type;

_Py_IDENTIFIER(__dir__);

static PyObject*
JsBoundMethod_cnew(JsRef func, JsRef this_);

////////////////////////////////////////////////////////////
// JsProxy
//
// This is a Python object that provides idiomatic access to a Javascript
// object.

// clang-format off
typedef struct
{
  PyObject_HEAD
  JsRef js;
  PyObject* bytes;
  bool awaited; // for promises
} JsProxy;
// clang-format on

#define JsProxy_REF(x) (((JsProxy*)x)->js)

static void
JsProxy_dealloc(JsProxy* self)
{
  hiwire_decref(self->js);
  Py_CLEAR(self->bytes);
  Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject*
JsProxy_Repr(PyObject* self)
{
  JsRef idrepr = hiwire_to_string(JsProxy_REF(self));
  PyObject* pyrepr = js2python(idrepr);
  return pyrepr;
}

PyObject*
JsProxy_typeof(PyObject* self, void* _unused)
{
  JsRef idval = hiwire_typeof(JsProxy_REF(self));
  PyObject* result = js2python(idval);
  hiwire_decref(idval);
  return result;
}

static PyObject*
JsProxy_GetAttr(PyObject* self, PyObject* attr)
{
  PyObject* result = PyObject_GenericGetAttr(self, attr);
  if (result != NULL) {
    return result;
  }
  PyErr_Clear();

  bool success = false;
  JsRef idresult;
  // result:
  PyObject* pyresult;

  const char* key = PyUnicode_AsUTF8(attr);
  FAIL_IF_NULL(key);

  idresult = hiwire_get_member_string(JsProxy_REF(self), key);
  if (idresult == NULL) {
    PyErr_SetString(PyExc_AttributeError, key);
    FAIL();
  }

  if (!hiwire_is_pyproxy(idresult) && hiwire_is_function(idresult)) {
    pyresult = JsBoundMethod_cnew(idresult, JsProxy_REF(self));
  } else {
    pyresult = js2python(idresult);
  }
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  hiwire_decref(idresult);
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

static int
JsProxy_SetAttr(PyObject* self, PyObject* attr, PyObject* pyvalue)
{
  bool success = false;
  JsRef idvalue = NULL;

  const char* key = PyUnicode_AsUTF8(attr);
  FAIL_IF_NULL(key);

  if (pyvalue == NULL) {
    FAIL_IF_MINUS_ONE(hiwire_delete_member_string(JsProxy_REF(self), key));
  } else {
    idvalue = python2js(pyvalue);
    FAIL_IF_MINUS_ONE(
      hiwire_set_member_string(JsProxy_REF(self), key, idvalue));
  }

  success = true;
finally:
  hiwire_CLEAR(idvalue);
  return success ? 0 : -1;
}

static PyObject*
JsProxy_Call(PyObject* self, PyObject* args, PyObject* kwargs)
{
  bool success = false;
  JsRef idargs = NULL;
  JsRef idarg = NULL;
  JsRef idkwargs = NULL;
  JsRef idresult = NULL;
  // result:
  PyObject* pyresult;
  Py_ssize_t nargs = PyTuple_Size(args);

  idargs = hiwire_array();
  for (Py_ssize_t i = 0; i < nargs; ++i) {
    idarg = python2js(PyTuple_GET_ITEM(args, i));
    FAIL_IF_NULL(idarg);
    FAIL_IF_MINUS_ONE(hiwire_push_array(idargs, idarg));
    hiwire_CLEAR(idarg);
  }

  if (PyDict_Size(kwargs)) {
    idkwargs = python2js(kwargs);
    FAIL_IF_MINUS_ONE(hiwire_push_array(idargs, idkwargs));
  }

  idresult = hiwire_call(JsProxy_REF(self), idargs);
  FAIL_IF_NULL(idresult);
  pyresult = js2python(idresult);
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  hiwire_CLEAR(idargs);
  hiwire_CLEAR(idarg);
  hiwire_CLEAR(idkwargs);
  hiwire_CLEAR(idresult);
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

static PyObject*
JsProxy_RichCompare(PyObject* a, PyObject* b, int op)
{
  JsProxy* aproxy = (JsProxy*)a;

  if (!JsProxy_Check(b)) {
    switch (op) {
      case Py_EQ:
        Py_RETURN_FALSE;
      case Py_NE:
        Py_RETURN_TRUE;
      default:
        return Py_NotImplemented;
    }
  }

  int result;
  JsRef ida = python2js(a);
  JsRef idb = python2js(b);
  switch (op) {
    case Py_LT:
      result = hiwire_less_than(ida, idb);
      break;
    case Py_LE:
      result = hiwire_less_than_equal(ida, idb);
      break;
    case Py_EQ:
      result = hiwire_equal(ida, idb);
      break;
    case Py_NE:
      result = hiwire_not_equal(ida, idb);
      break;
    case Py_GT:
      result = hiwire_greater_than(ida, idb);
      break;
    case Py_GE:
      result = hiwire_greater_than_equal(ida, idb);
      break;
  }

  hiwire_decref(ida);
  hiwire_decref(idb);
  if (result) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

static PyObject*
JsProxy_GetIter(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;

  JsRef iditer = hiwire_get_iterator(self->js);

  if (iditer == NULL) {
    PyErr_SetString(PyExc_TypeError, "Object is not iterable");
    return NULL;
  }

  return js2python(iditer);
}

static PyObject*
JsProxy_IterNext(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;

  JsRef idresult = hiwire_next(self->js);
  if (idresult == NULL) {
    return NULL;
  }

  JsRef iddone = hiwire_get_member_string(idresult, "done");
  int done = hiwire_nonzero(iddone);
  hiwire_decref(iddone);

  PyObject* pyvalue = NULL;
  if (!done) {
    JsRef idvalue = hiwire_get_member_string(idresult, "value");
    pyvalue = js2python(idvalue);
    hiwire_decref(idvalue);
  }

  hiwire_decref(idresult);
  return pyvalue;
}

static PyObject*
JsProxy_New(PyObject* o, PyObject* args, PyObject* kwargs)
{
  JsProxy* self = (JsProxy*)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  JsRef idargs = hiwire_array();

  for (Py_ssize_t i = 0; i < nargs; ++i) {
    JsRef idarg = python2js(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(idargs, idarg);
    hiwire_decref(idarg);
  }

  JsRef idresult = hiwire_new(self->js, idargs);
  hiwire_decref(idargs);
  PyObject* pyresult = js2python(idresult);
  hiwire_decref(idresult);
  return pyresult;
}

static Py_ssize_t
JsProxy_length(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;

  return hiwire_get_length(self->js);
}

static PyObject*
JsProxy_subscript(PyObject* o, PyObject* pyidx)
{
  JsProxy* self = (JsProxy*)o;

  JsRef ididx = python2js(pyidx);
  JsRef idresult = hiwire_get_member_obj(self->js, ididx);
  hiwire_decref(ididx);
  if (idresult == NULL) {
    PyErr_SetObject(PyExc_KeyError, pyidx);
    return NULL;
  }
  PyObject* pyresult = js2python(idresult);
  hiwire_decref(idresult);
  return pyresult;
}

static int
JsProxy_ass_subscript(PyObject* o, PyObject* pyidx, PyObject* pyvalue)
{
  JsProxy* self = (JsProxy*)o;
  JsRef ididx = python2js(pyidx);
  if (pyvalue == NULL) {
    hiwire_delete_member_obj(self->js, ididx);
  } else {
    JsRef idvalue = python2js(pyvalue);
    hiwire_set_member_obj(self->js, ididx, idvalue);
    hiwire_decref(idvalue);
  }
  hiwire_decref(ididx);
  return 0;
}

static int
JsProxy_GetBuffer(PyObject* o, Py_buffer* view, int flags)
{
  JsProxy* self = (JsProxy*)o;

  if (!hiwire_is_typedarray(self->js)) {
    goto fail;
  }

  Py_ssize_t byteLength = hiwire_get_byteLength(self->js);

  void* ptr;
  if (hiwire_is_on_wasm_heap(self->js)) {
    ptr = (void*)hiwire_get_byteOffset(self->js);
  } else {
    if (self->bytes == NULL) {
      self->bytes = PyBytes_FromStringAndSize(NULL, byteLength);
      if (self->bytes == NULL) {
        goto fail;
      }
    }
    ptr = PyBytes_AsString(self->bytes);
    hiwire_copy_to_ptr(self->js, ptr);
  }

  char* format;
  Py_ssize_t itemsize;
  hiwire_get_dtype(self->js, &format, &itemsize);
  if (format == NULL) {
    char* typename = hiwire_constructor_name(self->js);
    PyErr_Format(
      PyExc_RuntimeError,
      "Unknown typed array type '%s'. This is a problem with Pyodide, please "
      "open an issue about it here: "
      "https://github.com/iodide-project/pyodide/issues/new",
      typename);
    free(typename);

    goto fail;
  }

  Py_INCREF(self);

  view->buf = ptr;
  view->obj = (PyObject*)self;
  view->len = byteLength;
  view->readonly = 0;
  view->itemsize = itemsize;
  view->format = format;
  view->ndim = 1;
  view->shape = NULL;
  view->strides = NULL;
  view->suboffsets = NULL;

  return 0;
fail:
  if (!PyErr_Occurred()) {
    PyErr_SetString(PyExc_BufferError, "Can not use as buffer");
  }
  view->obj = NULL;
  return -1;
}

static PyObject*
JsProxy_HasBytes(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;

  if (self->bytes == NULL) {
    Py_RETURN_FALSE;
  } else {
    Py_RETURN_TRUE;
  }
}

#define GET_JSREF(x) (((JsProxy*)x)->js)

static PyObject*
JsProxy_Dir(PyObject* self)
{
  bool success = false;
  PyObject* object__dir__ = NULL;
  PyObject* keys = NULL;
  PyObject* result_set = NULL;
  JsRef iddir = NULL;
  PyObject* pydir = NULL;
  PyObject* null_or_pynone = NULL;

  PyObject* result = NULL;

  // First get base __dir__ via object.__dir__(self)
  // Would have been nice if they'd supplied PyObject_GenericDir...
  object__dir__ =
    _PyObject_GetAttrId((PyObject*)&PyBaseObject_Type, &PyId___dir__);
  FAIL_IF_NULL(object__dir__);
  keys = PyObject_CallFunctionObjArgs(object__dir__, self, NULL);
  FAIL_IF_NULL(keys);
  result_set = PySet_New(keys);
  FAIL_IF_NULL(result_set);

  // Now get attributes of js object
  iddir = hiwire_dir(GET_JSREF(self));
  pydir = js2python(iddir);
  FAIL_IF_NULL(pydir);
  // Merge and sort
  FAIL_IF_MINUS_ONE(_PySet_Update(result_set, pydir));
  result = PyList_New(0);
  FAIL_IF_NULL(result);
  null_or_pynone = _PyList_Extend((PyListObject*)result, result_set);
  FAIL_IF_NULL(null_or_pynone);
  FAIL_IF_MINUS_ONE(PyList_Sort(result));

  success = true;
finally:
  Py_CLEAR(object__dir__);
  Py_CLEAR(keys);
  Py_CLEAR(result_set);
  hiwire_decref(iddir);
  Py_CLEAR(pydir);
  Py_CLEAR(null_or_pynone);
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

static int
JsProxy_Bool(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;
  return hiwire_get_bool(self->js) ? 1 : 0;
}

PyObject*
JsProxy_Await(JsProxy* self)
{
  // Guards
  if (self->awaited) {
    PyErr_SetString(PyExc_RuntimeError,
                    "cannot reuse already awaited coroutine");
    return NULL;
  }

  if (!hiwire_is_promise(self->js)) {
    PyObject* str = JsProxy_Repr((PyObject*)self);
    const char* str_utf8 = PyUnicode_AsUTF8(str);
    PyErr_Format(PyExc_TypeError,
                 "object %s can't be used in 'await' expression",
                 str_utf8);
    return NULL;
  }

  // Main
  PyObject* result = NULL;

  PyObject* loop = NULL;
  PyObject* fut = NULL;
  PyObject* set_result = NULL;
  PyObject* set_exception = NULL;

  loop = _PyObject_CallNoArg(asyncio_get_event_loop);
  FAIL_IF_NULL(loop);

  fut = _PyObject_CallMethodId(loop, &PyId_create_future, NULL);
  FAIL_IF_NULL(fut);

  set_result = _PyObject_GetAttrId(fut, &PyId_set_result);
  FAIL_IF_NULL(set_result);
  set_exception = _PyObject_GetAttrId(fut, &PyId_set_exception);
  FAIL_IF_NULL(set_exception);

  JsRef promise_id = hiwire_resolve_promise(self->js);
  JsRef idargs = hiwire_array();
  JsRef idarg;
  // TODO: does this leak set_result and set_exception? See #1006.
  idarg = python2js(set_result);
  hiwire_push_array(idargs, idarg);
  hiwire_decref(idarg);
  idarg = python2js(set_exception);
  hiwire_push_array(idargs, idarg);
  hiwire_decref(idarg);
  hiwire_decref(hiwire_call_member(promise_id, "then", idargs));
  hiwire_decref(promise_id);
  hiwire_decref(idargs);
  result = _PyObject_CallMethodId(fut, &PyId___await__, NULL);

finally:
  Py_CLEAR(loop);
  Py_CLEAR(set_result);
  Py_CLEAR(set_exception);
  Py_DECREF(fut);
  return result;
}

// clang-format off
static PyMappingMethods JsProxy_MappingMethods = {
  JsProxy_length,
  JsProxy_subscript,
  JsProxy_ass_subscript,
};

static PyNumberMethods JsProxy_NumberMethods = {
  .nb_bool = JsProxy_Bool
};

static PyBufferProcs JsProxy_BufferProcs = {
  JsProxy_GetBuffer,
  NULL
};

static PyMethodDef JsProxy_Methods[] = {
  { "new",
    (PyCFunction)JsProxy_New,
    METH_VARARGS | METH_KEYWORDS,
    "Construct a new instance" },
  { "__iter__",
    (PyCFunction)JsProxy_GetIter,
    METH_NOARGS,
    "Get an iterator over the object" },
  { "__await__", (PyCFunction)JsProxy_Await, METH_NOARGS, ""},
  { "_has_bytes",
    (PyCFunction)JsProxy_HasBytes,
    METH_NOARGS,
    "Returns true if instance has buffer memory. For testing only." },
  { "__dir__",
    (PyCFunction)JsProxy_Dir,
    METH_NOARGS,
    "Returns a list of the members and methods on the object." },
  { NULL }
};
// clang-format on

static PyAsyncMethods JsProxy_asyncMethods = { .am_await =
                                                 (unaryfunc)JsProxy_Await };
static PyGetSetDef JsProxy_GetSet[] = { { "typeof", .get = JsProxy_typeof },
                                        { NULL } };

static PyTypeObject JsProxyType = {
  .tp_name = "JsProxy",
  .tp_basicsize = sizeof(JsProxy),
  .tp_dealloc = (destructor)JsProxy_dealloc,
  .tp_call = JsProxy_Call,
  .tp_getattro = JsProxy_GetAttr,
  .tp_setattro = JsProxy_SetAttr,
  .tp_as_async = &JsProxy_asyncMethods,
  .tp_richcompare = JsProxy_RichCompare,
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .tp_doc = "A proxy to make a Javascript object behave like a Python object",
  .tp_methods = JsProxy_Methods,
  .tp_getset = JsProxy_GetSet,
  .tp_as_mapping = &JsProxy_MappingMethods,
  .tp_as_number = &JsProxy_NumberMethods,
  .tp_iter = JsProxy_GetIter,
  .tp_iternext = JsProxy_IterNext,
  .tp_repr = JsProxy_Repr,
  .tp_as_buffer = &JsProxy_BufferProcs
};

// TODO: Instead use tp_new and Python's inheritance system
void
JsProxy_cinit(PyObject* obj, JsRef idobj)
{
  JsProxy* self = (JsProxy*)obj;
  self->js = hiwire_incref(idobj);
  self->bytes = NULL;
  self->awaited = false;
}

PyObject*
JsProxy_cnew(JsRef idobj)
{
  PyObject* self = JsProxyType.tp_alloc(&JsProxyType, 0);
  JsProxy_cinit(self, idobj);
  return self;
}

typedef struct
{
  PyException_HEAD PyObject* js_error;
} JsExceptionObject;

static PyMemberDef JsException_members[] = {
  { "js_error",
    T_OBJECT_EX,
    offsetof(JsExceptionObject, js_error),
    READONLY,
    PyDoc_STR("A wrapper around a Javascript Error to allow the Error to be "
              "thrown in Python.") },
  { NULL } /* Sentinel */
};

static int
JsException_init(JsExceptionObject* self, PyObject* args, PyObject* kwds)
{
  Py_ssize_t size = PyTuple_GET_SIZE(args);
  PyObject* js_error;
  if (size == 0) {
    PyErr_SetString(
      PyExc_TypeError,
      "__init__() missing 1 required positional argument: 'js_error'.");
    return -1;
  }

  js_error = PyTuple_GET_ITEM(args, 0);
  if (!PyObject_TypeCheck(js_error, &JsProxyType)) {
    PyErr_SetString(PyExc_TypeError,
                    "Argument 'js_error' must be an instance of JsProxy.");
    return -1;
  }

  if (PyExc_BaseException_Type->tp_init((PyObject*)self, args, kwds) == -1)
    return -1;

  Py_CLEAR(self->js_error);
  Py_INCREF(js_error);
  self->js_error = js_error;
  return 0;
}

static int
JsException_clear(JsExceptionObject* self)
{
  Py_CLEAR(self->js_error);
  return PyExc_BaseException_Type->tp_clear((PyObject*)self);
}

static void
JsException_dealloc(JsExceptionObject* self)
{
  JsException_clear(self);
  PyExc_BaseException_Type->tp_free((PyObject*)self);
}

static int
JsException_traverse(JsExceptionObject* self, visitproc visit, void* arg)
{
  Py_VISIT(self->js_error);
  return PyExc_BaseException_Type->tp_traverse((PyObject*)self, visit, arg);
}

static PyTypeObject _Exc_JsException = {
  PyVarObject_HEAD_INIT(NULL, 0) "JsException",
  .tp_basicsize = sizeof(JsExceptionObject),
  .tp_dealloc = (destructor)JsException_dealloc,
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,
  .tp_doc =
    PyDoc_STR("An exception which wraps a Javascript error. The js_error field "
              "contains a JsProxy for the wrapped error."),
  .tp_traverse = (traverseproc)JsException_traverse,
  .tp_clear = (inquiry)JsException_clear,
  .tp_members = JsException_members,
  // PyExc_Exception isn't static so we fill in .tp_base in JsProxy_init
  // .tp_base = (PyTypeObject *)PyExc_Exception,
  .tp_dictoffset = offsetof(JsExceptionObject, dict),
  .tp_init = (initproc)JsException_init
};
static PyObject* Exc_JsException = (PyObject*)&_Exc_JsException;

PyObject*
JsProxy_new_error(JsRef idobj)
{
  PyObject* proxy = JsProxy_cnew(idobj);
  PyObject* result = PyObject_CallFunctionObjArgs(Exc_JsException, proxy, NULL);
  return result;
}

////////////////////////////////////////////////////////////
// JsBoundMethod
//
// A special class for bound methods

typedef struct
{
  JsProxy super;
  JsRef this_;
} JsBoundMethod;

#define JsBoundMethod_THIS(x) (((JsBoundMethod*)x)->this_)

static void
JsBoundMethod_dealloc(PyObject* self)
{
  hiwire_CLEAR(JsBoundMethod_THIS(self));
  Py_TYPE(self)->tp_free(self);
}

// TODO: once #1033 is accepted, switch to VECTOR_CALL for this and unify the
// argument handling here and there so that bound methods and unbound methods
// actually behave the same.
static PyObject*
JsBoundMethod_Call(PyObject* self, PyObject* args, PyObject* kwargs)
{
  Py_ssize_t nargs = PyTuple_Size(args);

  JsRef idargs = hiwire_array();

  for (Py_ssize_t i = 0; i < nargs; ++i) {
    JsRef idarg = python2js(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(idargs, idarg);
    hiwire_decref(idarg);
  }

  JsRef idresult =
    hiwire_call_bound(JsProxy_REF(self), JsBoundMethod_THIS(self), idargs);
  hiwire_decref(idargs);
  PyObject* pyresult = js2python(idresult);
  hiwire_decref(idresult);
  return pyresult;
}

static PyTypeObject JsBoundMethodType = {
  //.tp_base = &JsProxy, // We have to do this in jsproxy_init.
  .tp_name = "JsBoundMethod",
  .tp_basicsize = sizeof(JsBoundMethod),
  .tp_dealloc = (destructor)JsBoundMethod_dealloc,
  .tp_call = JsBoundMethod_Call,
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .tp_doc = "A proxy to make it possible to call Javascript bound methods from "
            "Python."
};

// TODO: use tp_new and Python inheritance system
static PyObject*
JsBoundMethod_cnew(JsRef func, JsRef this_)
{
  PyObject* self = JsBoundMethodType.tp_alloc(&JsBoundMethodType, 0);
  JsProxy_cinit(self, func);
  JsBoundMethod_THIS(self) = hiwire_incref(this_);
  return self;
}

////////////////////////////////////////////////////////////
// Public functions

bool
JsProxy_Check(PyObject* x)
{
  return PyObject_TypeCheck(x, &JsProxyType);
}

JsRef
JsProxy_AsJs(PyObject* x)
{
  JsProxy* js_proxy = (JsProxy*)x;
  return hiwire_incref(js_proxy->js);
}

bool
JsException_Check(PyObject* x)
{
  return PyObject_TypeCheck(x, (PyTypeObject*)Exc_JsException);
}

JsRef
JsException_AsJs(PyObject* err)
{
  JsExceptionObject* err_obj = (JsExceptionObject*)err;
  JsProxy* js_error = (JsProxy*)(err_obj->js_error);
  return hiwire_incref(js_error->js);
}

// Copied from Python 3.9
// TODO: remove once we update to Python 3.9
static int
PyModule_AddType(PyObject* module, PyTypeObject* type)
{
  if (PyType_Ready(type) < 0) {
    return -1;
  }

  const char* name = _PyType_Name(type);
  assert(name != NULL);

  Py_INCREF(type);
  if (PyModule_AddObject(module, name, (PyObject*)type) < 0) {
    Py_DECREF(type);
    return -1;
  }

  return 0;
}

int
JsProxy_init(PyObject* core_module)
{
  bool success = false;

  PyObject* asyncio_module = NULL;
  PyObject* pyodide_module = NULL;

  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);

  asyncio_get_event_loop =
    _PyObject_GetAttrId(asyncio_module, &PyId_get_event_loop);
  FAIL_IF_NULL(asyncio_get_event_loop);

  PyExc_BaseException_Type = (PyTypeObject*)PyExc_BaseException;
  _Exc_JsException.tp_base = (PyTypeObject*)PyExc_Exception;

  JsBoundMethodType.tp_base = &JsProxyType;
  // Add JsException to the pyodide module so people can catch it if they want.
  FAIL_IF_MINUS_ONE(PyModule_AddType(core_module, &JsProxyType));
  FAIL_IF_MINUS_ONE(PyModule_AddType(core_module, &JsBoundMethodType));
  FAIL_IF_MINUS_ONE(PyModule_AddType(core_module, &_Exc_JsException));

  success = true;
finally:
  Py_CLEAR(asyncio_module);
  Py_CLEAR(pyodide_module);
  return success ? 0 : -1;
}
