/**
 * JsProxy Class
 *
 * The root JsProxy class is a simple class that wraps a JsRef.  We define
 * overloads for getattr, setattr, delattr, repr, bool, and comparison opertaors
 * on the base class.
 *
 * We define a wide variety of subclasses on the fly with different operator
 * overloads depending on the functionality detected on the wrapped js object.
 * This is pretty much an identical strategy to the one used in PyProxy.
 *
 * Most of the overloads do not require any extra space which is convenient
 * because multiple inheritance does not work well with different sized C
 * structs. The Callable subclass and the Buffer subclass both need some extra
 * space. Currently we use the maximum paranoia approach: JsProxy always
 * allocates the extra 12 bytes needed for a Callable, and that way if an object
 * ever comes around that is a Buffer and also is Callable, we've got it
 * covered.
 *
 * We create the dynamic types as heap types with PyType_FromSpecWithBases. It's
 * a good idea to consult the source for PyType_FromSpecWithBases in
 * typeobject.c before modifying since the behavior doesn't exactly match the
 * documentation.
 *
 * We don't currently have any way to define a new heap type
 * without leaking the dynamically allocated methods array, but this is fine
 * because we never free the dynamic types we construct. (it'd probably be
 * possible by subclassing PyType with a different tp_dealloc method).
 */

#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "docstring.h"
#include "hiwire.h"
#include "js2python.h"
#include "jsproxy.h"
#include "pyproxy.h"
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
Js_IDENTIFIER(then);
Js_IDENTIFIER(finally);
Js_IDENTIFIER(has);
Js_IDENTIFIER(get);
Js_IDENTIFIER(set);
Js_IDENTIFIER(delete);
Js_IDENTIFIER(includes);

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
// fields for buffers
  Py_ssize_t byteLength;
  char* format;
  Py_ssize_t itemsize;
  bool check_assignments;
// Currently just for module objects
  PyObject* dict;
} JsProxy;
// clang-format on

#define JsProxy_REF(x) (((JsProxy*)x)->js)

static void
JsProxy_dealloc(JsProxy* self)
{
#ifdef HW_TRACE_REFS
  printf("jsproxy delloc %zd, %zd\n", (long)self, (long)self->js);
#endif
  hiwire_CLEAR(self->js);
  hiwire_CLEAR(self->this_);
  Py_TYPE(self)->tp_free((PyObject*)self);
}

/**
 * repr overload, does `obj.toString()` which produces a low-quality repr.
 */
static PyObject*
JsProxy_Repr(PyObject* self)
{
  JsRef idrepr = hiwire_to_string(JsProxy_REF(self));
  PyObject* pyrepr = js2python(idrepr);
  hiwire_decref(idrepr);
  return pyrepr;
}

/**
 * typeof getter, returns `typeof(obj)`.
 */
static PyObject*
JsProxy_typeof(PyObject* self, void* _unused)
{
  JsRef idval = hiwire_typeof(JsProxy_REF(self));
  PyObject* result = js2python(idval);
  hiwire_decref(idval);
  return result;
}

/**
 * getattr overload, first checks whether the attribute exists in the JsProxy
 * dict, and if so returns that. Otherwise, it attempts lookup on the wrapped
 * object.
 */
