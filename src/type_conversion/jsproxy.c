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

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"
#include "Python.h"
#include "structmember.h"

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(create_future);
_Py_IDENTIFIER(set_exception);
_Py_IDENTIFIER(set_result);
_Py_IDENTIFIER(__await__);

static PyObject* asyncio_get_event_loop;


static PyTypeObject* PyExc_BaseException_Type;

static PyObject*
JsBoundMethod_cnew(int this_, const char* name);

////////////////////////////////////////////////////////////
// JsProxy
//
// This is a Python object that provides idiomatic access to a Javascript
// object.

typedef struct
{
  PyObject_HEAD int js;
  PyObject* bytes;
  PyObject* future; // for promises
} JsProxy;

static void
JsProxy_dealloc(JsProxy* self)
{
  hiwire_decref(self->js);
  Py_CLEAR(self->bytes);
  Py_CLEAR(self->future);
  Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject*
JsProxy_Repr(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;
  int idrepr = hiwire_to_string(self->js);
  PyObject* pyrepr = js2python(idrepr);
  return pyrepr;
}

static PyObject*
JsProxy_GetAttr(PyObject* o, PyObject* attr_name)
{
  JsProxy* self = (JsProxy*)o;

  PyObject* str = PyObject_Str(attr_name);
  if (str == NULL) {
    return NULL;
  }

  const char* key = PyUnicode_AsUTF8(str);

  if (strncmp(key, "new", 4) == 0 || strncmp(key, "_has_bytes", 11) == 0 ||
      strncmp(key, "__await__", 10) == 0) {
    Py_DECREF(str);
    return PyObject_GenericGetAttr(o, attr_name);
  } else if (strncmp(key, "typeof", 7) == 0) {
    Py_DECREF(str);
    int idval = hiwire_typeof(self->js);
    PyObject* result = js2python(idval);
    hiwire_decref(idval);
    return result;
  }

  int idresult = hiwire_get_member_string(self->js, (int)key);
  Py_DECREF(str);

  if (idresult == -1) {
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
JsProxy_SetAttr(PyObject* o, PyObject* attr_name, PyObject* pyvalue)
{
  JsProxy* self = (JsProxy*)o;

  PyObject* attr_name_py_str = PyObject_Str(attr_name);
  if (attr_name_py_str == NULL) {
    return -1;
  }
  const char* key = PyUnicode_AsUTF8(attr_name_py_str);

  if (pyvalue == NULL) {
    hiwire_delete_member_string(self->js, (int)key);
  } else {
    int idvalue = python2js(pyvalue);
    hiwire_set_member_string(self->js, (int)key, idvalue);
    hiwire_decref(idvalue);
  }
  Py_DECREF(attr_name_py_str);

  return 0;
}

static PyObject*
JsProxy_Call(PyObject* o, PyObject* args, PyObject* kwargs)
{
  JsProxy* self = (JsProxy*)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  int idargs = hiwire_array();

  for (Py_ssize_t i = 0; i < nargs; ++i) {
    int idarg = python2js(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(idargs, idarg);
    hiwire_decref(idarg);
  }

  if (PyDict_Size(kwargs)) {
    int idkwargs = python2js(kwargs);
    hiwire_push_array(idargs, idkwargs);
    hiwire_decref(idkwargs);
  }

  int idresult = hiwire_call(self->js, idargs);
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
  int ida = python2js(a);
  int idb = python2js(b);
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

  int iditer = hiwire_get_iterator(self->js);

  if (iditer == HW_ERROR) {
    PyErr_SetString(PyExc_TypeError, "Object is not iterable");
    return NULL;
  }

  return js2python(iditer);
}

static PyObject*
JsProxy_IterNext(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;

  int idresult = hiwire_next(self->js);
  if (idresult == -1) {
    return NULL;
  }

  int iddone = hiwire_get_member_string(idresult, (int)"done");
  int done = hiwire_nonzero(iddone);
  hiwire_decref(iddone);

  PyObject* pyvalue = NULL;
  if (!done) {
    int idvalue = hiwire_get_member_string(idresult, (int)"value");
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

  int idargs = hiwire_array();

  for (Py_ssize_t i = 0; i < nargs; ++i) {
    int idarg = python2js(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(idargs, idarg);
    hiwire_decref(idarg);
  }

  int idresult = hiwire_new(self->js, idargs);
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

  int ididx = python2js(pyidx);
  int idresult = hiwire_get_member_obj(self->js, ididx);
  hiwire_decref(ididx);
  if (idresult == -1) {
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
  int ididx = python2js(pyidx);
  if (pyvalue == NULL) {
    hiwire_delete_member_obj(self->js, ididx);
  } else {
    int idvalue = python2js(pyvalue);
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
    PyErr_SetString(PyExc_BufferError, "Can not use as buffer");
    view->obj = NULL;
    return -1;
  }

  Py_ssize_t byteLength = hiwire_get_byteLength(self->js);

  void* ptr;
  if (hiwire_is_on_wasm_heap(self->js)) {
    ptr = (void*)hiwire_get_byteOffset(self->js);
  } else {
    if (self->bytes == NULL) {
      self->bytes = PyBytes_FromStringAndSize(NULL, byteLength);
      if (self->bytes == NULL) {
        return -1;
      }
    }

    ptr = PyBytes_AsString(self->bytes);
    hiwire_copy_to_ptr(self->js, (int)ptr);
  }

  int dtype = hiwire_get_dtype(self->js);

  char* format;
  Py_ssize_t itemsize;
  switch (dtype) {
    case INT8_TYPE:
      format = "b";
      itemsize = 1;
      break;
    case UINT8_TYPE:
      format = "B";
      itemsize = 1;
      break;
    case UINT8CLAMPED_TYPE:
      format = "B";
      itemsize = 1;
      break;
    case INT16_TYPE:
      format = "h";
      itemsize = 2;
      break;
    case UINT16_TYPE:
      format = "H";
      itemsize = 2;
      break;
    case INT32_TYPE:
      format = "i";
      itemsize = 4;
      break;
    case UINT32_TYPE:
      format = "I";
      itemsize = 4;
      break;
    case FLOAT32_TYPE:
      format = "f";
      itemsize = 4;
      break;
    case FLOAT64_TYPE:
      format = "d";
      itemsize = 8;
      break;
    default:
      format = "B";
      itemsize = 1;
      break;
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

static PyObject*
JsProxy_Dir(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;

  int iddir = hiwire_dir(self->js);
  PyObject* pydir = js2python(iddir);
  hiwire_decref(iddir);
  return pydir;
}

static int
JsProxy_Bool(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;
  return (self->js && hiwire_get_bool(self->js)) ? 1 : 0;
}

PyObject*
JsProxy_Await(JsProxy* self)
{
  if (self->future != NULL) {
    return _PyObject_CallMethodId(self->future, &PyId___await__, NULL);
  }

  if (!hiwire_is_promise(((JsProxy*)self)->js)) {
    PyErr_SetString(
      PyExc_TypeError,
      "Attempted to await a Javascript object which is not a promise.");
    return NULL;
  }

  PyObject* loop = _PyObject_CallNoArg(asyncio_get_event_loop);
  if (loop == NULL) {
    return NULL;
  }

  PyObject* fut = _PyObject_CallMethodId(loop, &PyId_create_future, NULL);
  if (fut == NULL) {
    return NULL;
  }

  Py_CLEAR(loop);
  PyObject* set_result = _PyObject_GetAttrId(fut, &PyId_set_result);
  PyObject* set_exception = _PyObject_GetAttrId(fut, &PyId_set_exception);

  int idargs = hiwire_array();
  int idarg = python2js(set_result);
  hiwire_push_array(idargs, idarg);
  hiwire_decref(idarg);
  hiwire_call_member(self->js, (int)"then", idargs);

  idarg = python2js(set_exception);
  hiwire_set_member_int(idargs, 0, idarg);
  hiwire_decref(idarg);
  hiwire_call_member(self->js, (int)"catch", idargs);
  hiwire_decref(idargs);

  self->future = fut;

  return _PyObject_CallMethodId(self->future, &PyId___await__, NULL);
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
  .tp_as_mapping = &JsProxy_MappingMethods,
  .tp_as_number = &JsProxy_NumberMethods,
  .tp_iter = JsProxy_GetIter,
  .tp_iternext = JsProxy_IterNext,
  .tp_repr = JsProxy_Repr,
  .tp_as_buffer = &JsProxy_BufferProcs
};

PyObject*
JsProxy_cnew(int idobj)
{
  JsProxy* self;
  self = (JsProxy*)JsProxyType.tp_alloc(&JsProxyType, 0);
  self->js = hiwire_incref(idobj);
  self->bytes = NULL;
  self->future = NULL;
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
JsProxy_new_error(int idobj)
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
  PyObject_HEAD int this_;
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

  int idargs = hiwire_array();

  for (Py_ssize_t i = 0; i < nargs; ++i) {
    int idarg = python2js(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(idargs, idarg);
    hiwire_decref(idarg);
  }

  int idresult = hiwire_call_member(self->this_, (int)self->name, idargs);
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
JsBoundMethod_cnew(int this_, const char* name)
{
  JsBoundMethod* self;
  self = (JsBoundMethod*)JsBoundMethodType.tp_alloc(&JsBoundMethodType, 0);
  self->this_ = hiwire_incref(this_);
  self->name = name;
  return (PyObject*)self;
}

////////////////////////////////////////////////////////////
// Public functions

int
JsProxy_Check(PyObject* x)
{
  return (PyObject_TypeCheck(x, &JsProxyType) ||
          PyObject_TypeCheck(x, &JsBoundMethodType));
}

int
JsProxy_AsJs(PyObject* x)
{
  JsProxy* js_proxy = (JsProxy*)x;
  return hiwire_incref(js_proxy->js);
}

int
JsException_Check(PyObject* x)
{
  return PyObject_TypeCheck(x, (PyTypeObject*)Exc_JsException);
}

int
JsException_AsJs(PyObject* err)
{
  JsExceptionObject* err_obj = (JsExceptionObject*)err;
  JsProxy* js_error = (JsProxy*)(err_obj->js_error);
  return hiwire_incref(js_error->js);
}

int
JsProxy_init()
{
<<<<<<< HEAD
  PyObject* module = PyImport_ImportModule("asyncio");
  if (module == NULL) {
    goto fail;
  }

  asyncio_get_event_loop = PyObject_GetAttrString(module, "get_event_loop");
  if (asyncio_get_event_loop == NULL) {
=======
  PyExc_BaseException_Type = (PyTypeObject*)PyExc_BaseException;
  _Exc_JsException.tp_base = (PyTypeObject*)PyExc_Exception;

  PyObject* module;
  PyObject* exc;

  // Add JsException to the pyodide module so people can catch it if they want.
  module = PyImport_ImportModule("pyodide");
  if (module == NULL) {
    goto fail;
  }
  if (PyObject_SetAttrString(module, "JsException", Exc_JsException)) {
>>>>>>> bb604b367c0de1a30f35994d5e9be2591481e13a
    goto fail;
  }

  Py_CLEAR(module);
<<<<<<< HEAD

  return (PyType_Ready(&JsProxyType) || PyType_Ready(&JsBoundMethodType));
=======
  return (PyType_Ready(&JsProxyType) || PyType_Ready(&JsBoundMethodType) ||
          PyType_Ready(&_Exc_JsException));
>>>>>>> bb604b367c0de1a30f35994d5e9be2591481e13a

fail:
  Py_CLEAR(module);
  return -1;
}
