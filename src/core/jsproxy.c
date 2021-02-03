#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "hiwire.h"
#include "js2python.h"
#include "jsproxy.h"
#include "python2js.h"

#include "structmember.h"

// clang-format off
#define IS_ITERABLE  (1<<0)
#define IS_ITERATOR  (1<<1)
#define HAS_LENGTH   (1<<2)
#define HAS_GET      (1<<3)
#define HAS_SET      (1<<4)
#define HAS_HAS      (1<<5)
#define HAS_INCLUDES (1<<6)
#define IS_AWAITABLE (1<<7)
#define IS_BUFFER    (1<<8)
#define IS_CALLABLE  (1<<9)
#define IS_ARRAY     (1<<10)
// clang-format on

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(create_future);
_Py_IDENTIFIER(set_exception);
_Py_IDENTIFIER(set_result);
_Py_IDENTIFIER(__await__);
_Py_IDENTIFIER(__dir__);

static PyObject* asyncio_get_event_loop;

static PyTypeObject* PyExc_BaseException_Type;

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
// fields for methods
  JsRef this_;
  vectorcallfunc vectorcall;
  int supports_kwargs; // -1 : don't know. 0 : no, 1 : yes
} JsProxy;
// clang-format on

#define JsProxy_REF(x) (((JsProxy*)x)->js)