static PyObject*
JsProxy_GetAttr(PyObject* self, PyObject* attr)
{
  PyObject* result = PyObject_GenericGetAttr(self, attr);
  if (result != NULL || !PyErr_ExceptionMatches(PyExc_AttributeError)) {
    return result;
  }
  PyErr_Clear();

  bool success = false;
  JsRef idresult = 0;
  // result:
  PyObject* pyresult = NULL;

  const char* key = PyUnicode_AsUTF8(attr);
  FAIL_IF_NULL(key);
  if (strcmp(key, "keys") == 0 && JsArray_Check(JsProxy_REF(self))) {
    // Sometimes Python APIs test for the existence of a "keys" function
    // to decide whether something should be treated like a dict.
    // This mixes badly with the javascript Array.keys API, so pretend that it
    // doesn't exist. (Array.keys isn't very useful anyways so hopefully this
    // won't confuse too many people...)
    PyErr_SetString(PyExc_AttributeError, key);
    FAIL();
  }

  idresult = JsObject_GetString(JsProxy_REF(self), key);
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

/**
 * setattr / delttr overload. TODO: Raise an error if the attribute exists on
 * the proxy.
 */
static int
JsProxy_SetAttr(PyObject* self, PyObject* attr, PyObject* pyvalue)
{
  bool success = false;
  JsRef idvalue = NULL;

  const char* key = PyUnicode_AsUTF8(attr);
  FAIL_IF_NULL(key);

  if (strncmp(key, "__", 2) == 0) {
    // Avoid creating reference loops between Python and Javascript with js
    // modules. Such reference loops make it hard to avoid leaking memory.
    if (strcmp(key, "__loader__") == 0 || strcmp(key, "__name__") == 0 ||
        strcmp(key, "__package__") == 0 || strcmp(key, "__path__") == 0 ||
        strcmp(key, "__spec__") == 0) {
      return PyObject_GenericSetAttr(self, attr, pyvalue);
    }
  }

  if (pyvalue == NULL) {
    FAIL_IF_MINUS_ONE(JsObject_DeleteString(JsProxy_REF(self), key));
  } else {
    idvalue = python2js(pyvalue);
    FAIL_IF_MINUS_ONE(JsObject_SetString(JsProxy_REF(self), key, idvalue));
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

/**
 * iter overload. Present if IS_ITERABLE but not IS_ITERATOR (if the IS_ITERATOR
 * flag is present we use PyObject_SelfIter). Does `obj[Symbol.iterator]()`.
 */
static PyObject*
JsProxy_GetIter(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;

  JsRef iditer = hiwire_get_iterator(self->js);
  if (iditer == NULL) {
    return NULL;
  }
  PyObject* result = js2python(iditer);
  hiwire_decref(iditer);
  return result;
}

/**
 * next overload. Controlled by IS_ITERATOR.
 * TODO: Should add a similar send method for generator support.
 * Python 3.10 has a different way to handle this.
 */
static PyObject*
JsProxy_IterNext(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;
  JsRef idresult = NULL;
  PyObject* result = NULL;

  int done = hiwire_next(self->js, &idresult);
  // done:
  //   1 ==> finished
  //   0 ==> not finished
  //  -1 ==> unexpected Js error occurred (logic error in hiwire_next?)
  FAIL_IF_MINUS_ONE(done);
  // If there was no "value", "idresult" will be jsundefined
  // so pyvalue will be set to Py_None.
  result = js2python(idresult);
  FAIL_IF_NULL(result);
  if (done) {
    // For the return value of a generator, raise StopIteration with result.
    PyErr_SetObject(PyExc_StopIteration, result);
    Py_CLEAR(result);
  }

finally:
  hiwire_CLEAR(idresult);
  return result;
}

/**
 * This is exposed as a METH_NOARGS method on the JsProxy. It returns
 * Object.entries(obj) as a new JsProxy.
 */
static PyObject*
JsProxy_object_entries(PyObject* o, PyObject* _args)
{
  JsProxy* self = (JsProxy*)o;
  JsRef result_id = JsObject_Entries(self->js);
  if (result_id == NULL) {
    return NULL;
  }
  PyObject* result = JsProxy_create(result_id);
  hiwire_decref(result_id);
  return result;
}

PyMethodDef JsProxy_object_entries_MethodDef = {
  "object_entries",
  (PyCFunction)JsProxy_object_entries,
  METH_NOARGS,
};

/**
 * This is exposed as a METH_NOARGS method on the JsProxy. It returns
 * Object.keys(obj) as a new JsProxy.
 */
static PyObject*
JsProxy_object_keys(PyObject* o, PyObject* _args)
{
  JsProxy* self = (JsProxy*)o;
  JsRef result_id = JsObject_Keys(self->js);
  if (result_id == NULL) {
    return NULL;
  }
  PyObject* result = JsProxy_create(result_id);
  hiwire_decref(result_id);
  return result;
}

PyMethodDef JsProxy_object_keys_MethodDef = {
  "object_keys",
  (PyCFunction)JsProxy_object_keys,
  METH_NOARGS,
};

/**
 * This is exposed as a METH_NOARGS method on the JsProxy. It returns
 * Object.entries(obj) as a new JsProxy.
 */
static PyObject*
JsProxy_object_values(PyObject* o, PyObject* _args)
{
  JsProxy* self = (JsProxy*)o;
  JsRef result_id = JsObject_Values(self->js);
  if (result_id == NULL) {
    return NULL;
  }
  PyObject* result = JsProxy_create(result_id);
  hiwire_decref(result_id);
  return result;
}

PyMethodDef JsProxy_object_values_MethodDef = {
  "object_values",
  (PyCFunction)JsProxy_object_values,
  METH_NOARGS,
};

/**
 * len(proxy) overload for proxies of Js objects with `length` or `size` fields.
 * Prefers `object.size` over `object.length`. Controlled by HAS_LENGTH.
 */
static Py_ssize_t
JsProxy_length(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;
  int result = hiwire_get_length(self->js);
  if (result == -1) {
    PyErr_SetString(PyExc_TypeError, "object does not have a valid length");
  }
  return result;
}

/**
 * __getitem__ for proxies of Js Arrays, controlled by IS_ARRAY
 */
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
    JsRef result = JsArray_Get(self->js, i);
    if (result == NULL) {
      if (!PyErr_Occurred()) {
        PyErr_SetObject(PyExc_IndexError, item);
      }
      return NULL;
    }
    PyObject* pyresult = js2python(result);
    hiwire_decref(result);
    return pyresult;
  }
  if (PySlice_Check(item)) {
    PyErr_SetString(PyExc_NotImplementedError,
                    "Slice subscripting isn't implemented");
    return NULL;
  }
  PyErr_Format(PyExc_TypeError,
               "list indices must be integers or slices, not %.200s",
               item->ob_type->tp_name);
  return NULL;
}

/**
 * __setitem__ and __delitem__ for proxies of Js Arrays, controlled by IS_ARRAY
 */
static int
JsProxy_ass_subscript_array(PyObject* o, PyObject* item, PyObject* pyvalue)
{
  JsProxy* self = (JsProxy*)o;
  Py_ssize_t i;
  if (PySlice_Check(item)) {
    PyErr_SetString(PyExc_NotImplementedError,
                    "Slice subscripting isn't implemented");
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
    if (JsArray_Delete(self->js, i)) {
      if (!PyErr_Occurred()) {
        PyErr_SetObject(PyExc_IndexError, item);
      }
      FAIL();
    }
  } else {
    idvalue = python2js(pyvalue);
    FAIL_IF_NULL(idvalue);
    FAIL_IF_MINUS_ONE(JsArray_Set(self->js, i, idvalue));
  }
  success = true;
finally:
  hiwire_CLEAR(idvalue);
  return success ? 0 : -1;
}

// A helper method for jsproxy_subscript.
EM_JS_REF(JsRef, JsProxy_subscript_js, (JsRef idobj, JsRef idkey), {
  let obj = Module.hiwire.get_value(idobj);
  let key = Module.hiwire.get_value(idkey);
  let result = obj.get(key);
  // clang-format off
  if (result === undefined) {
    // Try to distinguish between undefined and missing:
    // If the object has a "has" method and it returns false for this key, the
    // key is missing. Otherwise, assume key present and value was undefined.
    // TODO: in absence of a "has" method, should we return None or KeyError?
    if (obj.has && typeof obj.has === "function" && !obj.has(key)) {
      return 0;
    }
  }
  // clang-format on
  return Module.hiwire.new_value(result);
});

/**
 * __getitem__ for JsProxies that have a "get" method. Translates proxy[key] to
 * obj.get(key). Controlled by HAS_GET
 */
static PyObject*
JsProxy_subscript(PyObject* o, PyObject* pyidx)
{
  JsProxy* self = (JsProxy*)o;
  JsRef ididx = NULL;
  JsRef idresult = NULL;
  PyObject* pyresult = NULL;

  ididx = python2js(pyidx);
  FAIL_IF_NULL(ididx);
  idresult = JsProxy_subscript_js(self->js, ididx);
  if (idresult == NULL) {
    if (!PyErr_Occurred()) {
      PyErr_SetObject(PyExc_KeyError, pyidx);
    }
    FAIL();
  }
  pyresult = js2python(idresult);

finally:
  hiwire_CLEAR(ididx);
  hiwire_CLEAR(idresult);
  return pyresult;
}

/**
 * __setitem__ / __delitem__ for JsProxies that have a "set" method (it's
 * currently assumed that they'll also have a del method...). Translates
 * `proxy[key] = value` to `obj.set(key, value)` and `del proxy[key]` to
 * `obj.del(key)`.
 * Controlled by HAS_SET.
 */
static int
JsProxy_ass_subscript(PyObject* o, PyObject* pyidx, PyObject* pyvalue)
{
  JsProxy* self = (JsProxy*)o;
  bool success = false;
  JsRef ididx = NULL;
  JsRef idvalue = NULL;
  JsRef jsresult = NULL;
  ididx = python2js(pyidx);
  if (pyvalue == NULL) {
    jsresult = hiwire_CallMethodId_OneArg(self->js, &JsId_delete, ididx);
    FAIL_IF_NULL(jsresult);
    if (!hiwire_to_bool(jsresult)) {
      if (!PyErr_Occurred()) {
        PyErr_SetObject(PyExc_KeyError, pyidx);
      }
      FAIL();
    }
  } else {
    idvalue = python2js(pyvalue);
    FAIL_IF_NULL(idvalue);
    jsresult =
      hiwire_CallMethodId_va(self->js, &JsId_set, ididx, idvalue, NULL);
    FAIL_IF_NULL(jsresult);
  }
  success = true;
finally:
  hiwire_CLEAR(ididx);
  hiwire_CLEAR(idvalue);
  hiwire_CLEAR(jsresult);
  return success ? 0 : -1;
}

/**
 * Overload of the "in" operator for objects with an "includes" method.
 * Translates `key in proxy` to `obj.includes(key)`. We prefer to use
 * JsProxy_has when the object has both an `includes` and a `has` method.
 * Controlled by HAS_INCLUDES.
 */
static int
JsProxy_includes(JsProxy* self, PyObject* obj)
{
  JsRef jsresult = NULL;
  int result = -1;
  JsRef jsobj = python2js(obj);
  FAIL_IF_NULL(jsobj);
  jsresult = hiwire_CallMethodId_OneArg(self->js, &JsId_includes, jsobj);
  FAIL_IF_NULL(jsresult);
  result = hiwire_to_bool(jsresult);

finally:
  hiwire_CLEAR(jsobj);
  hiwire_CLEAR(jsresult);
  return result;
}

/**
 * Overload of the "in" operator for objects with a "has" method.
 * Translates `key in proxy` to `obj.has(key)`.
 * Controlled by HAS_HAS.
 */
static int
JsProxy_has(JsProxy* self, PyObject* obj)
{
  JsRef jsresult = NULL;
  int result = -1;
  JsRef jsobj = python2js(obj);
  FAIL_IF_NULL(jsobj);
  jsresult = hiwire_CallMethodId_OneArg(self->js, &JsId_has, jsobj);
  FAIL_IF_NULL(jsresult);
  result = hiwire_to_bool(jsresult);

finally:
  hiwire_CLEAR(jsobj);
  hiwire_CLEAR(jsresult);
  return result;
}

#define GET_JSREF(x) (((JsProxy*)x)->js)

/**
 * Overload of `dir(proxy)`. Walks the prototype chain of the object and adds
 * the ownPropertyNames of each prototype.
 */
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
  keys = PyObject_CallOneArg(object__dir__, self);
  FAIL_IF_NULL(keys);
  result_set = PySet_New(keys);
  FAIL_IF_NULL(result_set);

  // Now get attributes of js object
  iddir = JsObject_Dir(GET_JSREF(self));
  pydir = js2python(iddir);
  FAIL_IF_NULL(pydir);
  // Merge and sort
  FAIL_IF_MINUS_ONE(_PySet_Update(result_set, pydir));
  if (JsArray_Check(GET_JSREF(self))) {
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

PyMethodDef JsProxy_Dir_MethodDef = {
  "__dir__",
  (PyCFunction)JsProxy_Dir,
  METH_NOARGS,
  PyDoc_STR("Returns a list of the members and methods on the object."),
};

static PyObject*
JsProxy_toPy(PyObject* self,
             PyObject* const* args,
             Py_ssize_t nargs,
             PyObject* kwnames)
{
  static const char* const _keywords[] = { "depth", 0 };
  static struct _PyArg_Parser _parser = { "|$i:toPy", _keywords, 0 };
  int depth = -1;
  if (kwnames != NULL &&
      !_PyArg_ParseStackAndKeywords(args, nargs, kwnames, &_parser, &depth)) {
    return NULL;
  }
  return js2python_convert(GET_JSREF(self), depth);
}

PyMethodDef JsProxy_toPy_MethodDef = {
  "to_py",
  (PyCFunction)JsProxy_toPy,
  METH_FASTCALL | METH_KEYWORDS,
};

/**
 * Overload for bool(proxy), implemented for every JsProxy. Return `False` if
 * the object is falsey in Javascript, or if it has a `size` field equal to 0,
 * or if it has a `length` field equal to zero and is an array. Otherwise return
 * `True`. This last convention could be replaced with "has a length equal to
 * zero and is not a function". In Javascript, `func.length` returns the number
 * of arguments `func` expects. We definitely don't want 0-argument functions to
 * be falsey.
 */
static int
JsProxy_Bool(PyObject* o)
{
  JsProxy* self = (JsProxy*)o;
  return hiwire_get_bool(self->js) ? 1 : 0;
}

/**
 * Create a Future attached to the given Promise. When the promise is
 * resolved/rejected, the status of the future is set accordingly and
 * done_callback is called.
 */
static PyObject*
wrap_promise(JsRef promise, JsRef done_callback)
{
  bool success = false;
  PyObject* loop = NULL;
  PyObject* set_result = NULL;
  PyObject* set_exception = NULL;
  JsRef promise_id = NULL;
  JsRef promise_handles = NULL;
  JsRef promise_result = NULL;

  PyObject* result = NULL;

  loop = PyObject_CallNoArgs(asyncio_get_event_loop);
  FAIL_IF_NULL(loop);

  result = _PyObject_CallMethodId(loop, &PyId_create_future, NULL);
  FAIL_IF_NULL(result);

  set_result = _PyObject_GetAttrId(result, &PyId_set_result);
  FAIL_IF_NULL(set_result);
  set_exception = _PyObject_GetAttrId(result, &PyId_set_exception);
  FAIL_IF_NULL(set_exception);

  promise_id = hiwire_resolve_promise(promise);
  FAIL_IF_NULL(promise_id);
  promise_handles =
    create_promise_handles(set_result, set_exception, done_callback);
  FAIL_IF_NULL(promise_handles);
  promise_result = hiwire_CallMethodId(promise_id, &JsId_then, promise_handles);
  FAIL_IF_NULL(promise_result);

  success = true;
finally:
  Py_CLEAR(loop);
  Py_CLEAR(set_result);
  Py_CLEAR(set_exception);
  hiwire_CLEAR(promise_id);
  hiwire_CLEAR(promise_handles);
  hiwire_CLEAR(promise_result);
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

/**
 * Overload for `await proxy` for js objects that have a `then` method.
 * Controlled by IS_AWAITABLE.
 */
static PyObject*
JsProxy_Await(JsProxy* self)
{
  if (!hiwire_is_promise(self->js)) {
    // This error is unlikely to be hit except in cases of intentional mischief.
    // Such mischief is conducted in test_jsproxy:test_mixins_errors_2
    PyObject* str = JsProxy_Repr((PyObject*)self);
    const char* str_utf8 = PyUnicode_AsUTF8(str);
    PyErr_Format(PyExc_TypeError,
                 "object %s can't be used in 'await' expression",
                 str_utf8);
    return NULL;
  }
  PyObject* fut = NULL;
  PyObject* result = NULL;

  fut = wrap_promise(self->js, NULL);
  FAIL_IF_NULL(fut);
  result = _PyObject_CallMethodId(fut, &PyId___await__, NULL);

finally:
  Py_CLEAR(fut);
  return result;
}

/**
 * Overload for `then` for JsProxies with a `then` method. Of course without
 * this overload, the call would just fall through to the normal `then`
 * function. The advantage of this overload is that it automatically releases
 * the references to the onfulfilled and onrejected callbacks, which is quite
 * hard to do otherwise.
 */
PyObject*
JsProxy_then(JsProxy* self, PyObject* args, PyObject* kwds)
{
  PyObject* onfulfilled = NULL;
  PyObject* onrejected = NULL;

  static char* kwlist[] = { "onfulfilled", "onrejected", 0 };
  if (!PyArg_ParseTupleAndKeywords(
        args, kwds, "|OO:then", kwlist, &onfulfilled, &onrejected)) {
    return NULL;
  }

  JsRef promise_id = NULL;
  JsRef promise_handles = NULL;
  JsRef result_promise = NULL;
  PyObject* result = NULL;

  if (onfulfilled == Py_None) {
    Py_CLEAR(onfulfilled);
  }
  if (onrejected == Py_None) {
    Py_CLEAR(onrejected);
  }
  promise_id = hiwire_resolve_promise(self->js);
  FAIL_IF_NULL(promise_id);
  promise_handles = create_promise_handles(onfulfilled, onrejected, NULL);
  FAIL_IF_NULL(promise_handles);
  result_promise = hiwire_CallMethodId(promise_id, &JsId_then, promise_handles);
  if (result_promise == NULL) {
    Py_CLEAR(onfulfilled);
    Py_CLEAR(onrejected);
    FAIL();
  }
  result = JsProxy_create(result_promise);

finally:
  // don't clear onfulfilled, onrejected, they are borrowed from arguments.
  hiwire_CLEAR(promise_id);
  hiwire_CLEAR(promise_handles);
  hiwire_CLEAR(result_promise);
  return result;
}

PyMethodDef JsProxy_then_MethodDef = {
  "then",
  (PyCFunction)JsProxy_then,
  METH_VARARGS | METH_KEYWORDS,
};

/**
 * Overload for `catch` for JsProxies with a `then` method.
 */
PyObject*
JsProxy_catch(JsProxy* self, PyObject* onrejected)
{
  JsRef promise_id = NULL;
  JsRef promise_handles = NULL;
  JsRef result_promise = NULL;
  PyObject* result = NULL;

  promise_id = hiwire_resolve_promise(self->js);
  FAIL_IF_NULL(promise_id);
  // We have to use create_promise_handles so that the handler gets released
  // even if the promise resolves successfully.
  promise_handles = create_promise_handles(NULL, onrejected, NULL);
  FAIL_IF_NULL(promise_handles);
  result_promise = hiwire_CallMethodId(promise_id, &JsId_then, promise_handles);
  if (result_promise == NULL) {
    Py_DECREF(onrejected);
    FAIL();
  }
  result = JsProxy_create(result_promise);

finally:
  hiwire_CLEAR(promise_id);
  hiwire_CLEAR(promise_handles);
  hiwire_CLEAR(result_promise);
  return result;
}

PyMethodDef JsProxy_catch_MethodDef = {
  "catch",
  (PyCFunction)JsProxy_catch,
  METH_O,
};

/**
 * Overload for `finally` for JsProxies with a `then` method. This isn't
 * strictly necessary since one could get the same effect by just calling
 * create_once_callable on the argument, but it'd be bad to have `then` and
 * `catch` handle freeing the handler automatically but require something extra
 * to use `finally`.
 */
PyObject*
JsProxy_finally(JsProxy* self, PyObject* onfinally)
{
  JsRef proxy = NULL;
  JsRef promise_id = NULL;
  JsRef result_promise = NULL;
  PyObject* result = NULL;

  promise_id = hiwire_resolve_promise(self->js);
  FAIL_IF_NULL(promise_id);
  // Finally method is called no matter what so we can use
  // `create_once_callable`.
  proxy = create_once_callable(onfinally);
  FAIL_IF_NULL(proxy);
  result_promise =
    hiwire_CallMethodId_va(promise_id, &JsId_finally, proxy, NULL);
  if (result_promise == NULL) {
    Py_DECREF(onfinally);
    FAIL();
  }
  result = JsProxy_create(result_promise);

finally:
  hiwire_CLEAR(promise_id);
  hiwire_CLEAR(proxy);
  hiwire_CLEAR(result_promise);
  return result;
}

PyMethodDef JsProxy_finally_MethodDef = {
  "finally_",
  (PyCFunction)JsProxy_finally,
  METH_O,
};

// clang-format off
static PyNumberMethods JsProxy_NumberMethods = {
  .nb_bool = JsProxy_Bool
};
// clang-format on

static PyGetSetDef JsProxy_GetSet[] = { { "typeof", .get = JsProxy_typeof },
                                        { NULL } };

static PyTypeObject JsProxyType = {
  .tp_name = "pyodide.JsProxy",
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
  .tp_dictoffset = offsetof(JsProxy, dict),
};

static int
JsProxy_cinit(PyObject* obj, JsRef idobj)
{
  JsProxy* self = (JsProxy*)obj;
  self->js = hiwire_incref(idobj);
#ifdef HW_TRACE_REFS
  printf("JsProxy cinit: %zd, object: %zd\n", (long)obj, (long)self->js);
#endif
  return 0;
}

/**
 * A wrapper for JsProxy that inherits from Exception. TODO: consider just
 * making JsProxy of an exception inherit from Exception?
 */
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

// Not sure we are interfacing with the GC correctly. There should be a call to
// PyObject_GC_Track somewhere?
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
  result = PyObject_CallOneArg(Exc_JsException, proxy);
  FAIL_IF_NULL(result);
finally:
  Py_CLEAR(proxy);
  return result;
}

////////////////////////////////////////////////////////////
// JsMethod
//
// A subclass of JsProxy for methods

#define JsMethod_THIS(x) (((JsProxy*)x)->this_)

/**
 * Prepare arguments from a `METH_FASTCALL | METH_KEYWORDS` Python function to a
 * Javascript call. We call `python2js` on each argument. Any PyProxy *created*
 * by `python2js` is stored into the `proxies` list to be destroyed later (if
 * the argument is a PyProxy created with `create_proxy` it won't be recorded
 * for destruction).
 */
JsRef
JsMethod_ConvertArgs(PyObject* const* args,
                     Py_ssize_t nargs,
                     PyObject* kwnames,
                     JsRef proxies)
{
  bool success = false;
  JsRef idargs = NULL;
  JsRef idarg = NULL;
  JsRef idkwargs = NULL;

  idargs = JsArray_New();
  FAIL_IF_NULL(idargs);
  for (Py_ssize_t i = 0; i < nargs; ++i) {
    idarg = python2js_track_proxies(args[i], proxies);
    FAIL_IF_NULL(idarg);
    FAIL_IF_MINUS_ONE(JsArray_Push(idargs, idarg));
    hiwire_CLEAR(idarg);
  }

  bool has_kwargs = false;
  if (kwnames != NULL) {
    // There were kwargs? But maybe kwnames is the empty tuple?
    PyObject* kwname = PyTuple_GetItem(kwnames, 0); /* borrowed!*/
    // Clear IndexError
    PyErr_Clear();
    if (kwname != NULL) {
      has_kwargs = true;
    }
  }
  if (!has_kwargs) {
    goto success;
  }

  // store kwargs into an object which we'll use as the last argument.
  idkwargs = JsObject_New();
  FAIL_IF_NULL(idkwargs);
  Py_ssize_t nkwargs = PyTuple_Size(kwnames);
  for (Py_ssize_t i = 0, k = nargs; i < nkwargs; ++i, ++k) {
    PyObject* name = PyTuple_GET_ITEM(kwnames, i); /* borrowed! */
    const char* name_utf8 = PyUnicode_AsUTF8(name);
    idarg = python2js_track_proxies(args[k], proxies);
    FAIL_IF_NULL(idarg);
    FAIL_IF_MINUS_ONE(JsObject_SetString(idkwargs, name_utf8, idarg));
    hiwire_CLEAR(idarg);
  }
  FAIL_IF_MINUS_ONE(JsArray_Push(idargs, idkwargs));

success:
  success = true;
finally:
  hiwire_CLEAR(idarg);
  hiwire_CLEAR(idkwargs);
  if (!success) {
    hiwire_CLEAR(idargs);
  }
  return idargs;
}

/**
 * This is a helper function for calling asynchronous js functions. proxies_id
 * is an Array of proxies to destroy, it returns a JsRef to a function that
 * destroys them and the result of the Promise.
 */
EM_JS_REF(JsRef, get_async_js_call_done_callback, (JsRef proxies_id), {
  let proxies = Module.hiwire.get_value(proxies_id);
  return Module.hiwire.new_value(function(result) {
    let msg = "This borrowed proxy was automatically destroyed " +
              "at the end of an asynchronous function call. Try " +
              "using create_proxy or create_once_callable.";
    for (let px of proxies) {
      Module.pyproxy_destroy(px, msg);
    }
    if (Module.isPyProxy(result)) {
      Module.pyproxy_destroy(result, msg);
    }
  });
});

/**
 * __call__ overload for methods. Controlled by IS_CALLABLE.
 */
static PyObject*
JsMethod_Vectorcall(PyObject* self,
                    PyObject* const* args,
                    size_t nargsf,
                    PyObject* kwnames)
{
  bool success = false;
  JsRef proxies = NULL;
  JsRef idargs = NULL;
  JsRef idresult = NULL;
  bool result_is_promise = false;
  JsRef async_done_callback = NULL;
  PyObject* pyresult = NULL;

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" in JsMethod_Vectorcall"));
  proxies = JsArray_New();
  idargs =
    JsMethod_ConvertArgs(args, PyVectorcall_NARGS(nargsf), kwnames, proxies);
  FAIL_IF_NULL(idargs);
  idresult = hiwire_call_bound(JsProxy_REF(self), JsMethod_THIS(self), idargs);
  FAIL_IF_NULL(idresult);
  result_is_promise = hiwire_is_promise(idresult);
  if (!result_is_promise) {
    pyresult = js2python(idresult);
  } else {
    // Result was a promise. In this case we don't want to destroy the arguments
    // until the promise is ready. Furthermore, since we destroy the result of
    // the Promise, we deny the user access to the Promise (would cause
    // exceptions). Instead we return a Future. When the promise is ready, we
    // resolve the Future with the result from the Promise and destroy the
    // arguments and result.
    async_done_callback = get_async_js_call_done_callback(proxies);
    FAIL_IF_NULL(async_done_callback);
    pyresult = wrap_promise(idresult, async_done_callback);
  }
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  Py_LeaveRecursiveCall(/* " in JsMethod_Vectorcall" */);
  if (!(success && result_is_promise)) {
    // If we succeeded and the result was a promise then we destroy the
    // arguments in async_done_callback instead of here. Otherwise, destroy the
    // arguments and return value now.
    if (idresult != NULL && hiwire_is_pyproxy(idresult)) {
      JsArray_Push(proxies, idresult);
    }
    destroy_proxies(proxies,
                    "This borrowed proxy was automatically destroyed at the "
                    "end of a function call. Try using "
                    "create_proxy or create_once_callable.");
  }
  hiwire_CLEAR(proxies);
  hiwire_CLEAR(idargs);
  hiwire_CLEAR(idresult);
  hiwire_CLEAR(async_done_callback);
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

/**
 * jsproxy.new implementation. Controlled by IS_CALLABLE.
 *
 * This does Reflect.construct(this, args). In other words, this treats the
 * JsMethod as a Javascript class, constructs a new Javascript object of that
 * class and returns a new JsProxy wrapping it. Similar to `new this(args)`.
 */
static PyObject*
JsMethod_Construct(PyObject* self,
                   PyObject* const* args,
                   Py_ssize_t nargs,
                   PyObject* kwnames)
{
  bool success = false;
  JsRef proxies = NULL;
  JsRef idargs = NULL;
  JsRef idresult = NULL;
  PyObject* pyresult = NULL;

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" in JsMethod_Construct"));

  proxies = JsArray_New();
  idargs = JsMethod_ConvertArgs(args, nargs, kwnames, proxies);
  FAIL_IF_NULL(idargs);
  idresult = hiwire_construct(JsProxy_REF(self), idargs);
  FAIL_IF_NULL(idresult);
  pyresult = js2python(idresult);
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  Py_LeaveRecursiveCall(/* " in JsMethod_Construct" */);
  destroy_proxies(proxies,
                  "This borrowed proxy was automatically destroyed. Try using "
                  "create_proxy or create_once_callable.");
  hiwire_CLEAR(proxies);
  hiwire_CLEAR(idargs);
  hiwire_CLEAR(idresult);
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

