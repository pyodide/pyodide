#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <abstract.h> /* PySendResult */
#include <object.h>   /* sendfunc, Py_TPFLAGS_HAVE_AM_SEND */

typedef enum
{
  PYGEN_RETURN = 0,
  PYGEN_ERROR = -1,
  PYGEN_NEXT = 1,
} PySendResult;
typedef PySendResult (*sendfunc)(PyObject* iter,
                                 PyObject* value,
                                 PyObject** result);
#include "jsproxy.h"

#include "Python.h"
#include "hiwire.h"
#include "js2python.h"
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
JsBoundMethod_cnew(JsRef this_, const char* name);

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

static void
JsProxy_dealloc(JsProxy* self)
{
  hiwire_decref(self->js);
  Py_CLEAR(self->bytes);
  Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject*
JsProxy_Repr(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;
  JsRef idrepr = hiwire_to_string(self->js);
  PyObject* pyrepr = js2python(idrepr);
  return pyrepr;
}

PyObject*
JsProxy_typeof(PyObject* obj, void* _unused)
{
  JsProxy* self = (JsProxy*)obj;
  JsRef idval = hiwire_typeof(self->js);
  PyObject* result = js2python(idval);
  hiwire_decref(idval);
  return result;
}

static PyObject*
JsProxy_GetAttr(PyObject* o, PyObject* attr)
{
  PyObject* result = PyObject_GenericGetAttr(o, attr);
  if (result != NULL) {
    return result;
  }
  PyErr_Clear();

  JsProxy* self = (JsProxy*)o;
  const char* key = PyUnicode_AsUTF8(attr);
  if (key == NULL) {
    return NULL;
  }

  JsRef idresult = hiwire_get_member_string(self->js, key);

  if (idresult == NULL) {
    PyErr_SetString(PyExc_AttributeError, key);
    return NULL;
  }

  if (hiwire_is_function(idresult)) {
    hiwire_decref(idresult);
    return JsBoundMethod_cnew(self->js, key);
  }

  PyObject* pyresult = js2python(idresult);
  hiwire_decref(idresult);
  return pyresult;
}

static int
JsProxy_SetAttr(PyObject* o, PyObject* attr, PyObject* pyvalue)
{
  JsProxy* self = (JsProxy*)o;
  const char* key = PyUnicode_AsUTF8(attr);
  if (key == NULL) {
    return -1;
  }

  if (pyvalue == NULL) {
    hiwire_delete_member_string(self->js, key);
  } else {
    JsRef idvalue = python2js(pyvalue);
    hiwire_set_member_string(self->js, key, idvalue);
    hiwire_decref(idvalue);
  }

  return 0;
}

static PyObject*
JsProxy_Call(PyObject* o, PyObject* args, PyObject* kwargs)
{
  JsProxy* self = (JsProxy*)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  JsRef idargs = hiwire_array();

  for (Py_ssize_t i = 0; i < nargs; ++i) {
    JsRef idarg = python2js(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(idargs, idarg);
    hiwire_decref(idarg);
  }

  if (PyDict_Size(kwargs)) {
    JsRef idkwargs = python2js(kwargs);
    hiwire_push_array(idargs, idkwargs);
    hiwire_decref(idkwargs);
  }

  JsRef idresult = hiwire_call(self->js, idargs);
  hiwire_decref(idargs);
  PyObject* pyresult = js2python(idresult);
  hiwire_decref(idresult);
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

#define QUIT_IF_NULL(x)                                                        \
  do {                                                                         \
    if (x == NULL) {                                                           \
      goto finally;                                                            \
    }                                                                          \
  } while (0)

#define QUIT_IF_NZ(x)                                                          \
  do {                                                                         \
    if (x != 0) {                                                              \
      goto finally;                                                            \
    }                                                                          \
  } while (0)

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
  QUIT_IF_NULL(object__dir__);
  keys = PyObject_CallFunctionObjArgs(object__dir__, self, NULL);
  QUIT_IF_NULL(keys);
  result_set = PySet_New(keys);
  QUIT_IF_NULL(result_set);

  // Now get attributes of js object
  iddir = hiwire_dir(GET_JSREF(self));
  pydir = js2python(iddir);
  QUIT_IF_NULL(pydir);
  // Merge and sort
  QUIT_IF_NZ(_PySet_Update(result_set, pydir));
  result = PyList_New(0);
  QUIT_IF_NULL(result);
  null_or_pynone = _PyList_Extend((PyListObject*)result, result_set);
  QUIT_IF_NULL(null_or_pynone);
  QUIT_IF_NZ(PyList_Sort(result));

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

#define QUIT_IF_NULL(x)                                                        \
  do {                                                                         \
    if (x == NULL) {                                                           \
      goto finally;                                                            \
    }                                                                          \
  } while (0)

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
  QUIT_IF_NULL(loop);

  fut = _PyObject_CallMethodId(loop, &PyId_create_future, NULL);
  QUIT_IF_NULL(fut);

  set_result = _PyObject_GetAttrId(fut, &PyId_set_result);
  QUIT_IF_NULL(set_result);
  set_exception = _PyObject_GetAttrId(fut, &PyId_set_exception);
  QUIT_IF_NULL(set_exception);

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
  // { "__await__", (PyCFunction)JsProxy_Await, METH_NOARGS, ""},
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
  .tp_flags = Py_TPFLAGS_DEFAULT,
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

PyObject*
JsProxy_cnew(JsRef idobj)
{
  JsProxy* self;
  self = (JsProxy*)JsProxyType.tp_alloc(&JsProxyType, 0);
  self->js = hiwire_incref(idobj);
  self->bytes = NULL;
  self->awaited = false;
  return (PyObject*)self;
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
  PyObject_HEAD JsRef this_;
  const char* name;
} JsBoundMethod;

static void
JsBoundMethod_dealloc(JsBoundMethod* self)
{
  hiwire_decref(self->this_);
  Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject*
JsBoundMethod_Call(PyObject* o, PyObject* args, PyObject* kwargs)
{
  JsBoundMethod* self = (JsBoundMethod*)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  JsRef idargs = hiwire_array();

  for (Py_ssize_t i = 0; i < nargs; ++i) {
    JsRef idarg = python2js(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(idargs, idarg);
    hiwire_decref(idarg);
  }

  JsRef idresult = hiwire_call_member(self->this_, self->name, idargs);
  hiwire_decref(idargs);
  PyObject* pyresult = js2python(idresult);
  hiwire_decref(idresult);
  return pyresult;
}

static PyTypeObject JsBoundMethodType = {
  .tp_name = "JsBoundMethod",
  .tp_basicsize = sizeof(JsBoundMethod),
  .tp_dealloc = (destructor)JsBoundMethod_dealloc,
  .tp_call = JsBoundMethod_Call,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = "A proxy to make it possible to call Javascript bound methods from "
            "Python."
};

static PyObject*
JsBoundMethod_cnew(JsRef this_, const char* name)
{
  JsBoundMethod* self;
  self = (JsBoundMethod*)JsBoundMethodType.tp_alloc(&JsBoundMethodType, 0);
  self->this_ = hiwire_incref(this_);
  self->name = name;
  return (PyObject*)self;
}

////////////////////////////////////////////////////////////
// Public functions

bool
JsProxy_Check(PyObject* x)
{
  return (PyObject_TypeCheck(x, &JsProxyType) ||
          PyObject_TypeCheck(x, &JsBoundMethodType));
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

int
JsProxy_init()
{
  PyObject* module = NULL;

  module = PyImport_ImportModule("asyncio");
  if (module == NULL) {
    goto fail;
  }

  asyncio_get_event_loop = PyObject_GetAttrString(module, "get_event_loop");
  if (asyncio_get_event_loop == NULL) {
    goto fail;
  }
  PyExc_BaseException_Type = (PyTypeObject*)PyExc_BaseException;
  _Exc_JsException.tp_base = (PyTypeObject*)PyExc_Exception;

  Py_CLEAR(module);
  // Add JsException to the pyodide module so people can catch it if they want.
  module = PyImport_ImportModule("pyodide");
  if (module == NULL) {
    goto fail;
  }
  if (PyObject_SetAttrString(module, "JsException", Exc_JsException)) {
    goto fail;
  }

  Py_CLEAR(module);
  return (PyType_Ready(&JsProxyType) || PyType_Ready(&JsBoundMethodType) ||
          PyType_Ready(&_Exc_JsException));

fail:
  Py_CLEAR(module);
  return -1;
}