static void
JsProxy_dealloc(JsProxy* self)
{
  hiwire_CLEAR(self->js);
  hiwire_CLEAR(self->this_);
  Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject*
JsProxy_Repr(PyObject* self)
{
  JsRef idrepr = hiwire_to_string(JsProxy_REF(self));
  PyObject* pyrepr = js2python(idrepr);
  return pyrepr;
}

static PyObject*
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
  if (strcmp(key, "keys") == 0 && hiwire_is_array(JsProxy_REF(self))) {
    // Sometimes Python APIs test for the existence of a "keys" function
    // to decide whether something should be treated like a dict.
    // This mixes badly with the javascript Array.keys api, so pretend that it
    // doesn't exist. (Array.keys isn't very useful anyways so hopefully this
    // won't confuse too many people...)
    PyErr_SetString(PyExc_AttributeError, key);
    FAIL();
  }

  idresult = hiwire_get_member_string(JsProxy_REF(self), key);
  if (idresult == NULL) {
    PyErr_SetString(PyExc_AttributeError, key);
    FAIL();
  }

  if (!hiwire_is_pyproxy(idresult) && hiwire_is_function(idresult)) {
    pyresult = JsProxy_create_with_this(idresult, JsProxy_REF(self));
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

#define JsProxy_JSREF(x) (((JsProxy*)x)->js)

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
JsProxy_object_entries(PyObject* o, PyObject* _args)
{
  JsProxy* self = (JsProxy*)o;
  JsRef result_id = hiwire_object_entries(self->js);
  if (result_id == NULL) {
    return NULL;
  }
  PyObject* result = JsProxy_create(result_id);
  hiwire_decref(result_id);
  return result;
}

static Py_ssize_t
JsProxy_length(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;

  return hiwire_get_length(self->js);
}

static PyObject*
JsProxy_subscript_array(PyObject* o, PyObject* item)
{
  JsProxy* self = (JsProxy*)o;
  if (PyIndex_Check(item)) {
    Py_ssize_t i;
    i = PyNumber_AsSsize_t(item, PyExc_IndexError);
    if (i == -1 && PyErr_Occurred())
      return NULL;
    if (i < 0)
      i += hiwire_get_length(self->js);
    JsRef result = hiwire_get_member_int(self->js, i);
    if (result == NULL) {
      PyErr_SetObject(PyExc_KeyError, item);
      return NULL;
    }
    PyObject* pyresult = js2python(result);
    hiwire_decref(result);
    return pyresult;
  }
  if (PySlice_Check(item)) {
    PyErr_SetString(PyExc_NotImplementedError,
                    "Haven't implemented slice subscript yet");
    return NULL;
  }
  PyErr_Format(PyExc_TypeError,
               "list indices must be integers or slices, not %.200s",
               item->ob_type->tp_name);
  return NULL;
}

static int
JsProxy_ass_subscript_array(PyObject* o, PyObject* item, PyObject* pyvalue)
{
  JsProxy* self = (JsProxy*)o;
  Py_ssize_t i;
  if (PySlice_Check(item)) {
    PyErr_SetString(PyExc_NotImplementedError,
                    "Haven't implemented slice assign yet");
    return -1;
  } else if (PyIndex_Check(item)) {
    i = PyNumber_AsSsize_t(item, PyExc_IndexError);
    if (i == -1 && PyErr_Occurred())
      return -1;
    if (i < 0)
      i += hiwire_get_length(self->js);
  } else {
    PyErr_Format(PyExc_TypeError,
                 "list indices must be integers or slices, not %.200s",
                 item->ob_type->tp_name);
    return -1;
  }

  bool success = false;
  JsRef idvalue = NULL;
  if (pyvalue == NULL) {
    if (hiwire_delete_member_int(self->js, i)) {
      PyErr_SetObject(PyExc_KeyError, item);
      FAIL();
    }
  } else {
    idvalue = python2js(pyvalue);
    FAIL_IF_NULL(idvalue);
    FAIL_IF_MINUS_ONE(hiwire_set_member_int(self->js, i, idvalue));
  }
  success = true;
finally:
  hiwire_CLEAR(idvalue);
  return success ? 0 : -1;
}

static PyObject*
JsProxy_subscript(PyObject* o, PyObject* pyidx)
{
  JsProxy* self = (JsProxy*)o;

  JsRef ididx = python2js(pyidx);
  JsRef idresult = hiwire_get_meth(self->js, ididx);
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
  bool success = false;
  JsRef ididx = NULL;
  JsRef idvalue = NULL;
  ididx = python2js(pyidx);
  if (pyvalue == NULL) {
    if (hiwire_delete_meth(self->js, ididx)) {
      PyErr_SetObject(PyExc_KeyError, pyidx);
      FAIL();
    }
  } else {
    idvalue = python2js(pyvalue);
    FAIL_IF_NULL(idvalue);
    FAIL_IF_MINUS_ONE(hiwire_set_meth(self->js, ididx, idvalue));
  }
  success = true;
finally:
  hiwire_CLEAR(ididx);
  hiwire_CLEAR(idvalue);
  return success ? 0 : -1;
}

static int
JsProxy_includes(JsProxy* self, PyObject* obj)
{
  int result = -1;
  JsRef jsobj = python2js(obj);
  FAIL_IF_NULL(jsobj);
  result = hiwire_includes_meth(self->js, jsobj);

finally:
  hiwire_CLEAR(jsobj);
  return result;
}

static int
JsProxy_has(JsProxy* self, PyObject* obj)
{
  int result = -1;
  JsRef jsobj = python2js(obj);
  FAIL_IF_NULL(jsobj);
  result = hiwire_has_meth(self->js, jsobj);

finally:
  hiwire_CLEAR(jsobj);
  return result;
}

#define GET_JSREF(x) (((JsProxy*)x)->js)

static PyObject*
JsProxy_Dir(PyObject* self, PyObject* _args)
{
  bool success = false;
  PyObject* object__dir__ = NULL;
  PyObject* keys = NULL;
  PyObject* result_set = NULL;
  JsRef iddir = NULL;
  PyObject* pydir = NULL;
  PyObject* keys_str = NULL;
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
  if (hiwire_is_array(GET_JSREF(self))) {
    // See comment about Array.keys in GetAttr
    keys_str = PyUnicode_FromString("keys");
    FAIL_IF_NULL(keys_str);
    FAIL_IF_MINUS_ONE(PySet_Discard(result_set, keys_str));
  }
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
  Py_CLEAR(keys_str);
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

static PyObject*
JsProxy_Await(JsProxy* self, PyObject* _args)
{
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
static PyNumberMethods JsProxy_NumberMethods = {
  .nb_bool = JsProxy_Bool
};
// clang-format on

static PyGetSetDef JsProxy_GetSet[] = { { "typeof", .get = JsProxy_typeof },
                                        { NULL } };

static PyTypeObject JsProxyType = {
  .tp_name = "JsProxy",
  .tp_basicsize = sizeof(JsProxy),
  .tp_dealloc = (destructor)JsProxy_dealloc,
  .tp_getattro = JsProxy_GetAttr,
  .tp_setattro = JsProxy_SetAttr,
  .tp_richcompare = JsProxy_RichCompare,
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .tp_doc = "A proxy to make a Javascript object behave like a Python object",
  .tp_getset = JsProxy_GetSet,
  .tp_as_number = &JsProxy_NumberMethods,
  .tp_repr = JsProxy_Repr,
};

static int
JsProxy_cinit(PyObject* obj, JsRef idobj)
{
  JsProxy* self = (JsProxy*)obj;
  self->js = hiwire_incref(idobj);
  return 0;
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

static PyObject*
JsProxy_new_error(JsRef idobj)
{
  PyObject* proxy = NULL;
  PyObject* result = NULL;
  proxy = JsProxyType.tp_alloc(&JsProxyType, 0);
  FAIL_IF_NULL(proxy);
  FAIL_IF_NONZERO(JsProxy_cinit(proxy, idobj));
  result = PyObject_CallFunctionObjArgs(Exc_JsException, proxy, NULL);
  FAIL_IF_NULL(result);
finally:
  return result;
}

////////////////////////////////////////////////////////////
// JsMethod
//
// A subclass of JsProxy for methods

#define JsMethod_THIS(x) (((JsProxy*)x)->this_)
#define JsMethod_SUPPORTS_KWARGS(x) (((JsProxy*)x)->supports_kwargs)

static PyObject*
JsMethod_Vectorcall(PyObject* self,
                    PyObject* const* args,
                    size_t nargsf,
                    PyObject* kwnames)
{
  bool kwargs = false;
  if (kwnames != NULL) {
    // There were kwargs? But maybe kwnames is the empty tuple?
    PyObject* kwname = PyTuple_GetItem(kwnames, 0); /* borrowed!*/
    // Clear IndexError
    PyErr_Clear();
    if (kwname != NULL) {
      kwargs = true;
      if (JsMethod_SUPPORTS_KWARGS(self) == -1) {
        JsMethod_SUPPORTS_KWARGS(self) =
          hiwire_function_supports_kwargs(JsProxy_REF(self));
        if (JsMethod_SUPPORTS_KWARGS(self) == -1) {
          // if it's still -1, hiwire_function_supports_kwargs threw an error.
          return NULL;
        }
      }
    }
    if (kwargs && !JsMethod_SUPPORTS_KWARGS(self)) {
      // We have kwargs but function doesn't support them. Raise error.
      const char* kwname_utf8 = PyUnicode_AsUTF8(kwname);
      PyErr_Format(PyExc_TypeError,
                   "jsproxy got an unexpected keyword argument '%s'",
                   kwname_utf8);
      return NULL;
    }
  }

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" in JsProxy_Vectorcall"));
  bool success = false;
  JsRef idargs = NULL;
  JsRef idkwargs = NULL;
  JsRef idarg = NULL;
  JsRef idresult = NULL;

  Py_ssize_t nargs = PyVectorcall_NARGS(nargsf);
  idargs = hiwire_array();
  FAIL_IF_NULL(idargs);
  for (Py_ssize_t i = 0; i < nargs; ++i) {
    idarg = python2js(args[i]);
    FAIL_IF_NULL(idarg);
    FAIL_IF_MINUS_ONE(hiwire_push_array(idargs, idarg));
    hiwire_CLEAR(idarg);
  }

  if (kwargs) {
    // store kwargs into an object which we'll use as the last argument.
    idkwargs = hiwire_object();
    FAIL_IF_NULL(idkwargs);
    Py_ssize_t nkwargs = PyTuple_Size(kwnames);
    for (Py_ssize_t i = 0, k = nargsf; i < nkwargs; ++i, ++k) {
      PyObject* name = PyTuple_GET_ITEM(kwnames, i); /* borrowed! */
      const char* name_utf8 = PyUnicode_AsUTF8(name);
      idarg = python2js(args[k]);
      FAIL_IF_NULL(idarg);
      FAIL_IF_MINUS_ONE(hiwire_set_member_string(idkwargs, name_utf8, idarg));
      hiwire_CLEAR(idarg);
    }
    FAIL_IF_MINUS_ONE(hiwire_push_array(idargs, idkwargs));
  }

  idresult = hiwire_call_bound(JsProxy_REF(self), JsMethod_THIS(self), idargs);
  FAIL_IF_NULL(idresult);
  PyObject* pyresult = js2python(idresult);
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  Py_LeaveRecursiveCall(/* " in JsProxy_Vectorcall" */);
  hiwire_CLEAR(idargs);
  hiwire_CLEAR(idkwargs);
  hiwire_CLEAR(idarg);
  hiwire_CLEAR(idresult);
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

/* This doesn't construct a new JsMethod object, it treats the JsMethod as a
 * javascript class and this constructs a new javascript object of that class
 * and returns a new JsProxy wrapping it.
 */
static PyObject*
JsMethod_jsnew(PyObject* o, PyObject* args, PyObject* kwargs)
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

static int
JsMethod_cinit(PyObject* obj, JsRef this_)
{
  JsProxy* self = (JsProxy*)obj;
  self->this_ = hiwire_incref(this_);
  self->vectorcall = JsMethod_Vectorcall;
  self->supports_kwargs = -1; // don't know
  return 0;
}

////////////////////////////////////////////////////////////
// JsBuffer
//
// A subclass of JsProxy for Buffers

typedef struct
{
  JsProxy super;
  Py_ssize_t byteLength;
  char* format;
  Py_ssize_t itemsize;
  PyObject* bytes;
} JsBuffer;

static PyObject*
JsBuffer_HasBytes(PyObject* o,
                  PyObject* _args) /* METH_NO_ARGS ==> _args is always NULL */
{
  JsBuffer* self = (JsBuffer*)o;
  if (self->bytes == NULL) {
    Py_RETURN_FALSE;
  } else {
    Py_RETURN_TRUE;
  }
}

static int
JsBuffer_GetBuffer(PyObject* obj, Py_buffer* view, int flags)
{
  bool success = false;
  JsBuffer* self = (JsBuffer*)obj;
  view->obj = NULL;

  void* ptr;
  if (hiwire_is_on_wasm_heap(JsProxy_REF(self))) {
    ptr = (void*)hiwire_get_byteOffset(JsProxy_REF(self));
  } else {
    // Every time JsBuffer_GetBuffer is called, copy the current data from the
    // TypedArray into the buffer. (TODO: don't do this.)
    ptr = PyBytes_AsString(self->bytes);
    FAIL_IF_NULL(ptr);
    hiwire_copy_to_ptr(JsProxy_REF(self), ptr);
  }

  Py_INCREF(self);

  view->buf = ptr;
  view->obj = (PyObject*)self;
  view->len = self->byteLength;
  view->readonly = false;
  view->itemsize = self->itemsize;
  view->format = self->format;
  view->ndim = 1;
  view->shape = NULL;
  view->strides = NULL;
  view->suboffsets = NULL;

  success = true;
finally:
  return success ? 0 : -1;
}

static void
JsBuffer_dealloc(JsBuffer* self)
{
  Py_CLEAR(self->bytes);
  Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyBufferProcs JsBuffer_BufferProcs = {
  .bf_getbuffer = JsBuffer_GetBuffer,
  .bf_releasebuffer = NULL,
};

static PyTypeObject JsBufferType = {
  //.tp_base = &JsProxy, // We have to do this in jsproxy_init.
  .tp_name = "JsBuffer",
  .tp_basicsize = sizeof(JsBuffer),
  .tp_dealloc = (destructor)JsBuffer_dealloc,
  .tp_as_buffer = &JsBuffer_BufferProcs,
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .tp_doc = "A proxy to make it possible to use Javascript TypedArrays as "
            "Python memory buffers",
};

int
JsBuffer_cinit(PyObject* obj)
{
  bool success = false;
  JsBuffer* self = (JsBuffer*)obj;
  self->byteLength = hiwire_get_byteLength(JsProxy_REF(self));
  if (hiwire_is_on_wasm_heap(JsProxy_REF(self))) {
    self->bytes = NULL;
  } else {
    self->bytes = PyBytes_FromStringAndSize(NULL, self->byteLength);
    FAIL_IF_NULL(self->bytes);
  }

  // format string is borrowed from hiwire_get_dtype, DO NOT DEALLOCATE!
  hiwire_get_dtype(JsProxy_REF(self), &self->format, &self->itemsize);
  if (self->format == NULL) {
    char* typename = hiwire_constructor_name(JsProxy_REF(self));
    PyErr_Format(
      PyExc_RuntimeError,
      "Unknown typed array type '%s'. This is a problem with Pyodide, please "
      "open an issue about it here: "
      "https://github.com/iodide-project/pyodide/issues/new",
      typename);
    free(typename);
    FAIL();
  }

  success = true;
finally:
  return success ? 0 : -1;
}

static PyObject*
JsProxy_create_subtype(int flags)
{
  PyType_Slot slots[20];
  int cur_slot = 0;
  PyMethodDef methods[5];
  int cur_method = 0;
  PyMemberDef members[5];
  int cur_member = 0;

  // clang-format off
  methods[cur_method++] = (PyMethodDef){
    "__dir__",
    (PyCFunction)JsProxy_Dir,
    METH_NOARGS,
    "Returns a list of the members and methods on the object." 
  };
  methods[cur_method++] = (PyMethodDef){
    "object_entries",
    (PyCFunction)JsProxy_object_entries,
    METH_NOARGS,
    "This does javascript Object.entries(object)."
  };
  // clang-format on

  PyTypeObject* base = &JsProxyType;
  int tp_flags = Py_TPFLAGS_DEFAULT;

  if (flags & IS_ITERABLE) {
    // This uses `obj[Symbol.iterator]()`
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_iter, .pfunc = (void*)JsProxy_GetIter };
  }
  if (flags & IS_ITERATOR) {
    // JsProxy_GetIter would work just as well as PyObject_SelfIter but 
    // PyObject_SelfIter avoids an unnecessary allocation.
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_iter, .pfunc = (void*)PyObject_SelfIter };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_iternext, .pfunc = (void*)JsProxy_IterNext };
  }
  if (flags & HAS_LENGTH) {
    // If the function has a `size` or `length` member, use this for `len(proxy)`
    // Prefer `size` to `length`.
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_mp_length, .pfunc = (void*)JsProxy_length };
  }
  if (flags & HAS_GET) {
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_mp_subscript,
                                       .pfunc = (void*)JsProxy_subscript };
  }
  if (flags & HAS_SET) {
    // It's assumed that if HAS_SET then also HAS_DELETE.
    // We will try to use `obj.delete("key")` to resolve `del proxy["key"]`
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_mp_ass_subscript,
                                       .pfunc = (void*)JsProxy_ass_subscript };
  }
  // Overloads for the `in` operator: javascript uses `obj.has()` for cheap containment
  // checks (e.g., set, map) and `includes` for less cheap ones (eg array).
  // Prefer the `has` method if present.
  if (flags & HAS_INCLUDES) {
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_contains, .pfunc = (void*)JsProxy_includes };
  }
  if (flags & HAS_HAS) {
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_contains, .pfunc = (void*)JsProxy_has };
  }

  if (flags & IS_AWAITABLE) {
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_am_await, .pfunc = (void*)JsProxy_Await };
  }
  if (flags & IS_CALLABLE) {
    tp_flags |= _Py_TPFLAGS_HAVE_VECTORCALL;
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_call, .pfunc = (void*)PyVectorcall_Call };
    // We could test separately for whether a function is constructable,
    // but it generates a lot of false positives.
    // clang-format off
    methods[cur_method++] = (PyMethodDef){
      "new",
      (PyCFunction)JsMethod_jsnew,
      METH_VARARGS | METH_KEYWORDS,
      "Construct a new instance"
    };
    // clang-format on
  }
  if (flags & IS_BUFFER) {
    // PyBufferProcs cannot be assigned with a `PyType_Slot` in Python v3.8
    // this has been added in v3.9. In the meantime we need to use a static
    // subclass to fill in PyBufferProcs
    base = &JsBufferType;
    methods[cur_method++] = (PyMethodDef){
      "_has_bytes",
      JsBuffer_HasBytes,
      METH_NOARGS,
      "Returns true if instance has buffer memory. For testing only."
    };
  }
  if (flags & IS_ARRAY) {
    // If the object is an array (or a HTMLCollection or NodeList), then we want
    // subscripting `proxy[idx]` to go to `jsobj[idx]` instead of `jsobj.get(idx)`.
    // Hopefully anyone else who defines a custom array object will subclass Array.
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_mp_subscript,
                     .pfunc = (void*)JsProxy_subscript_array };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_mp_ass_subscript,
                     .pfunc = (void*)JsProxy_ass_subscript_array };
  }
  methods[cur_method++] = (PyMethodDef){ 0 };
  members[cur_member++] = (PyMemberDef){ 0 };

  bool success = false;
  PyMethodDef* methods_heap = NULL;
  PyObject* bases = NULL;
  PyObject* result = NULL;

  // PyType_FromSpecWithBases copies "members" automatically into the end of the type
  // It doesn't store the slots. But it just copies the pointer to "methods" into the
  // PyTypeObject, so if we give it a stack allocated methods there will be trouble.
  // (There are several other buggy behaviors in PyType_FromSpecWithBases, like if you 
  // use two PyMembers slots, the first one with more members than the second, it will 
  // corrupt memory).
  // If the type object were later deallocated, we would leak this memory. It's 
  // unclear how to fix that, but we store the type in JsProxy_TypeDict forever 
  // anyway so it will never be deallocated.
  methods_heap = (PyMethodDef*)PyMem_Malloc(sizeof(PyMethodDef) * cur_method);
  if (methods_heap == NULL) {
    PyErr_NoMemory();
    FAIL();
  }
  memcpy(methods_heap, methods, sizeof(PyMethodDef) * cur_method);

  slots[cur_slot++] =
    (PyType_Slot){ .slot = Py_tp_members, .pfunc = (void*)members };
  slots[cur_slot++] =
    (PyType_Slot){ .slot = Py_tp_methods, .pfunc = (void*)methods_heap };
  slots[cur_slot++] = (PyType_Slot){ 0 };

  PyType_Spec spec = {
    .name = "JsProxy", // TODO: this will need to change for Python 3.9
    .itemsize = 0,
    .flags = tp_flags,
    .slots = slots,
  };
  if (flags & IS_BUFFER) {
    spec.basicsize = sizeof(JsBuffer);
  } else {
    spec.basicsize = sizeof(JsProxy);
  }
  bases = Py_BuildValue("(O)", base);
  FAIL_IF_NULL(bases);
  result = PyType_FromSpecWithBases(&spec, bases);
  FAIL_IF_NULL(result);
  if (flags & IS_CALLABLE) {
    // Python 3.9 provides an alternate way to do this by setting a special member
    // __vectorcall_offset__ but it doesn't work in I like this approach better
    ((PyTypeObject*)result)->tp_vectorcall_offset =
      offsetof(JsProxy, vectorcall);
  }

  success = true;