// clang-format off
PyMethodDef JsMethod_Construct_MethodDef = {
  "new",
  (PyCFunction)JsMethod_Construct,
  METH_FASTCALL | METH_KEYWORDS
};
// clang-format on

static int
JsMethod_cinit(PyObject* obj, JsRef this_)
{
  JsProxy* self = (JsProxy*)obj;
  self->this_ = hiwire_incref(this_);
  self->vectorcall = JsMethod_Vectorcall;
  return 0;
}

////////////////////////////////////////////////////////////
// JsBuffer
//
// A subclass of JsProxy for Buffers

// We make our own Buffer struct because as far as I can tell BytesArray and
// array are both unsuitable. (To use "array" we need to perform extra copies,
// using BytesArray we run into trouble finding a location to store the Shape.)
// clang-format off
typedef struct
{
  PyObject_HEAD
  void* data;
  Py_ssize_t byteLength; // invariant: byteLength should be equal to length * itemsize
  Py_ssize_t length;
  char* format;
  Py_ssize_t itemsize;
} Buffer;
// clang-format on

static int
Buffer_cinit(Buffer* self,
             Py_ssize_t byteLength,
             char* format,
             Py_ssize_t itemsize)
{
  self->data = PyMem_Malloc(byteLength);
  self->byteLength = byteLength;
  self->format = format; // Format has static lifetime
  self->itemsize = itemsize;
  self->length = byteLength / itemsize;
  return 0;
}

void
Buffer_dealloc(PyObject* self)
{
  PyMem_Free(((Buffer*)self)->data);
  ((Buffer*)self)->data = NULL;
}

static int
Buffer_GetBuffer(PyObject* obj, Py_buffer* view, int flags)
{
  bool success = false;
  Buffer* self = (Buffer*)obj;
  view->obj = NULL;
  // This gets decremented automatically by PyBuffer_Release (even though
  // bf_releasebuffer is NULL)
  Py_INCREF(self);

  view->buf = self->data;
  view->obj = (PyObject*)self;
  view->len = self->byteLength;
  view->readonly = false;
  view->itemsize = self->itemsize;
  view->format = self->format;
  view->ndim = 1;
  // It's important to include the shape:
  // "If shape is NULL as a result of a PyBUF_SIMPLE or a PyBUF_WRITABLE
  // request, the consumer must disregard itemsize and assume itemsize == 1."
  view->shape = &self->length;
  view->strides = NULL;
  view->suboffsets = NULL;

  success = true;
finally:
  return success ? 0 : -1;
}

static PyBufferProcs Buffer_BufferProcs = {
  .bf_getbuffer = Buffer_GetBuffer,
  .bf_releasebuffer = NULL,
};

static PyTypeObject BufferType = {
  .tp_name = "Buffer",
  .tp_basicsize = sizeof(Buffer),
  .tp_dealloc = Buffer_dealloc,
  .tp_as_buffer = &Buffer_BufferProcs,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = PyDoc_STR("An internal helper buffer"),
};