finally:
  Py_CLEAR(bases);
  if (!success && methods_heap != NULL) {
    PyMem_Free(methods_heap);
  }
  return result;
}

static PyObject* JsProxy_TypeDict;

static PyTypeObject*
JsProxy_get_subtype(int flags)
{
  PyObject* flags_key = PyLong_FromLong(flags);
  PyObject* type = PyDict_GetItemWithError(JsProxy_TypeDict, flags_key);
  Py_XINCREF(type);
  if (type != NULL || PyErr_Occurred()) {
    goto finally;
  }
  type = JsProxy_create_subtype(flags);
  FAIL_IF_NULL(type);
  FAIL_IF_MINUS_ONE(PyDict_SetItem(JsProxy_TypeDict, flags_key, type));
finally:
  Py_CLEAR(flags_key);
  return (PyTypeObject*)type;
}

////////////////////////////////////////////////////////////
// Public functions

PyObject*
JsProxy_create_with_this(JsRef object, JsRef this)
{
  if (hiwire_is_error(object)) {
    return JsProxy_new_error(object);
  }
  int type_flags = 0;
  if (hiwire_is_function(object)) {
    type_flags |= IS_CALLABLE;
  }
  if (hiwire_is_promise(object)) {
    type_flags |= IS_AWAITABLE;
  }
  if (hiwire_is_iterable(object)) {
    type_flags |= IS_ITERABLE;
  }
  if (hiwire_is_iterator(object)) {
    type_flags |= IS_ITERATOR;
  }
  if (hiwire_has_length(object)) {
    type_flags |= HAS_LENGTH;
  }
  if (hiwire_has_get_meth(object)) {
    type_flags |= HAS_GET;
  }
  if (hiwire_has_set_meth(object)) {
    type_flags |= HAS_SET;
  }
  if (hiwire_has_has_meth(object)) {
    type_flags |= HAS_HAS;
  }
  if (hiwire_has_includes_meth(object)) {
    type_flags |= HAS_INCLUDES;
  }
  if (hiwire_is_typedarray(object)) {
    type_flags |= IS_BUFFER;
  }
  if (hiwire_is_promise(object)) {
    type_flags |= IS_AWAITABLE;
  }
  if (hiwire_is_array(object)) {
    type_flags |= IS_ARRAY;
  }

  bool success = false;
  PyTypeObject* type = NULL;
  PyObject* result = NULL;

  type = JsProxy_get_subtype(type_flags);
  FAIL_IF_NULL(type);

  result = type->tp_alloc(type, 0);
  FAIL_IF_NONZERO(JsProxy_cinit(result, object));
  if (type_flags & IS_CALLABLE) {
    FAIL_IF_NONZERO(JsMethod_cinit(result, this));
  }
  if (type_flags & IS_BUFFER) {
    FAIL_IF_NONZERO(JsBuffer_cinit(result));
  }

  success = true;
finally:
  Py_CLEAR(type);
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

PyObject*
JsProxy_create(JsRef object)
{
  return JsProxy_create_with_this(object, NULL);
}

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

  JsProxy_TypeDict = PyDict_New();
  FAIL_IF_NULL(JsProxy_TypeDict);

  PyExc_BaseException_Type = (PyTypeObject*)PyExc_BaseException;
  _Exc_JsException.tp_base = (PyTypeObject*)PyExc_Exception;

  JsBufferType.tp_base = &JsProxyType;
  FAIL_IF_MINUS_ONE(PyModule_AddType(core_module, &JsProxyType));
  FAIL_IF_MINUS_ONE(PyModule_AddType(core_module, &JsBufferType));
  // Add JsException to the pyodide module so people can catch it if they want.
  FAIL_IF_MINUS_ONE(PyModule_AddType(core_module, &_Exc_JsException));

  success = true;
finally:
  Py_CLEAR(asyncio_module);
  Py_CLEAR(pyodide_module);
  return success ? 0 : -1;
}