/**
 * This is a helper function to do error checking for JsBuffer_AssignToPyBuffer
 * and JsBuffer_AssignPyBuffer.
 *
 * self -- The Javascript buffer involved
 * view -- The Py_buffer view involved
 * safe -- If true, check data type compatibility, if false only check size
 *         compatibility.
 * dir -- Used for error messages, if true we are assigning from js buffer to
 *        the py buffer, if false we are assigning from the py buffer to the js
 *        buffer
 */
static int
check_buffer_compatibility(JsProxy* self, Py_buffer view, bool safe, bool dir)
{
  if (view.len != self->byteLength) {
    if (dir) {
      PyErr_Format(
        PyExc_ValueError,
        "cannot assign from TypedArray of length %d to buffer of length %d",
        self->byteLength,
        view.len);
    } else {
      PyErr_Format(
        PyExc_ValueError,
        "cannot assign to TypedArray of length %d from buffer of length %d",
        view.len,
        self->byteLength);
    }
    return -1;
  }
  if (safe) {
    bool compatible;
    if (view.format && self->format) {
      compatible = strcmp(view.format, self->format) != 0;
    } else {
      compatible = view.itemsize == self->itemsize;
    }
    if (!compatible) {
      PyErr_Format(PyExc_ValueError,
                   "TypedArray and memorybuffer have incompatible formats");
      return -1;
    }
  }
  return 0;
}

/**
 * Assign from a js buffer to a py buffer
 * obj -- A JsBuffer (meaning a PyProxy of an ArrayBuffer or an ArrayBufferView)
 * buffer -- A PyObject whcih supports the buffer protocol and is writable.
 */
static PyObject*
JsBuffer_AssignToPyBuffer(PyObject* obj, PyObject* target)
{
  JsProxy* self = (JsProxy*)obj;
  bool success = false;
  Py_buffer view = { 0 };

  FAIL_IF_MINUS_ONE(
    PyObject_GetBuffer(target, &view, PyBUF_ANY_CONTIGUOUS | PyBUF_WRITABLE));
  bool safe = self->check_assignments;
  bool dir = true;
  FAIL_IF_MINUS_ONE(check_buffer_compatibility(self, view, safe, dir));
  FAIL_IF_MINUS_ONE(hiwire_assign_to_ptr(JsProxy_REF(self), view.buf));

  success = true;
finally:
  PyBuffer_Release(&view);
  if (success) {
    Py_RETURN_NONE;
  }
  return NULL;
}

/**
 * Assign from a py buffer to a js buffer
 * obj -- A JsBuffer (meaning a PyProxy of an ArrayBuffer or an ArrayBufferView)
 * buffer -- A PyObject which supports the buffer protocol (can be read only)
 */
static PyObject*
JsBuffer_AssignPyBuffer(PyObject* obj, PyObject* source)
{
  JsProxy* self = (JsProxy*)obj;
  bool success = false;
  Py_buffer view = { 0 };

  FAIL_IF_MINUS_ONE(PyObject_GetBuffer(source, &view, PyBUF_ANY_CONTIGUOUS));
  bool safe = self->check_assignments;
  bool dir = false;
  FAIL_IF_MINUS_ONE(check_buffer_compatibility(self, view, safe, dir));
  FAIL_IF_MINUS_ONE(hiwire_assign_from_ptr(JsProxy_REF(self), view.buf));

  success = true;
finally:
  PyBuffer_Release(&view);
  if (success) {
    Py_RETURN_NONE;
  }
  return NULL;
}

/**
 * Used from js2python for to_py. Make a new Python buffer with the same data as
 * jsbuffer.
 *
 * All other arguments are calculated from jsbuffer, but it's more convenient to
 * calculate them in Javascript and pass them as arguments than to acquire them
 * from C.
 *
 * jsbuffer - An ArrayBuffer view or an ArrayBuffer
 * byteLength - the byteLength of jsbuffer
 * format - the appropriate format for jsbuffer, from get_buffer_datatype
 * itemsize - the appropriate itemsize for jsbuffer, from get_buffer_datatype
 */
PyObject*
JsBuffer_CloneIntoPython(JsRef jsbuffer,
                         Py_ssize_t byteLength,
                         char* format,
                         Py_ssize_t itemsize)
{
  bool success = false;
  Buffer* buffer = NULL;
  PyObject* result = NULL;

  buffer = (Buffer*)BufferType.tp_alloc(&BufferType, byteLength);
  FAIL_IF_NULL(buffer);
  FAIL_IF_MINUS_ONE(Buffer_cinit(buffer, byteLength, format, itemsize));
  FAIL_IF_MINUS_ONE(hiwire_assign_to_ptr(jsbuffer, buffer->data));
  result = PyMemoryView_FromObject((PyObject*)buffer);
  FAIL_IF_NULL(result);

  success = true;
finally:
  Py_CLEAR(buffer);
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

int
JsBuffer_cinit(PyObject* obj)
{
  bool success = false;
  JsProxy* self = (JsProxy*)obj;
  // TODO: should logic here be any different if we're on wasm heap?
  self->byteLength = hiwire_get_byteLength(JsProxy_REF(self));
  // format string is borrowed from hiwire_get_buffer_datatype, DO NOT
  // DEALLOCATE!
  hiwire_get_buffer_datatype(JsProxy_REF(self),
                             &self->format,
                             &self->itemsize,
                             &self->check_assignments);
  if (self->format == NULL) {
    char* typename = hiwire_constructor_name(JsProxy_REF(self));
    PyErr_Format(
      PyExc_RuntimeError,
      "Unknown typed array type '%s'. This is a problem with Pyodide, please "
      "open an issue about it here: "
      "https://github.com/pyodide/pyodide/issues/new",
      typename);
    free(typename);
    FAIL();
  }

  success = true;
finally:
  return success ? 0 : -1;
}

/**
 * This dynamically creates a subtype of JsProxy using PyType_FromSpecWithBases.
 * It is called from JsProxy_get_subtype(flags) when a type with the given flags
 * doesn't already exist.
 *
 * None of these types have tp_new method, we create them with tp_alloc and then
 * call whatever init methods are needed. "new" and multiple inheritance don't
 * go together very well.
 */
static PyObject*
JsProxy_create_subtype(int flags)
{
  // Make sure these stack allocations are large enough to fit!
  PyType_Slot slots[20];
  int cur_slot = 0;
  PyMethodDef methods[10];
  int cur_method = 0;
  PyMemberDef members[5];
  int cur_member = 0;

  methods[cur_method++] = JsProxy_Dir_MethodDef;
  methods[cur_method++] = JsProxy_toPy_MethodDef;
  methods[cur_method++] = JsProxy_object_entries_MethodDef;
  methods[cur_method++] = JsProxy_object_keys_MethodDef;
  methods[cur_method++] = JsProxy_object_values_MethodDef;

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
    // If the function has a `size` or `length` member, use this for
    // `len(proxy)` Prefer `size` to `length`.
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
  // Overloads for the `in` operator: javascript uses `obj.has()` for cheap
  // containment checks (e.g., set, map) and `includes` for less cheap ones (eg
  // array). Prefer the `has` method if present.
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
    methods[cur_method++] = JsProxy_then_MethodDef;
    methods[cur_method++] = JsProxy_catch_MethodDef;
    methods[cur_method++] = JsProxy_finally_MethodDef;
  }
  if (flags & IS_CALLABLE) {
    tp_flags |= _Py_TPFLAGS_HAVE_VECTORCALL;
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_call, .pfunc = (void*)PyVectorcall_Call };
    // We could test separately for whether a function is constructable,
    // but it generates a lot of false positives.
    methods[cur_method++] = JsMethod_Construct_MethodDef;
  }
  if (flags & IS_ARRAY) {
    // If the object is an array (or a HTMLCollection or NodeList), then we want
    // subscripting `proxy[idx]` to go to `jsobj[idx]` instead of
    // `jsobj.get(idx)`. Hopefully anyone else who defines a custom array object
    // will subclass Array.
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_mp_subscript,
                     .pfunc = (void*)JsProxy_subscript_array };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_mp_ass_subscript,
                     .pfunc = (void*)JsProxy_ass_subscript_array };
  }
  if (flags & IS_BUFFER) {
    methods[cur_method++] = (PyMethodDef){
      "assign",
      (PyCFunction)JsBuffer_AssignPyBuffer,
      METH_O,
      PyDoc_STR("Copies a buffer into the TypedArray "),
    };
    methods[cur_method++] = (PyMethodDef){
      "assign_to",
      (PyCFunction)JsBuffer_AssignToPyBuffer,
      METH_O,
      PyDoc_STR("Copies the TypedArray into a buffer"),
    };
  }
  methods[cur_method++] = (PyMethodDef){ 0 };
  members[cur_member++] = (PyMemberDef){ 0 };

  bool success = false;
  PyMethodDef* methods_heap = NULL;
  PyObject* bases = NULL;
  PyObject* result = NULL;

  // PyType_FromSpecWithBases copies "members" automatically into the end of the
  // type. It doesn't store the slots. But it just copies the pointer to
  // "methods" into the PyTypeObject, so if we give it a stack allocated methods
  // there will be trouble. (There are several other buggy behaviors in
  // PyType_FromSpecWithBases, like if you use two PyMembers slots, the first
  // one with more members than the second, it will corrupt memory). If the type
  // object were later deallocated, we would leak this memory. It's unclear how
  // to fix that, but we store the type in JsProxy_TypeDict forever anyway so it
  // will never be deallocated.
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

  // clang-format off
  PyType_Spec spec = {
    .name = "pyodide.JsProxy",
    .basicsize = sizeof(JsProxy),
    .itemsize = 0,
    .flags = tp_flags,
    .slots = slots,
  };
  // clang-format on
  bases = Py_BuildValue("(O)", base);
  FAIL_IF_NULL(bases);
  result = PyType_FromSpecWithBases(&spec, bases);
  FAIL_IF_NULL(result);
  if (flags & IS_CALLABLE) {
    // Python 3.9 provides an alternate way to do this by setting a special
    // member __vectorcall_offset__ but it doesn't work in 3.8. I like this
    // approach better.
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

/**
 * Look up the appropriate type object in the types dict, if we don't find it
 * call JsProxy_create_subtype. This is a helper for JsProxy_create_with_this
 * and JsProxy_create.
 */
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

/**
 * Create a JsProxy. In case it's a method, bind "this" to the argument. (In
 * most cases "this" will be NULL, `JsProxy_create` specializes to this case.)
 * We check what capabilities are present on the javascript object, set
 * appropriate flags, then we get the appropriate type with JsProxy_get_subtype.
 */
PyObject*
JsProxy_create_with_this(JsRef object, JsRef this)
{
  int type_flags = 0;
  bool success = false;
  PyTypeObject* type = NULL;
  PyObject* result = NULL;
  if (hiwire_is_comlink_proxy(object)) {
    // Comlink proxies are weird and break our feature detection pretty badly.
    type_flags = IS_CALLABLE | IS_AWAITABLE | IS_ARRAY;
    goto done_feature_detecting;
  }
  if (hiwire_is_error(object)) {
    return JsProxy_new_error(object);
  }
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
  if (hiwire_HasMethodId(object, &JsId_get)) {
    type_flags |= HAS_GET;
  }
  if (hiwire_HasMethodId(object, &JsId_set)) {
    type_flags |= HAS_SET;
  }
  if (hiwire_HasMethodId(object, &JsId_has)) {
    type_flags |= HAS_HAS;
  }
  if (hiwire_HasMethodId(object, &JsId_includes)) {
    type_flags |= HAS_INCLUDES;
  }
  if (hiwire_is_typedarray(object)) {
    type_flags |= IS_BUFFER;
  }
  if (hiwire_is_promise(object)) {
    type_flags |= IS_AWAITABLE;
  }
  if (JsArray_Check(object)) {
    type_flags |= IS_ARRAY;
  }
done_feature_detecting:

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

int
JsProxy_init(PyObject* core_module)
{
  bool success = false;

  PyObject* _pyodide_core_docs = NULL;
  PyObject* jsproxy_mock = NULL;
  PyObject* asyncio_module = NULL;

  _pyodide_core_docs = PyImport_ImportModule("_pyodide._core_docs");
  FAIL_IF_NULL(_pyodide_core_docs);
  _Py_IDENTIFIER(JsProxy);
  jsproxy_mock =
    _PyObject_CallMethodIdNoArgs(_pyodide_core_docs, &PyId_JsProxy);
  FAIL_IF_NULL(jsproxy_mock);

  // Load the docstrings for JsProxy methods from the corresponding stubs in
  // _pyodide._core_docs.set_method_docstring uses
  // _pyodide.docstring.get_cmeth_docstring to generate the appropriate C-style
  // docstring from the Python-style docstring.
#define SET_DOCSTRING(x)                                                       \
  FAIL_IF_MINUS_ONE(set_method_docstring(&x, jsproxy_mock))
  SET_DOCSTRING(JsProxy_object_entries_MethodDef);
  SET_DOCSTRING(JsProxy_object_keys_MethodDef);
  SET_DOCSTRING(JsProxy_object_values_MethodDef);
  // SET_DOCSTRING(JsProxy_Dir_MethodDef);
  SET_DOCSTRING(JsProxy_toPy_MethodDef);
  SET_DOCSTRING(JsProxy_then_MethodDef);
  SET_DOCSTRING(JsProxy_catch_MethodDef);
  SET_DOCSTRING(JsProxy_finally_MethodDef);
  SET_DOCSTRING(JsMethod_Construct_MethodDef);
#undef SET_DOCSTRING

  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);

  asyncio_get_event_loop =
    _PyObject_GetAttrId(asyncio_module, &PyId_get_event_loop);
  FAIL_IF_NULL(asyncio_get_event_loop);

  JsProxy_TypeDict = PyDict_New();
  FAIL_IF_NULL(JsProxy_TypeDict);

  PyExc_BaseException_Type = (PyTypeObject*)PyExc_BaseException;
  _Exc_JsException.tp_base = (PyTypeObject*)PyExc_Exception;

  FAIL_IF_MINUS_ONE(PyType_Ready(&BufferType));
  FAIL_IF_MINUS_ONE(PyModule_AddType(core_module, &JsProxyType));
  FAIL_IF_MINUS_ONE(PyModule_AddType(core_module, &_Exc_JsException));

  success = true;
finally:
  Py_CLEAR(_pyodide_core_docs);
  Py_CLEAR(jsproxy_mock);
  Py_CLEAR(asyncio_module);
  return success ? 0 : -1;
}
