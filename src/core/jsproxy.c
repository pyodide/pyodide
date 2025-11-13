/**
 * JsProxy Class
 *
 * The root JsProxy class is a simple class that wraps a JsRef.  We define
 * overloads for getattr, setattr, delattr, repr, bool, and comparison operators
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
#include "python_unexposed.h"

#include "docstring.h"
#include "error_handling.h"
#include "js2python.h"
#include "jsbind.h"
#include "jslib.h"
#include "jsmemops.h"
#include "jsproxy.h"
#include "jsproxy_call.h"
#include "pyproxy.h"
#include "python2js.h"

#include "structmember.h"

// clang-format off
#define IS_ITERABLE        (1 << 0)
#define IS_ITERATOR        (1 << 1)
#define HAS_LENGTH         (1 << 2)
#define HAS_GET            (1 << 3)
#define HAS_SET            (1 << 4)
#define HAS_HAS            (1 << 5)
#define HAS_INCLUDES       (1 << 6)
#define IS_AWAITABLE       (1 << 7)
#define IS_BUFFER          (1 << 8)
#define IS_CALLABLE        (1 << 9)
#define IS_ARRAY           (1 << 10)
#define IS_ARRAY_LIKE      (1 << 11)
#define IS_TYPEDARRAY      (1 << 12)
#define IS_DOUBLE_PROXY    (1 << 13)
#define IS_OBJECT_MAP      (1 << 14)
#define IS_ASYNC_ITERABLE  (1 << 15)
#define IS_GENERATOR       (1 << 16)
#define IS_ASYNC_GENERATOR (1 << 17)
#define IS_ASYNC_ITERATOR  (1 << 18)
#define IS_ERROR           (1 << 19)
#define IS_PY_JSON_DICT    (1 << 20)
#define IS_PY_JSON_SEQUENCE (1 << 21)
// clang-format on

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(ensure_future);
_Py_IDENTIFIER(create_future);
_Py_IDENTIFIER(set_exception);
_Py_IDENTIFIER(set_result);
_Py_IDENTIFIER(__await__);
_Py_IDENTIFIER(__dir__);
_Py_IDENTIFIER(KeysView);
_Py_IDENTIFIER(ItemsView);
_Py_IDENTIFIER(ValuesView);
_Py_IDENTIFIER(popitem);
_Py_IDENTIFIER(clear);
_Py_IDENTIFIER(update);
_Py_IDENTIFIER(_js_type_flags);
Js_IDENTIFIER(then);
Js_IDENTIFIER(finally);
Js_IDENTIFIER(has);
Js_IDENTIFIER(set);
Js_IDENTIFIER(delete);
Js_IDENTIFIER(includes);
Js_IDENTIFIER(next);
Js_IDENTIFIER(return);
Js_IDENTIFIER(throw);
_Py_IDENTIFIER(fileno);
_Py_IDENTIFIER(register);

static PyObject* collections_abc;
static PyObject* typing;
static PyObject* MutableMapping;
static PyObject* JsProxy_metaclass;
static PyObject* asyncio_mod;
static PyObject* MutableSequence;
static PyObject* Sequence;
static PyObject* MutableMapping;
static PyObject* Mapping;
static PyObject* future_helper_mod;

Js_static_string(PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL,
                 "This borrowed proxy was automatically destroyed at the "
                 "end of a function call. Try using "
                 "create_proxy or create_once_callable.");

////////////////////////////////////////////////////////////
// JsProxy
//
// This is a Python object that provides idiomatic access to a JavaScript
// object.

struct BufferFields
{
  Py_ssize_t byteLength;
  char* format;
  Py_ssize_t itemsize;
  bool check_assignments;
};

struct MethodFields
{
  JsRef this_;
  vectorcallfunc vectorcall;
};

struct ExceptionFields
{
  PyObject* args;
  PyObject* notes;
  PyObject* traceback;
  PyObject* context;
  PyObject* cause;
  char suppress_context;
};

struct ObjectMapFields
{
  bool hereditary;
};

// clang-format off

// dict and js fields always needs to be in the same place.
// dict field is part of PyBaseExceptionObject, so it should go up top.
// The js field has to come after ExceptionFields so we get the memory layout
// right so we put it at the end
// In between we have a union with the extra fields that are used by just by one
// of JsBuffer, JsCallable, and JsException

typedef struct
{
  PyObject_HEAD
  PyObject* dict;
  union {
    struct BufferFields bf;
    struct MethodFields mf;
    struct ExceptionFields ef;
    struct ObjectMapFields omf;
  } tf;
  JsRef js;
  PyObject* signature;
} JsProxy;
// clang-format on

// Layout of dict and ExceptionFields needs to exactly match the layout of the
// same-name fields of BaseException. Otherwise bad things will happen. Check it
// with static asserts!
_Static_assert(offsetof(PyBaseExceptionObject, dict) == offsetof(JsProxy, dict),
               "dict layout conflict between JsProxy and PyExc_BaseException");

#define CHECK_EXC_FIELD(field)                                                 \
  _Static_assert(                                                              \
    offsetof(PyBaseExceptionObject, field) ==                                  \
      offsetof(JsProxy, tf) + offsetof(struct ExceptionFields, field),         \
    "'" #field "' layout conflict between JsProxy and PyExc_BaseException");

CHECK_EXC_FIELD(args);
CHECK_EXC_FIELD(notes);
CHECK_EXC_FIELD(traceback);
CHECK_EXC_FIELD(context);
CHECK_EXC_FIELD(cause);
CHECK_EXC_FIELD(suppress_context);

#undef CHEC_EXC_FIELD

#define FIELD_SIZE(type, field) sizeof(((type*)0)->field)

_Static_assert(sizeof(PyBaseExceptionObject) ==
                 sizeof(PyObject) + FIELD_SIZE(JsProxy, dict) +
                   sizeof(struct ExceptionFields),
               "size conflict between JsProxy and PyExc_BaseException");
#undef FIELD_SIZE

#define JsProxy_REF(x) ((JsProxy*)x)->js
#define JsProxy_VAL(x) hiwire_get(JsProxy_REF(x))
#define JsProxy_DICT(x) (((JsProxy*)x)->dict)
#define JsProxy_SIG(x) (((JsProxy*)x)->signature)

#define JsMethod_THIS_REF(x) ((JsProxy*)x)->tf.mf.this_
#define JsMethod_THIS(x) JsRef_toVal(JsMethod_THIS_REF(x))
#define JsMethod_VECTORCALL(x) (((JsProxy*)x)->tf.mf.vectorcall)

#define JsException_ARGS(x) (((JsProxy*)x)->tf.ef.args)

#define JsBuffer_FORMAT(x) (((JsProxy*)x)->tf.bf.format)
#define JsBuffer_BYTE_LENGTH(x) (((JsProxy*)x)->tf.bf.byteLength)
#define JsBuffer_ITEMSIZE(x) (((JsProxy*)x)->tf.bf.itemsize)
#define JsBuffer_CHECK_ASSIGNMENTS(x) (((JsProxy*)x)->tf.bf.check_assignments)

#define JsObjMap_HEREDITARY(x) (((JsProxy*)x)->tf.omf.hereditary)

int
JsProxy_getflags(PyObject* self)
{
  PyObject* pyflags =
    _PyObject_GetAttrId((PyObject*)Py_TYPE(self), &PyId__js_type_flags);
  if (pyflags == NULL) {
    return -1;
  }
  int result = PyLong_AsLong(pyflags);
  Py_CLEAR(pyflags);
  return result;
}

#define OBJMAP_HEREDITARY 1
#define OBJMAP_PY_JSON 2

static int
JsProxy_get_objmap_flags(PyObject* self)
{
  int flags = JsProxy_getflags(self);
  bool py_json = !!(flags & (IS_PY_JSON_DICT | IS_PY_JSON_SEQUENCE));
  bool objmap_hereditary = (flags & IS_OBJECT_MAP) && JsObjMap_HEREDITARY(self);
  int result = 0;
  if (py_json) {
    result |= OBJMAP_PY_JSON;
  }
  if (objmap_hereditary) {
    result |= OBJMAP_HEREDITARY;
  }
  return result;
}

int
JsProxy_is_py_json(PyObject* self)
{
  return !!(JsProxy_getflags(self) & (IS_PY_JSON_DICT | IS_PY_JSON_SEQUENCE));
}

static PyObject*
js2python_objmap(JsVal jsval, int flags)
{
  PyObject* result = NULL;

  result = js2python_immutable(jsval);
  if (result != NULL) {
    return result;
  }
  return JsProxy_create_objmap(jsval, flags);
}

PyObject*
js2python_as_py_json(JsVal jsval)
{
  return js2python_objmap(jsval, OBJMAP_PY_JSON);
}

#define INCLUDE_OBJMAP_METHODS(flags)                                          \
  !((flags) & (IS_ARRAY | IS_TYPEDARRAY | IS_ARRAY_LIKE | IS_BUFFER |          \
               IS_DOUBLE_PROXY | IS_ITERATOR | IS_CALLABLE | IS_ERROR))

static int
JsProxy_clear(PyObject* self)
{
  int flags = JsProxy_getflags(self);
  if (flags == -1) {
    return -1;
  }
  if ((flags & IS_CALLABLE) && (JsMethod_THIS_REF(self) != NULL)) {
    JsVal this = hiwire_pop(JsMethod_THIS_REF(self));
    if (pyproxy_Check(this)) {
      destroy_proxy(this, NULL);
    }
  }
  Py_CLEAR(JsProxy_DICT(self));
  Py_CLEAR(JsProxy_SIG(self));
#ifdef DEBUG_F
  extern bool tracerefs;
  if (tracerefs) {
    printf("jsproxy clear %zd, %zd\n", (long)self, (long)JsProxy_REF(self));
  }
#endif
  if (flags & IS_ERROR) {
    if (((PyTypeObject*)PyExc_Exception)->tp_clear(self)) {
      return -1;
    }
  }
  hiwire_CLEAR(JsProxy_REF(self));
  return 0;
}

static void
JsProxy_dealloc(PyObject* self)
{
  FAIL_IF_MINUS_ONE(JsProxy_clear(self));
  Py_TYPE(self)->tp_free(self);
  return;
finally:
  printf("Internal Pyodide error Unraiseable error in JsProxy_dealloc:\n");
  PyErr_Print();
}

// attach a signature to a copy of the JsProxy.
// js_id stays the same.
PyObject*
JsProxy_bind_sig(PyObject* self, PyObject* sig)
{
  return JsProxy_create_with_this(
    JsProxy_VAL(self), JsMethod_THIS(self), sig, JsProxy_is_py_json(self));
}

static PyMethodDef JsProxy_bind_sig_MethodDef = {
  "bind_sig",
  (PyCFunction)JsProxy_bind_sig,
  METH_O,
};

PyObject*
JsProxy_bind_class(PyObject* self, PyObject* sig)
{
  PyObject* result = NULL;

  // Call `sig = jsbind.bind_class_sig(sig)` and then delegate to
  // JsProxy_bind_sig.
  // bind_class_sig takes sig and returns type[sig].
  _Py_IDENTIFIER(bind_class_sig);
  PyObject* class_sig =
    _PyObject_CallMethodIdOneArg(jsbind, &PyId_bind_class_sig, sig);
  FAIL_IF_NULL(class_sig);
  result = JsProxy_bind_sig(self, class_sig);
finally:
  Py_CLEAR(class_sig);
  return result;
}

static PyMethodDef JsProxy_bind_class_MethodDef = {
  "bind_class",
  (PyCFunction)JsProxy_bind_class,
  METH_O,
};

/**
 * repr overload, does `obj.toString()` which produces a low-quality repr.
 */
static PyObject*
JsProxy_Repr(PyObject* self)
{
  JsVal repr = JsvObject_toString(JsProxy_VAL(self));
  if (JsvError_Check(repr)) {
    return NULL;
  }
  return js2python(repr);
}

/**
 * typeof getter, returns `typeof(obj)`.
 */
static PyObject*
JsProxy_typeof(PyObject* self, void* _unused)
{
  return js2python(Jsv_typeof(JsProxy_VAL(self)));
}

static PyObject*
JsProxy_js_id(PyObject* self, void* _unused)
{
  PyObject* result = NULL;

  JsRef idval = JsProxy_REF(self);
  int x[2] = { (int)Py_TYPE(self), (int)idval };
  Py_hash_t result_c = _Py_HashBytes(x, 8);
  FAIL_IF_MINUS_ONE(result_c);
  result = PyLong_FromLong(result_c);
finally:
  return result;
}

EM_JS(bool, isReservedWord, (int word), {
  if (!Module.pythonReservedWords) {
    Module.pythonReservedWords = new Set([
      "False",  "await", "else",     "import", "pass",   "None",    "break",
      "except", "in",    "raise",    "True",   "class",  "finally", "is",
      "return", "and",   "continue", "for",    "lambda", "try",     "as",
      "def",    "from",  "nonlocal", "while",  "assert", "del",     "global",
      "not",    "with",  "async",    "elif",   "if",     "or",      "yield",
    ]);
  }
  return Module.pythonReservedWords.has(word);
})

/**
 * action: a javascript string, one of get, set, or delete. For error reporting.
 * word: a javascript string, the property being accessed
 */
EM_JS(int, normalizeReservedWords, (int word), {
  // clang-format off
  // 1. if word is not a reserved word followed by 0 or more underscores, return
  //    it unchanged.
  const noTrailing_ = word.replace(/_*$/, "");
  if (!isReservedWord(noTrailing_)) {
    return word;
  }
  // 2. If there is at least one trailing underscore, return the word with a
  //    single underscore removed.
  if (noTrailing_ !== word) {
    return word.slice(0, -1);
  }
  // 3. If the word is exactly a reserved word, return it unchanged
  return word;
  // clang-format on
});

EM_JS_VAL(JsVal, JsProxy_GetAttr_js, (JsVal jsobj, const char* ptrkey), {
  const jskey = normalizeReservedWords(UTF8ToString(ptrkey));
  const result = jsobj[jskey];
  // clang-format off
  if (result === undefined && !(jskey in jsobj)) {
    // clang-format on
    return Module.error;
  }
  return result;
});

// JsMethodCallSingleton is a special structure which we return from
// JsProxy_GetMethod. The purpose of it is to optimize method calls
// `jsproxy.f()`. When we execute JsProxy_GetMethod(jsproxy, f_unicode), we
// stuff the JS function `jsproxy.f`, the JS object `jsproxy`, and the method
// signature into one of these structs and return it. Then the call is routed to
// this struct which avoids making a JsProxy.
//
// As an additional optimization, we observe that the pattern is always:
//
// method = PyObject_GetMethod(obj, method_name);
// result = PyObject_Call(method, obj, ... other args)
// Py_DECREF(method);
//
// In other words, the return value of `_PyObject_GetMethod` is used exactly
// once. To save on allocations, we make a global called method_call_singleton
// and reuse it if the reference count is 1 (since then the only reference to it
// is our reference). Otherwise we allocate a new one. We shouldn't have to
// allocate a new `method_call_singleton` except when third party code uses
// `_PyObject_GetMethod`.

typedef struct
{
  PyObject_HEAD;
  JsRef func;
  JsRef this_;
  PyObject* signature;
  vectorcallfunc vectorcall;
} JsMethodCallSingleton;

static PyTypeObject JsMethodCallSingletonType;
static JsMethodCallSingleton* method_call_singleton;

static PyObject*
JsMethodCallSingleton_Vectorcall(PyObject* o,
                                 PyObject* const* pyargs,
                                 size_t nargsf,
                                 PyObject* kwnames)
{
  JsMethodCallSingleton* self = (JsMethodCallSingleton*)o;
  if (self->func == NULL) {
    PyErr_SetString(PyExc_SystemError, "Expected self->func not to be NULL");
    return NULL;
  }
  JsVal func = hiwire_get(self->func);
  JsVal this_ = hiwire_get(self->this_);
  PyObject* sig = self->signature;
  return JsMethod_Vectorcall_impl(func, this_, sig, pyargs, nargsf, kwnames);
}

static JsMethodCallSingleton*
make_method_call_singleton()
{
  JsMethodCallSingleton* result =
    (JsMethodCallSingleton*)JsMethodCallSingletonType.tp_alloc(
      &JsMethodCallSingletonType, 0);
  if (result == NULL) {
    return NULL;
  }
  result->vectorcall = JsMethodCallSingleton_Vectorcall;
  result->func = NULL;
  result->this_ = NULL;
  result->signature = NULL;
  return result;
}

static int
JsMethodCallSingleton_clear(JsMethodCallSingleton* o)
{
  JsMethodCallSingleton* self = (JsMethodCallSingleton*)o;
  hiwire_CLEAR(self->func);
  hiwire_CLEAR(self->this_);
  Py_CLEAR(self->signature);
  return 0;
}

// This isn't static so we can call it from conftest.py to prevent leak check
// false positives
EMSCRIPTEN_KEEPALIVE void
clear_method_call_singleton(void)
{
  if (Py_REFCNT(method_call_singleton) == 1) {
    // We hold the only reference count so we can reuse it.
    // Clear it out first.
    JsMethodCallSingleton_clear(method_call_singleton);
  } else {
    // Oops, someone held on to the previous method_call_singleton or otherwise
    // used it in an unexpected way. Make another!
    // This should never happen except when third party code uses
    // `_PyObject_GetMethod`.
    Py_SETREF(method_call_singleton, make_method_call_singleton());
  }
}

static void
JsMethodCallSingleton_dealloc(PyObject* self)
{
  JsMethodCallSingleton_clear((JsMethodCallSingleton*)self);
  Py_TYPE(self)->tp_free(self);
}

static PyTypeObject JsMethodCallSingletonType = {
  .tp_name = "_pyodide.JsMethodCallSingleton",
  .tp_basicsize = sizeof(JsMethodCallSingleton),
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_VECTORCALL,
  .tp_vectorcall_offset = offsetof(JsMethodCallSingleton, vectorcall),
  .tp_call = (PyCFunctionWithKeywords)PyObject_Vectorcall,
  .tp_doc = "A hacky type to avoid temporaries",
  .tp_dealloc = JsMethodCallSingleton_dealloc,
};

static PyObject*
JsProxy_GetAttr_helper(PyObject* self, PyObject* attr, bool is_method);

PyObject*
JsProxy_GetMethod(PyObject* self, PyObject* attr)
{
  return JsProxy_GetAttr_helper(self, attr, true);
}

PyObject*
JsProxy_GetAttr(PyObject* self, PyObject* attr)
{
  return JsProxy_GetAttr_helper(self, attr, false);
}

/**
 * getattr overload, first checks whether the attribute exists in the JsProxy
 * dict, and if so returns that. Otherwise, it attempts lookup on the wrapped
 * object.
 */
static PyObject*
JsProxy_GetAttr_helper(PyObject* self, PyObject* attr, bool is_method)
{
  PyObject* result = _PyObject_GenericGetAttrWithDict(self, attr, NULL, 1);
  if (result != NULL || PyErr_Occurred()) {
    return result;
  }

  bool success = false;
  JsVal jsresult = JS_ERROR;
  PyObject* get_attr_sig_res = NULL;
  PyObject* attr_sig = NULL;
  // result:
  PyObject* pyresult = NULL;

  const char* key = PyUnicode_AsUTF8(attr);
  FAIL_IF_NULL(key);
  if (strcmp(key, "keys") == 0 && JsvArray_Check(JsProxy_VAL(self))) {
    // Sometimes Python APIs test for the existence of a "keys" function
    // to decide whether something should be treated like a dict.
    // This mixes badly with the javascript Array.keys API, so pretend that it
    // doesn't exist. (Array.keys isn't very useful anyways so hopefully this
    // won't confuse too many people...)
    PyErr_SetString(PyExc_AttributeError, key);
    FAIL();
  }

  jsresult = JsProxy_GetAttr_js(JsProxy_VAL(self), key);
  if (JsvError_Check(jsresult)) {
    if (!PyErr_Occurred()) {
      PyErr_SetString(PyExc_AttributeError, key);
    }
    FAIL();
  }

  if (JsProxy_SIG(self) != NULL) {
    _Py_IDENTIFIER(get_attr_sig);
    get_attr_sig_res = _PyObject_CallMethodIdObjArgs(
      jsbind, &PyId_get_attr_sig, JsProxy_SIG(self), attr, NULL);
    FAIL_IF_NULL(get_attr_sig_res);

    bool got_converter;
    PyObject* sig;
    if (!PyArg_ParseTuple(get_attr_sig_res, "pO", &got_converter, &sig)) {
      FAIL();
    }
    if (got_converter) {
      pyresult = Js2PyConverter_convert(sig, jsresult, Jsv_null);
      goto success;
    }
    if (!Py_IsNone(sig)) {
      attr_sig = Py_XNewRef(sig);
    }
  }
  // attr_sig might contain the result sig or it might be NULL.
  // TODO: maybe allow being strict and requiring that we get a sig?
  if (pyproxy_Check(jsresult)) {
    pyresult = js2python(jsresult);
    FAIL_IF_NULL(pyresult);
    goto success;
  }
  if (is_method) {
    if (!JsvFunction_Check(jsresult)) {
      // Not callable, this should be an error...
      PyErr_SetString(PyExc_TypeError, "Expected callable");
      FAIL();
    }
    clear_method_call_singleton();
    pyresult = Py_NewRef(method_call_singleton);
    method_call_singleton->func = hiwire_new(jsresult);
    method_call_singleton->this_ = JsProxy_REF(self);
    hiwire_incref(method_call_singleton->this_);
    method_call_singleton->signature = Py_NewRef(attr_sig);
    goto success;
  }
  if (JsvFunction_Check(jsresult)) {
    pyresult =
      JsProxy_create_with_this(jsresult, JsProxy_VAL(self), attr_sig, false);
  } else if (attr_sig) {
    pyresult =
      JsProxy_create_with_this(jsresult, Jsv_undefined, attr_sig, false);
  } else {
    pyresult = js2python(jsresult);
  }
  FAIL_IF_NULL(pyresult);

success:
  success = true;
finally:
  Py_CLEAR(attr_sig);
  Py_CLEAR(get_attr_sig_res);
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

// clang-format off
EM_JS_NUM(errcode,
JsProxy_SetAttr_js,
(JsVal jsobj, const char* ptrkey, JsVal jsval),
{
  let jskey = normalizeReservedWords(UTF8ToString(ptrkey));
  jsobj[jskey] = jsval;
});
// clang-format on

EM_JS_NUM(errcode, JsProxy_DelAttr_js, (JsVal jsobj, const char* ptrkey), {
  let jskey = normalizeReservedWords(UTF8ToString(ptrkey));
  delete jsobj[jskey];
});

/**
 * setattr / delttr overload. TODO: Raise an error if the attribute exists on
 * the proxy.
 */
static int
JsProxy_SetAttr(PyObject* self, PyObject* attr, PyObject* pyvalue)
{
  bool success = false;

  const char* key = PyUnicode_AsUTF8(attr);
  FAIL_IF_NULL(key);

  if (strncmp(key, "__", 2) == 0) {
    // Avoid creating reference loops between Python and JavaScript with js
    // modules. Such reference loops make it hard to avoid leaking memory.
    if (strcmp(key, "__loader__") == 0 || strcmp(key, "__name__") == 0 ||
        strcmp(key, "__package__") == 0 || strcmp(key, "__path__") == 0 ||
        strcmp(key, "__spec__") == 0) {
      return PyObject_GenericSetAttr(self, attr, pyvalue);
    }
  }

  if (pyvalue == NULL) {
    FAIL_IF_MINUS_ONE(JsProxy_DelAttr_js(JsProxy_VAL(self), key));
  } else {
    JsVal jsvalue = python2js(pyvalue);
    FAIL_IF_MINUS_ONE(JsProxy_SetAttr_js(JsProxy_VAL(self), key, jsvalue));
  }

  success = true;
finally:
  return success ? 0 : -1;
}

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
  JsVal jsa = JsProxy_VAL(a);
  JsVal jsb = JsProxy_VAL(b);
  switch (op) {
    case Py_LT:
      result = Jsv_less_than(jsa, jsb);
      break;
    case Py_LE:
      result = Jsv_less_than_equal(jsa, jsb);
      break;
    case Py_EQ:
      result = Jsv_equal(jsa, jsb);
      break;
    case Py_NE:
      result = Jsv_not_equal(jsa, jsb);
      break;
    case Py_GT:
      result = Jsv_greater_than(jsa, jsb);
      break;
    case Py_GE:
      result = Jsv_greater_than_equal(jsa, jsb);
      break;
  }

  if (result) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

EM_JS_VAL(JsVal, JsProxy_GetIter_js, (JsVal obj), {
  return obj[Symbol.iterator]();
});

/**
 * iter overload. Present if IS_ITERABLE but not IS_ITERATOR (if the IS_ITERATOR
 * flag is present we use PyObject_SelfIter). Does `obj[Symbol.iterator]()`.
 */
static PyObject*
JsProxy_GetIter(PyObject* self)
{
  JsVal iter = JsProxy_GetIter_js(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(iter);
  return js2python_objmap(iter, JsProxy_get_objmap_flags(self));
finally:
  return NULL;
}

// clang-format off
EM_JS_NUM(
JsVal,
handle_next_result_js,
(JsVal res, int* done, char** msg),
{
  let errmsg;
  if(typeof res !== "object") {
    errmsg = `Result should have type "object" not "${typeof res}"`;
  } else if(typeof res.done === "undefined") {
    if (typeof res.then === "function") {
      errmsg = `Result was a promise, use anext() / asend() / athrow() instead.`;
    } else {
      errmsg = `Result has no "done" field.`;
    }
  }
  if (errmsg) {
    DEREF_U32(msg, 0) = stringToNewUTF8(errmsg);
    DEREF_U32(done, 0) = -1;
  }
  DEREF_U32(done, 0) = res.done;
  return res.value;
});

PySendResult
handle_next_result(JsVal next_res, PyObject** result, int objmap_flags){
  PySendResult res = PYGEN_ERROR;
  char* msg = NULL;
  *result = NULL;
  int done;

  JsVal jsresult = handle_next_result_js(next_res, &done, &msg);
  // done:
  //   1 ==> finished
  //   0 ==> not finished
  //  -1 ==> error (if msg is set, we set the error flag to a TypeError with
  //         msg otherwise the error flag must already be set)
  if (msg) {
    PyErr_SetString(PyExc_TypeError, msg);
    free(msg);
    FAIL();
  }
  FAIL_IF_MINUS_ONE(done);
  // If there was no "value", "idresult" will be jsundefined
  // so pyvalue will be set to Py_None.
  *result = js2python_immutable(jsresult);
  if (!*result) {
    *result = JsProxy_create_objmap(jsresult, objmap_flags);
  }
  FAIL_IF_NULL(*result);
  if(pyproxy_Check(jsresult)) {
    Js_static_string(msg, "This borrowed proxy was automatically destroyed at the end"
                          " of a generator");
    destroy_proxy(jsresult, &msg);
  }

  res = done ? PYGEN_RETURN : PYGEN_NEXT;
finally:
  return res;
}

// clang-format on

PySendResult
JsProxy_am_send(PyObject* self, PyObject* arg, PyObject** result)
{
  *result = NULL;
  PySendResult ret = PYGEN_ERROR;

  JsVal proxies = JsvArray_New();
  JsVal jsarg = Jsv_undefined;
  if (arg) {
    jsarg = python2js_track_proxies(arg, proxies, true);
    FAIL_IF_JS_ERROR(jsarg);
  }
  JsVal next_res =
    JsvObject_CallMethodId_OneArg(JsProxy_VAL(self), &JsId_next, jsarg);
  FAIL_IF_JS_ERROR(next_res);
  ret = handle_next_result(next_res, result, JsProxy_get_objmap_flags(self));
finally:
  if (arg) {
    destroy_proxies(proxies, &PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL);
  }
  return ret;
}

PyObject*
JsProxy_IterNext(PyObject* self)
{
  PyObject* result;
  if (JsProxy_am_send(self, NULL, &result) == PYGEN_RETURN) {
    // The Python docs for tp_iternext say "When the iterator is exhausted, it
    // must return NULL; a StopIteration exception may or may not be set."
    // So if the result is None, we can just leave error flag unset.
    if (!Py_IsNone(result)) {
      _PyGen_SetStopIterationValue(result);
    }
    Py_CLEAR(result);
  }
  return result;
}

PyObject*
JsGenerator_send(PyObject* self, PyObject* arg)
{
  PyObject* result;
  if (JsProxy_am_send(self, arg, &result) == PYGEN_RETURN) {
    if (Py_IsNone(result)) {
      PyErr_SetNone(PyExc_StopIteration);
    } else {
      _PyGen_SetStopIterationValue(result);
    }
    Py_CLEAR(result);
  }
  return result;
}

static PyMethodDef JsGenerator_send_MethodDef = {
  "send",
  (PyCFunction)JsGenerator_send,
  METH_O,
};

static PyObject* JsException;

static PyObject*
JsException_reduce(PyObject* self, PyObject* Py_UNUSED(ignored))
{
  // Record name, message, and stack.
  // See _core_docs.JsException._new_exc where the unpickling will happen.
  PyObject* res = NULL;
  PyObject* args = NULL;
  PyObject* name = NULL;
  PyObject* message = NULL;
  PyObject* stack = NULL;

  name = PyObject_GetAttrString(self, "name");
  FAIL_IF_NULL(name);
  message = PyObject_GetAttrString(self, "message");
  FAIL_IF_NULL(message);
  stack = PyObject_GetAttrString(self, "stack");
  FAIL_IF_NULL(stack);

  args = PyTuple_Pack(3, name, message, stack);
  FAIL_IF_NULL(args);

  PyObject* dict = JsProxy_DICT(self);
  if (dict) {
    res = PyTuple_Pack(3, Py_TYPE(self), args, dict);
  } else {
    res = PyTuple_Pack(2, Py_TYPE(self), args);
  }

finally:
  Py_CLEAR(args);
  Py_CLEAR(name);
  Py_CLEAR(message);
  Py_CLEAR(stack);
  return res;
}

static PyMethodDef JsException_reduce_MethodDef = {
  "__reduce__",
  (PyCFunction)JsException_reduce,
  METH_NOARGS
};

PyObject*
JsException_js_error_getter(PyObject* self, void* closure)
{
  Py_INCREF(self);
  return self;
}

// clang-format off
EM_JS_VAL(JsVal,
JsException_new_helper,
(char* name_ptr, char* message_ptr, char* stack_ptr),
{
  let name = UTF8ToString(name_ptr);
  let message = UTF8ToString(message_ptr);
  let stack = UTF8ToString(stack_ptr);
  return API.deserializeError(name, message, stack);
});
// clang-format on

// We use this to unpickle JsException objects.
static PyObject*
JsException_new(PyTypeObject* subtype, PyObject* args, PyObject* kwds)
{
  static char* kwlist[] = { "name", "message", "stack", 0 };
  char* name;
  char* message = "";
  char* stack = "";
  if (!PyArg_ParseTupleAndKeywords(
        args, kwds, "s|ss:__new__", kwlist, &name, &message, &stack)) {
    return NULL;
  }
  JsVal result = JsException_new_helper(name, message, stack);
  FAIL_IF_JS_ERROR(result);
  return js2python(result);
finally:
  return NULL;
}

static int
JsException_init(PyBaseExceptionObject* self, PyObject* args, PyObject* kwds)
{
  return 0;
}

/**
 * Shared logic between throw and async throw.
 *
 * Possibly "typ" is an exception instance and val and tb are null. Otherwise,
 * it's an old style call "typ" should be an exception type, "val" an instance,
 * and tb an optional traceback. Figure out which is the case and get an
 * exception object.
 *
 * Then if the exception object is PyExc_GeneratorExit, call jsobj.return().
 * Otherwise, convert it to js and call jsobj.throw(jsexc). Return the result of
 * whichever of these two calls we make (or set the error flag and return NULL
 * if something goes wrong).
 */
JsVal
process_throw_args(PyObject* self, PyObject* typ, PyObject* val, PyObject* tb)
{
  if (Py_IsNone(tb)) {
    tb = NULL;
  } else if (tb != NULL && !PyTraceBack_Check(tb)) {
    PyErr_SetString(PyExc_TypeError,
                    "throw() third argument must be a traceback object");
    return JS_ERROR;
  }

  Py_INCREF(typ);
  Py_XINCREF(val);
  Py_XINCREF(tb);

  if (PyExceptionClass_Check(typ)) {
    PyErr_NormalizeException(&typ, &val, &tb);
    if (tb != NULL) {
      PyException_SetTraceback(val, tb);
    }
  } else if (PyExceptionInstance_Check(typ)) {
    /* Raising an instance.  The value should be a dummy. */
    if (val && !Py_IsNone(val)) {
      PyErr_SetString(PyExc_TypeError,
                      "instance exception may not have a separate value");
      goto failed_throw;
    } else {
      /* Normalize to raise <class>, <instance> */
      Py_XDECREF(val);
      val = typ;
      typ = PyExceptionInstance_Class(typ);
      Py_INCREF(typ);

      if (tb == NULL)
        /* Returns NULL if there's no traceback */
        tb = PyException_GetTraceback(val);
    }
  } else {
    /* Not something you can raise.  throw() fails. */
    PyErr_Format(PyExc_TypeError,
                 "exceptions must be classes or instances "
                 "deriving from BaseException, not %s",
                 Py_TYPE(typ)->tp_name);
    goto failed_throw;
  }

  PyErr_Restore(typ, val, tb);
  JsVal res;
  if (PyErr_ExceptionMatches(PyExc_GeneratorExit)) {
    PyErr_Clear();
    res = JsvObject_CallMethodId_NoArgs(JsProxy_VAL(self), &JsId_return);
  } else {
    JsVal exc;
    if (PyErr_ExceptionMatches(JsException)) {
      PyErr_Fetch(&typ, &val, &tb);
      exc = JsProxy_VAL(val);
      Py_CLEAR(typ);
      Py_CLEAR(val);
      Py_CLEAR(tb);
    } else {
      exc = wrap_exception(); // cannot fail.
    }
    res = JsvObject_CallMethodId_OneArg(JsProxy_VAL(self), &JsId_throw, exc);
  }
  return res;

failed_throw:
  /* Didn't use our arguments, so restore their original refcounts */
  Py_DECREF(typ);
  Py_XDECREF(val);
  Py_XDECREF(tb);
  return JS_ERROR;
}

static PyObject*
JsGenerator_throw_inner(PyObject* self,
                        PyObject* typ,
                        PyObject* val,
                        PyObject* tb)
{
  PyObject* result = NULL;
  JsVal throw_res = process_throw_args(self, typ, val, tb);
  FAIL_IF_JS_ERROR(throw_res);
  PySendResult ret = handle_next_result(throw_res, &result, 0);
  if (ret == PYGEN_RETURN) {
    if (Py_IsNone(result)) {
      PyErr_SetNone(PyExc_StopIteration);
    } else {
      _PyGen_SetStopIterationValue(result);
    }
    Py_CLEAR(result);
  }
finally:
  return result;
}

static PyObject*
JsGenerator_throw(PyObject* self, PyObject* const* args, Py_ssize_t nargs)
{
  PyObject* typ;
  PyObject* val = NULL;
  PyObject* tb = NULL;

  if (!_PyArg_ParseStack(args, nargs, "O|OO:throw", &typ, &val, &tb)) {
    return NULL;
  }

  return JsGenerator_throw_inner(self, typ, val, tb);
}

static PyMethodDef JsGenerator_throw_MethodDef = {
  "throw",
  (PyCFunction)JsGenerator_throw,
  METH_FASTCALL,
};

static PyObject*
JsGenerator_close(PyObject* self, PyObject* ignored)
{
  PyObject* result =
    JsGenerator_throw_inner(self, PyExc_GeneratorExit, NULL, NULL);
  if (result != NULL) {
    // We could also just return it, but this matches Python. Generators that do
    // shenanigans stuff in "finally" blocks are hard to work with so we might
    // as well yell at people for using them.
    PyErr_SetString(PyExc_RuntimeError, "JavaScript generator ignored return");
    Py_DECREF(result);
    return NULL;
  }
  if (PyErr_ExceptionMatches(PyExc_StopIteration) ||
      PyErr_ExceptionMatches(PyExc_GeneratorExit)) {
    PyErr_Clear(); /* ignore these errors */
    Py_RETURN_NONE;
  }
  return NULL;
}

static PyMethodDef JsGenerator_close_MethodDef = {
  "close",
  (PyCFunction)JsGenerator_close,
  METH_NOARGS,
};

EM_JS_VAL(JsVal, JsProxy_GetAsyncIter_js, (JsVal obj), {
  return obj[Symbol.asyncIterator]();
});

/**
 * iter overload. Present if IS_ASYNC_ITERABLE but not IS_ITERATOR (if the
 * IS_ITERATOR flag is present we use PyObject_SelfIter). Does
 * `obj[Symbol.asyncIterator]()`.
 */
static PyObject*
JsProxy_GetAsyncIter(PyObject* self)
{
  JsVal iter = JsProxy_GetAsyncIter_js(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(iter);
  return js2python(iter);
finally:
  return NULL;
}

/**
 * The innermost layer of the result handling. This is called when the promise
 * resolves. status tells us whether we are:
 *  1. returning
 *  0. yielding
 * -1. raising
 *
 *
 * jsvalue is either the result that we are returning/yielding or the error we
 * are raising. closing tells us whether ``close`` was called, if so we raise
 * an error if there is a yield in a finally block.
 */
EMSCRIPTEN_KEEPALIVE void
_agen_handle_result_js_c(PyObject* set_result,
                         PyObject* set_exception,
                         int status,
                         JsVal jsvalue,
                         bool closing)
{
  PyObject* pyvalue = NULL;
  PyObject* e = NULL;

  if (closing && status == 0) {
    // If closing, status should not be yielding.
    PyErr_SetString(PyExc_RuntimeError, "JavaScript generator ignored return");
    goto return_error;
  }

  pyvalue = js2python(jsvalue);
  if (pyvalue == NULL) {
    // hopefully this won't happen...
    PyErr_SetString(PyExc_RuntimeError, "Unable to get result");
    goto return_error;
  }

  if (status == 1 && pyproxy_Check(jsvalue)) {
    Js_static_string(
      msg,
      "This borrowed proxy was automatically destroyed at the end"
      " of a async generator");
    destroy_proxy(jsvalue, &msg);
  }

  if (status == 0) {
    PyObject_CallOneArg(set_result, pyvalue);
    // Not sure what to do if there is an error here...
    goto finally;
  }

  if (status == 1) {
    // Returning
    e = PyObject_CallOneArg(PyExc_StopAsyncIteration, pyvalue);
    // Not sure what to do if there is an error here...
    goto return_error;
  }

  if (status == -1) {
    Py_INCREF(pyvalue);
    e = pyvalue;
    goto return_error;
  }

return_error:
  if (e == NULL) {
    // Grab e from error flag
    PyObject *tp, *tb;
    PyErr_Fetch(&tp, &e, &tb);
    Py_CLEAR(tp);
    Py_CLEAR(tb);
  }
  if (closing && (PyErr_GivenExceptionMatches(e, PyExc_StopAsyncIteration) ||
                  PyErr_GivenExceptionMatches(e, PyExc_GeneratorExit))) {
    PyObject_CallOneArg(set_result, Py_None);
    goto finally;
  }

  PyObject_CallOneArg(set_exception, e);
  // Don't know what to do if there was an error...
  PyErr_Clear();
  goto finally;

finally:
  Py_CLEAR(pyvalue);
  Py_CLEAR(e);
}

// clang-format off
EM_JS_NUM(
int,
_agen_handle_result_js,
(JsVal p, char** msg, PyObject* set_result, PyObject* set_exception, bool closing),
{
  // First check that p is a proper promise, if not return the error message for
  // the type error.
  let errmsg;
  if(typeof p !== "object") {
    errmsg = `Result of anext() should be object not ${typeof p}`;
  } else if(typeof p.then !== "function") {
    if (typeof p.done === "boolean") {
      errmsg = `Result of anext() was not a promise, use next() instead.`;
    } else {
      errmsg = `Result of anext() was not a promise.`;
    }
  }
  if (errmsg) {
    DEREF_U32(msg, 0) = stringToNewUTF8(errmsg);
    return -1;
  }
  // We need to hold onto set_result and set_exception until the promise resolves.
  _Py_IncRef(set_result);
  _Py_IncRef(set_exception);
  // Call back into C to create the response.
  p.then(({done, value}) => {
    __agen_handle_result_js_c(set_result, set_exception, done, value, closing);
  }, (err) => {
    __agen_handle_result_js_c(set_result, set_exception, -1, err, closing);
  }).finally(() => {
    _Py_DecRef(set_result);
    _Py_DecRef(set_exception);
  });
  return 0;
});
// clang-format on

/**
 * Common logic between asend, athrow and aclose. Handle the resulting promise
 * returned from next, throw, or return.
 *
 * Create a future and attach the promise to the future using the helper
 * anext_js.
 */
PyObject*
_agen_handle_result(JsVal promise, bool closing)
{
  bool success = false;
  PyObject* loop = NULL;
  PyObject* set_result = NULL;
  PyObject* set_exception = NULL;
  PyObject* result = NULL;

  loop = _PyObject_CallMethodIdNoArgs(asyncio_mod, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);

  result = _PyObject_CallMethodIdNoArgs(loop, &PyId_create_future);
  FAIL_IF_NULL(result);

  set_result = _PyObject_GetAttrId(result, &PyId_set_result);
  FAIL_IF_NULL(set_result);
  set_exception = _PyObject_GetAttrId(result, &PyId_set_exception);
  FAIL_IF_NULL(set_exception);

  char* msg = NULL;
  int status =
    _agen_handle_result_js(promise, &msg, set_result, set_exception, closing);
  if (status == -1) {
    if (msg) {
      PyErr_SetString(PyExc_TypeError, msg);
      free(msg);
    }
    FAIL();
  }

  success = true;
finally:
  if (!success) {
    Py_CLEAR(result);
  }
  Py_CLEAR(loop);
  Py_CLEAR(set_result);
  Py_CLEAR(set_exception);
  return result;
}

static PyObject*
JsGenerator_asend(PyObject* self, PyObject* arg)
{
  PyObject* result = NULL;

  JsVal proxies = JsvArray_New();
  JsVal jsarg = Jsv_undefined;
  if (arg != NULL) {
    jsarg = python2js_track_proxies(arg, proxies, true);
    FAIL_IF_JS_ERROR(jsarg);
  }
  JsVal next_res =
    JsvObject_CallMethodId_OneArg(JsProxy_VAL(self), &JsId_next, jsarg);
  FAIL_IF_JS_ERROR(next_res);
  result = _agen_handle_result(next_res, false);

finally:
  if (arg) {
    destroy_proxies(proxies, &PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL);
  }
  return result;
}

static PyMethodDef JsGenerator_asend_MethodDef = {
  "asend",
  (PyCFunction)JsGenerator_asend,
  METH_O,
};

static PyObject*
JsGenerator_anext(PyObject* self)
{
  return JsGenerator_asend(self, NULL);
}

static PyObject*
JsGenerator_athrow(PyObject* self, PyObject* const* args, Py_ssize_t nargs)
{
  PyObject* typ;
  PyObject* val = NULL;
  PyObject* tb = NULL;

  if (!_PyArg_ParseStack(args, nargs, "O|OO:athrow", &typ, &val, &tb)) {
    return NULL;
  }

  PyObject* result = NULL;

  JsVal throw_res = process_throw_args(self, typ, val, tb);
  FAIL_IF_JS_ERROR(throw_res);
  result = _agen_handle_result(throw_res, false);

finally:
  return result;
}

static PyMethodDef JsGenerator_athrow_MethodDef = {
  "athrow",
  (PyCFunction)JsGenerator_athrow,
  METH_FASTCALL,
};

static PyObject*
JsGenerator_aclose(PyObject* self, PyObject* ignored)
{
  PyObject* result = NULL;

  JsVal throw_res = process_throw_args(self, PyExc_GeneratorExit, NULL, NULL);
  FAIL_IF_JS_ERROR(throw_res);
  result = _agen_handle_result(throw_res, true);

finally:
  return result;
}

static PyMethodDef JsGenerator_aclose_MethodDef = {
  "aclose",
  (PyCFunction)JsGenerator_aclose,
  METH_NOARGS,
};

/**
 * This is exposed as a METH_NOARGS method on the JsProxy. It returns
 * Object.entries(obj) as a new JsProxy.
 */
static PyObject*
JsProxy_object_entries(PyObject* self, PyObject* _args)
{
  JsVal jsresult = JsvObject_Entries(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(jsresult);
  return JsProxy_create(jsresult);
finally:
  return NULL;
}

static PyMethodDef JsProxy_object_entries_MethodDef = {
  "object_entries",
  (PyCFunction)JsProxy_object_entries,
  METH_NOARGS,
};

/**
 * This is exposed as a METH_NOARGS method on the JsProxy. It returns
 * Object.keys(obj) as a new JsProxy.
 */
static PyObject*
JsProxy_object_keys(PyObject* self, PyObject* _args)
{
  JsVal jsresult = JsvObject_Keys(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(jsresult);
  return JsProxy_create(jsresult);
finally:
  return NULL;
}

static PyMethodDef JsProxy_object_keys_MethodDef = {
  "object_keys",
  (PyCFunction)JsProxy_object_keys,
  METH_NOARGS,
};

/**
 * This is exposed as a METH_NOARGS method on the JsProxy. It returns
 * Object.entries(obj) as a new JsProxy.
 */
static PyObject*
JsProxy_object_values(PyObject* self, PyObject* _args)
{
  JsVal jsresult = JsvObject_Values(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(jsresult);
  return JsProxy_create(jsresult);
finally:
  return NULL;
}

static PyMethodDef JsProxy_object_values_MethodDef = {
  "object_values",
  (PyCFunction)JsProxy_object_values,
  METH_NOARGS,
};

#define ERR_NO_LENGTH -2
#define ERR_NEGATIVE_LENGTH -3
#define ERR_LENGTH_TOO_BIG -4

EM_JS_NUM(int, get_length_helper, (JsVal val), {
  // clang-format off
  let result;
  // Maybe we should allow it to return a BigInt?
  if (typeof val.size === "number") {
    result = val.size;
  } else if (typeof val.length === "number") {
    result = val.length;
  } else {
    return ERR_NO_LENGTH;
  }
  if(result < 0){
    return ERR_NEGATIVE_LENGTH;
  }
  if(result > INT_MAX){
    return ERR_LENGTH_TOO_BIG;
  }
  return result;
  // clang-format on
});

// Needed to render the length accurately when there is an error
EM_JS_REF(char*, get_length_string, (JsVal val), {
  let result;
  // clang-format off
  if (typeof val.size === "number") {
    result = val.size;
  } else if (typeof val.length === "number") {
    result = val.length;
  }
  // clang-format on
  return stringToNewUTF8(" " + result.toString())
})

static int
get_length(JsVal obj)
{
  int result = get_length_helper(obj);
  if (result >= 0) {
    return result;
  }
  // Something went wrong. Case work:
  // * Either `val.size` or `val.length` was a getter which managed to raise an
  //   error. Propagate this JS error.
  if (result == -1) {
    return -1;
  }

  // Doesn't have a length or size, or the typeof the returned value is not
  // number
  if (result == ERR_NO_LENGTH) {
    PyErr_SetString(PyExc_TypeError, "object does not have a valid length");
    return -1;
  }

  char* length_as_string_alloc = get_length_string(obj);
  char* length_as_string = length_as_string_alloc;
  if (length_as_string == NULL) {
    // Really screwed up.
    length_as_string = "";
  }
  if (result == ERR_NEGATIVE_LENGTH) {
    PyErr_Format(
      PyExc_ValueError, "length%s of object is negative", length_as_string);
  }
  if (result == ERR_LENGTH_TOO_BIG) {
    PyErr_Format(PyExc_OverflowError,
                 "length%s of object is larger than INT_MAX (%d)",
                 length_as_string,
                 INT_MAX);
  }
  if (length_as_string_alloc != NULL) {
    free(length_as_string_alloc);
  }
  return -1;
}

/**
 * len(proxy) overload for proxies of Js objects with `length` or `size` fields.
 * Prefers `object.size` over `object.length`. Controlled by HAS_LENGTH.
 */
static Py_ssize_t
JsProxy_length(PyObject* self)
{
  return get_length(JsProxy_VAL(self));
}

static PyObject*
JsProxy_item_array(PyObject* self, Py_ssize_t i)
{
  PyObject* pyresult = NULL;
  JsVal jsresult = JsvArray_Get(JsProxy_VAL(self), i);
  FAIL_IF_JS_ERROR(jsresult);
  pyresult = js2python(jsresult);
finally:
  return pyresult;
}

/**
 * __getitem__ for proxies of Js Arrays, controlled by IS_ARRAY
 */
static PyObject*
JsArray_subscript(PyObject* self, PyObject* item)
{
  PyObject* pyresult = NULL;

  if (PyIndex_Check(item)) {
    Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
    if (i == -1)
      FAIL_IF_ERR_OCCURRED();
    if (i < 0) {
      int length = get_length(JsProxy_VAL(self));
      FAIL_IF_MINUS_ONE(length);
      i += length;
    }
    JsVal jsresult = JsvArray_Get(JsProxy_VAL(self), i);
    if (JsvError_Check(jsresult)) {
      if (!PyErr_Occurred()) {
        PyErr_SetObject(PyExc_IndexError, item);
      }
      FAIL();
    }
    pyresult = js2python_objmap(jsresult, JsProxy_get_objmap_flags(self));
    goto success;
  }
  if (PySlice_Check(item)) {
    Py_ssize_t start, stop, step;
    FAIL_IF_MINUS_ONE(PySlice_Unpack(item, &start, &stop, &step));
    int length = get_length(JsProxy_VAL(self));
    FAIL_IF_MINUS_ONE(length);
    // PySlice_AdjustIndices is "Always successful" per the docs.
    Py_ssize_t slicelength = PySlice_AdjustIndices(length, &start, &stop, step);
    JsVal jsresult;
    if (slicelength <= 0) {
      jsresult = JsvArray_New();
    } else {
      jsresult =
        JsvArray_slice(JsProxy_VAL(self), slicelength, start, stop, step);
    }
    FAIL_IF_JS_ERROR(jsresult);
    pyresult = js2python_objmap(jsresult, JsProxy_get_objmap_flags(self));
    goto success;
  }
  PyErr_Format(PyExc_TypeError,
               "list indices must be integers or slices, not %.200s",
               Py_TYPE(item)->tp_name);
success:
finally:
  return pyresult;
}

PyObject*
JsArray_sq_item(PyObject* o, Py_ssize_t i)
{
  PyObject* pyresult = NULL;

  JsVal jsresult = JsvArray_Get(JsProxy_VAL(o), i);
  if (JsvError_Check(jsresult)) {
    if (!PyErr_Occurred()) {
      PyErr_SetString(PyExc_IndexError, "array index out of range");
    }
    FAIL();
  }
  pyresult = js2python(jsresult);
  FAIL_IF_NULL(pyresult);
finally:
  return pyresult;
}

Py_ssize_t
JsArray_sq_ass_item(PyObject* o, Py_ssize_t i, PyObject* pyval)
{
  bool success = false;

  if (pyval == NULL) {
    // Delete
    JsVal jsval = JsvArray_Delete(JsProxy_VAL(o), i);
    FAIL_IF_JS_ERROR(jsval);
    success = true;
    goto finally;
  }

  JsVal jsval = python2js(pyval);
  FAIL_IF_JS_ERROR(jsval);
  FAIL_IF_MINUS_ONE(JsvArray_Set(JsProxy_VAL(o), i, jsval));

  success = true;
finally:
  return success ? 0 : -1;
}

Py_ssize_t
JsTypedArray_sq_ass_item(PyObject* o, Py_ssize_t i, PyObject* pyval)
{
  if (pyval == NULL) {
    PyErr_SetString(PyExc_TypeError, "object doesn't support item deletion");
    return -1;
  }
  return JsArray_sq_ass_item(o, i, pyval);
}

/**
 * __getitem__ for proxies of Js TypedArrays, controlled by IS_TYPEDARRAY
 */
static PyObject*
JsTypedArray_subscript(PyObject* o, PyObject* item)
{
  if (PySlice_Check(item)) {
    PyErr_SetString(PyExc_NotImplementedError,
                    "Slice subscripting isn't implemented for typed arrays");
    return NULL;
  }
  return JsArray_subscript(o, item);
}

/**
 * __getitem__ for proxies of array-like objects like HTMLCollection or
 * NodeList, controlled by IS_ARRAY_LIKE
 */
static PyObject*
JsArrayLike_subscript(PyObject* o, PyObject* item)
{
  if (PySlice_Check(item)) {
    PyErr_SetString(PyExc_NotImplementedError,
                    "Slice subscripting is only implemented for arrays, not "
                    "for array-like objects");
    return NULL;
  }
  return JsArray_subscript(o, item);
}

/**
 * __setitem__ and __delitem__ for proxies of Js Arrays, controlled by IS_ARRAY
 */
static int
JsArray_ass_subscript(PyObject* self, PyObject* item, PyObject* pyvalue)
{
  bool success = false;
  PyObject* seq = NULL;
  Py_ssize_t i;
  if (PySlice_Check(item)) {
    Py_ssize_t start, stop, step, slicelength;
    FAIL_IF_MINUS_ONE(PySlice_Unpack(item, &start, &stop, &step));
    int length = get_length(JsProxy_VAL(self));
    FAIL_IF_MINUS_ONE(length);
    // PySlice_AdjustIndices is "Always successful" per the docs.
    slicelength = PySlice_AdjustIndices(length, &start, &stop, step);

    if (pyvalue != NULL) {
      seq = PySequence_Fast(pyvalue, "must assign iterable to extended slice");
      FAIL_IF_NULL(seq);
    }
    if (pyvalue != NULL && step != 1 &&
        PySequence_Fast_GET_SIZE(seq) != slicelength) {
      PyErr_Format(PyExc_ValueError,
                   "attempt to assign sequence of "
                   "size %zd to extended slice of "
                   "size %zd",
                   PySequence_Fast_GET_SIZE(seq),
                   slicelength);
      FAIL();
    }
    if (pyvalue == NULL) {
      if (slicelength <= 0) {
        success = true;
        goto finally;
      }
      if (step < 0) {
        // We have to delete in backwards order so make sure step > 0.
        stop = start + 1;
        start = stop + step * (slicelength - 1) - 1;
        step = -step;
      }
      FAIL_IF_MINUS_ONE(JsvArray_slice_assign(
        JsProxy_VAL(self), slicelength, start, stop, step, 0, NULL));
    } else {
      if (step != 1 && !slicelength) {
        // At this point, assigning to an extended slice of length 0 must be a
        // no-op
        success = true;
        goto finally;
      }
      FAIL_IF_MINUS_ONE(JsvArray_slice_assign(JsProxy_VAL(self),
                                              slicelength,
                                              start,
                                              stop,
                                              step,
                                              PySequence_Fast_GET_SIZE(seq),
                                              PySequence_Fast_ITEMS(seq)));
    }
    success = true;
    goto finally;
  } else if (PyIndex_Check(item)) {
    i = PyNumber_AsSsize_t(item, PyExc_IndexError);
    if (i == -1)
      FAIL_IF_ERR_OCCURRED();
    if (i < 0) {
      int length = get_length(JsProxy_VAL(self));
      FAIL_IF_MINUS_ONE(length);
      i += length;
    }
  } else {
    PyErr_Format(PyExc_TypeError,
                 "list indices must be integers or slices, not %.200s",
                 Py_TYPE(item)->tp_name);
    return -1;
  }

  if (pyvalue == NULL) {
    if (JsvError_Check(JsvArray_Delete(JsProxy_VAL(self), i))) {
      if (!PyErr_Occurred()) {
        PyErr_SetObject(PyExc_IndexError, item);
      }
      FAIL();
    }
  } else {
    JsVal jsvalue = python2js(pyvalue);
    FAIL_IF_JS_ERROR(jsvalue);
    FAIL_IF_MINUS_ONE(JsvArray_Set(JsProxy_VAL(self), i, jsvalue));
  }
  success = true;
finally:
  Py_CLEAR(seq);
  return success ? 0 : -1;
}

/**
 * __setitem__ and __delitem__ for proxies of TypedArrays, controlled by
 * IS_TYPEDARRAY
 */
static int
JsTypedArray_ass_subscript(PyObject* o, PyObject* item, PyObject* pyvalue)
{
  if (pyvalue == NULL) {
    PyErr_SetString(PyExc_TypeError, "object doesn't support item deletion");
    return -1;
  }
  if (PySlice_Check(item)) {
    PyErr_SetString(PyExc_NotImplementedError,
                    "Slice assignment isn't implemented for typed arrays");
    return -1;
  }
  return JsArray_ass_subscript(o, item, pyvalue);
}

static int
JsArray_extend_by_python_iterable(JsVal jsarray, PyObject* iterable)
{
  PyObject* it = NULL;
  bool success = false;

  if (PyList_CheckExact(iterable) || PyTuple_CheckExact(iterable)) {
    iterable = PySequence_Fast(iterable, "argument must be iterable");
    if (!iterable)
      return -1;
    Py_ssize_t n = PySequence_Fast_GET_SIZE(iterable);
    if (n == 0) {
      /* short circuit when iterable is empty */
      success = true;
      goto finally;
    }
    /* note that we may still have self == iterable here for the
     * situation a.extend(a), but the following code works
     * in that case too.  Just make sure to resize self
     * before calling PySequence_Fast_ITEMS.
     */
    /* populate the end of self with iterable's items */
    PyObject** src = PySequence_Fast_ITEMS(iterable);
    for (int i = 0; i < n; i++) {
      JsVal jsval = python2js(src[i]);
      FAIL_IF_JS_ERROR(jsval);
      JsvArray_Push(jsarray, jsval);
    }
  } else {
    Py_INCREF(iterable);
    it = PyObject_GetIter(iterable);
    PyObject* (*iternext)(PyObject*);
    iternext = *Py_TYPE(it)->tp_iternext;

    /* Run iterator to exhaustion. */
    for (;;) {
      PyObject* item = iternext(it);
      if (item == NULL) {
        if (PyErr_Occurred()) {
          if (PyErr_ExceptionMatches(PyExc_StopIteration))
            PyErr_Clear();
          else {
            FAIL();
          }
        }
        break;
      }
      JsVal jsval = python2js(item);
      FAIL_IF_JS_ERROR(jsval);
      JsvArray_Push(jsarray, jsval);
    }
  }
  success = true;
finally:
  Py_CLEAR(it);
  return success ? 0 : -1;
}

EM_JS(void, destroy_jsarray_entries, (JsVal array), {
  for (let v of array) {
    // clang-format off
    try {
      if(typeof v.destroy === "function"){
          v.destroy();
      }
    } catch(e) {
      console.warn("Weird error:", e);
    }
    // clang-format on
  }
})

static PyObject*
JsArray_extend_meth(PyObject* o, PyObject* iterable)
{
  bool success = false;

  JsVal temp = JsvArray_New();
  // Make sure that if anything goes wrong the original array stays unmodified
  FAIL_IF_MINUS_ONE(JsArray_extend_by_python_iterable(temp, iterable));
  JsvArray_Extend(JsProxy_VAL(o), temp);
  success = true;
finally:
  if (!success) {
    destroy_jsarray_entries(temp);
  }
  if (success) {
    Py_RETURN_NONE;
  } else {
    return NULL;
  }
}

static PyMethodDef JsArray_extend_MethodDef = {
  "extend",
  (PyCFunction)JsArray_extend_meth,
  METH_O,
};

static PyObject*
JsArray_sq_concat(PyObject* self, PyObject* other)
{
  PyObject* pyresult = NULL;
  bool success = true;

  JsVal jsresult = JsvArray_ShallowCopy(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(jsresult);
  pyresult = js2python(jsresult);
  FAIL_IF_NULL(pyresult);
  FAIL_IF_MINUS_ONE(
    JsArray_extend_by_python_iterable(JsProxy_VAL(pyresult), other));
finally:
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

static PyObject*
JsArray_sq_inplace_concat(PyObject* self, PyObject* other)
{
  PyObject* result = JsArray_extend_meth(self, other);
  FAIL_IF_NULL(result);
  Py_DECREF(result);
  Py_INCREF(self);
  return self;
finally:
  return NULL;
}

EM_JS_VAL(JsVal, JsArray_repeat_js, (JsVal o, Py_ssize_t count), {
  // clang-format off
  return Array.from({ length : count }, () => o).flat();
  // clang-format on
})

static PyObject*
JsArray_sq_repeat(PyObject* o, Py_ssize_t count)
{
  JsVal jsresult = JsArray_repeat_js(JsProxy_Val(o), count);
  FAIL_IF_JS_ERROR(jsresult);
  return js2python(jsresult);

finally:
  return NULL;
}

EM_JS_NUM(errcode, JsArray_inplace_repeat_js, (JsVal o, Py_ssize_t count), {
  // clang-format off
  o.splice(0, o.length, ... Array.from({ length : count }, () => o).flat());
  // clang-format on
})

static PyObject*
JsArray_sq_inplace_repeat(PyObject* o, Py_ssize_t count)
{
  FAIL_IF_MINUS_ONE(JsArray_inplace_repeat_js(JsProxy_VAL(o), count));
  Py_INCREF(o);
  return o;
finally:
  return NULL;
}

static PyObject*
JsArray_append(PyObject* self, PyObject* arg)
{
  bool success = false;

  JsVal jsarg = python2js(arg);
  FAIL_IF_JS_ERROR(jsarg);
  JsvArray_Push(JsProxy_VAL(self), jsarg);

  success = true;
finally:
  if (success) {
    Py_RETURN_NONE;
  } else {
    return NULL;
  }
}

static PyMethodDef JsArray_append_MethodDef = {
  "append",
  (PyCFunction)JsArray_append,
  METH_O,
};

// Copied directly from Python
static inline int
valid_index(Py_ssize_t i, Py_ssize_t limit)
{
  /* The cast to size_t lets us use just a single comparison
      to check whether i is in the range: 0 <= i < limit.

      See:  Section 14.2 "Bounds Checking" in the Agner Fog
      optimization manual found at:
      https://www.agner.org/optimize/optimizing_cpp.pdf
  */
  return (size_t)i < (size_t)limit;
}

static PyObject*
JsArray_pop(PyObject* self, PyObject* const* args, Py_ssize_t nargs)
{
  PyObject* pyresult = NULL;
  PyObject* iobj = NULL;
  Py_ssize_t index = -1;

  if (!_PyArg_CheckPositional("pop", nargs, 0, 1)) {
    FAIL();
  }
  if (nargs > 0) {
    iobj = PyNumber_Index(args[0]);
    FAIL_IF_NULL(iobj);
    index = PyLong_AsSsize_t(iobj);
    if (index == -1) {
      FAIL_IF_ERR_OCCURRED();
    }
  }

  int length = get_length(JsProxy_VAL(self));
  FAIL_IF_MINUS_ONE(length);

  if (length == 0) {
    /* Special-case most common failure cause */
    PyErr_SetString(PyExc_IndexError, "pop from empty list");
    FAIL();
  }
  if (index < 0)
    index += length;
  if (!valid_index(index, length)) {
    PyErr_SetString(PyExc_IndexError, "pop index out of range");
    FAIL();
  }

  JsVal jsresult = JsvArray_Delete(JsProxy_VAL(self), index);
  FAIL_IF_JS_ERROR(jsresult);
  pyresult = js2python(jsresult);

finally:
  Py_CLEAR(iobj);
  return pyresult;
}

static PyMethodDef JsArray_pop_MethodDef = {
  "pop",
  (PyCFunction)JsArray_pop,
  METH_FASTCALL,
};

EM_JS(JsVal, JsArray_reversed_iterator, (JsVal array), {
  return new ReversedIterator(array);
}
// clang-format off
class ReversedIterator {
  constructor(array) {
    this._array = array;
    this._i = array.length - 1;
  }

  __length_hint__() {
    return this._array.length;
  }

  [Symbol.toStringTag]() {
    return "ReverseIterator";
  }

  next() {
    const i = this._i;
    const a = this._array;
    const done = i < 0;
    const value = done ? undefined : a[i];
    this._i--;
    return { done, value };
  }
}
// clang-format on
)

static PyObject*
JsArray_reversed(PyObject* self, PyObject* ignored)
{
  JsVal iter = JsArray_reversed_iterator(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(iter);
  return js2python(iter);
finally:
  return NULL;
}

static PyMethodDef JsArray_reversed_MethodDef = {
  "__reversed__",
  (PyCFunction)JsArray_reversed,
  METH_NOARGS,
};

// clang-format off
EM_JS_NUM(int,
JsArray_index_js,
(JsVal o, JsVal v, int start, int stop),
{
  for (let i = start; i < stop; i++) {
    if (o[i] === v) {
      return i;
    }
  }
  return -2;
})
// clang-format on

static Py_ssize_t
JsArray_index_helper(PyObject* self,
                     PyObject* value,
                     Py_ssize_t start,
                     Py_ssize_t stop)
{
  Py_ssize_t length = JsProxy_length(self);
  if (length == -1) {
    return -1;
  }
  if (start < 0) {
    start += length;
    if (start < 0)
      start = 0;
  }
  if (stop < 0) {
    stop += length;
    if (stop < 0)
      stop = 0;
  }
  if (stop > length) {
    stop = length;
  }

  JsVal jsvalue = python2js_track_proxies(value, JS_ERROR, true);
  if (JsvError_Check(jsvalue)) {
    PyErr_Clear();
    for (Py_ssize_t i = start; i < stop; i++) {
      JsVal jsobj = JsvArray_Get(JsProxy_VAL(self), i);
      // We know `value` is not a `JsProxy`: if it were we would have taken the
      // other branch. Thus, if `jsobj` is not a `PyProxy`,
      // `PyObject_RichCompareBool` is guaranteed to return false. As a speed
      // up, only perform the check if the object is a `PyProxy`.
      PyObject* pyobj = pyproxy_AsPyObject(jsobj); /* borrowed! */
      if (pyobj == NULL) {
        continue;
      }
      int cmp = PyObject_RichCompareBool(pyobj, value, Py_EQ);
      if (cmp > 0)
        return i;
      else if (cmp < 0)
        goto error;
    }
    goto error;
  } else {
    int result = JsArray_index_js(JsProxy_VAL(self), jsvalue, start, stop);
    if (result == -2) {
      goto error;
    }
    return result;
  }
error:
  PyErr_Format(PyExc_ValueError, "%R is not in list", value);
  return -1;
}

static PyObject*
JsArray_index(PyObject* self, PyObject* args)
{
  PyObject* value;
  Py_ssize_t start = 0;
  Py_ssize_t stop = PY_SSIZE_T_MAX;
  if (!PyArg_ParseTuple(args, "O|nn:index", &value, &start, &stop)) {
    return NULL;
  }

  Py_ssize_t result = JsArray_index_helper(self, value, start, stop);
  if (result == -1) {
    return NULL;
  }
  return PyLong_FromSsize_t(result);
}

static PyMethodDef JsArray_index_MethodDef = {
  "index",
  (PyCFunction)JsArray_index,
  METH_VARARGS,
};

// clang-format off
EM_JS_NUM(int,
JsArray_count_js,
(JsVal o, JsVal v),
{
  let result = 0;
  for (let i = 0; i < o.length; i++) {
    if (o[i] === v) {
      result++;
    }
  }
  return result;
})
// clang-format on

static PyObject*
JsArray_count(PyObject* self, PyObject* value)
{
  JsVal jsvalue = python2js_track_proxies(value, JS_ERROR, true);
  if (JsvError_Check(jsvalue)) {
    PyErr_Clear();
    int result = 0;
    Py_ssize_t stop = JsProxy_length(self);
    if (stop == -1) {
      return NULL;
    }
    for (int i = 0; i < stop; i++) {
      JsVal jsobj = JsvArray_Get(JsProxy_VAL(self), i);
      // We know `value` is not a `JsProxy`: if it were we would have taken the
      // other branch. Thus, if `jsobj` is not a `PyProxy`,
      // `PyObject_RichCompareBool` is guaranteed to return false. As a speed
      // up, only perform the check if the object is a `PyProxy`.
      PyObject* pyobj = pyproxy_AsPyObject(jsobj); /* borrowed! */
      if (pyobj == NULL) {
        continue;
      }
      int cmp = PyObject_RichCompareBool(pyobj, value, Py_EQ);
      if (cmp > 0)
        result++;
      else if (cmp < 0)
        return NULL;
    }
    return PyLong_FromSsize_t(result);
  } else {
    int result = JsArray_count_js(JsProxy_VAL(self), jsvalue);
    if (result == -1) {
      return NULL;
    } else {
      return PyLong_FromSsize_t(result);
    }
  }
}

static PyMethodDef JsArray_count_MethodDef = {
  "count",
  (PyCFunction)JsArray_count,
  METH_O,
};

EM_JS_NUM(errcode, JsArray_reverse_js, (JsVal array), { array.reverse(); })

static PyObject*
JsArray_reverse(PyObject* self, PyObject* _ignored)
{
  if (JsArray_reverse_js(JsProxy_Val(self)) == -1) {
    return NULL;
  }
  Py_RETURN_NONE;
}

static PyMethodDef JsArray_reverse_MethodDef = {
  "reverse",
  (PyCFunction)JsArray_reverse,
  METH_NOARGS,
};

static PyObject*
JsArray_insert(PyObject* self, PyObject* args)
{
  Py_ssize_t index;
  PyObject* pyvalue;
  if (!PyArg_ParseTuple(args, "nO:insert", &index, &pyvalue)) {
    return NULL;
  }
  JsVal jsvalue = python2js(pyvalue);
  FAIL_IF_JS_ERROR(jsvalue);
  FAIL_IF_MINUS_ONE(JsvArray_Insert(JsProxy_VAL(self), index, jsvalue));
  Py_RETURN_NONE;
finally:
  return NULL;
}

static PyMethodDef JsArray_insert_MethodDef = {
  "insert",
  (PyCFunction)JsArray_insert,
  METH_VARARGS,
};

static PyObject*
JsArray_remove(PyObject* self, PyObject* arg)
{
  int index = JsArray_index_helper(self, arg, 0, PY_SSIZE_T_MAX);
  FAIL_IF_MINUS_ONE(index);
  JsvArray_Delete(JsProxy_VAL(self), index);
  Py_RETURN_NONE;
finally:
  return NULL;
}

static PyMethodDef JsArray_remove_MethodDef = {
  "remove",
  (PyCFunction)JsArray_remove,
  METH_O,
};

// A helper method for jsproxy_subscript.
EM_JS_VAL(JsVal, JsProxy_subscript_js, (JsVal obj, JsVal key), {
  let result = obj.get(key);
  // clang-format off
  if (result === undefined) {
    // Try to distinguish between undefined and missing:
    // If the object has a "has" method and it returns false for this key, the
    // key is missing. Otherwise, assume key present and value was undefined.
    // TODO: in absence of a "has" method, should we return None or KeyError?
    if (obj.has && typeof obj.has === "function" && !obj.has(key)) {
      return Module.error;
    }
  }
  // clang-format on
  return result;
});

/**
 * __getitem__ for JsProxies that have a "get" method. Translates proxy[key] to
 * obj.get(key). Controlled by HAS_GET
 */
static PyObject*
JsProxy_subscript(PyObject* self, PyObject* pyidx)
{
  JsVal idx = python2js(pyidx);
  FAIL_IF_JS_ERROR(idx);
  JsVal result = JsProxy_subscript_js(JsProxy_VAL(self), idx);
  if (JsvError_Check(result)) {
    if (!PyErr_Occurred()) {
      PyErr_SetObject(PyExc_KeyError, pyidx);
    }
    FAIL();
  }
  return js2python(result);
finally:
  return NULL;
}

/**
 * __setitem__ / __delitem__ for JsProxies that have a "set" method (it's
 * currently assumed that they'll also have a del method...). Translates
 * `proxy[key] = value` to `obj.set(key, value)` and `del proxy[key]` to
 * `obj.del(key)`.
 * Controlled by HAS_SET.
 */
static int
JsProxy_ass_subscript(PyObject* self, PyObject* pyidx, PyObject* pyvalue)
{
  bool success = false;

  JsVal idx = python2js(pyidx);
  FAIL_IF_JS_ERROR(idx);
  if (pyvalue == NULL) {
    JsVal result =
      JsvObject_CallMethodId_OneArg(JsProxy_VAL(self), &JsId_delete, idx);
    FAIL_IF_JS_ERROR(result);
    if (!Jsv_to_bool(result)) {
      if (!PyErr_Occurred()) {
        PyErr_SetObject(PyExc_KeyError, pyidx);
      }
      FAIL();
    }
  } else {
    JsVal value = python2js(pyvalue);
    FAIL_IF_JS_ERROR(value);
    FAIL_IF_JS_ERROR(
      JsvObject_CallMethodId_TwoArgs(JsProxy_VAL(self), &JsId_set, idx, value));
  }
  success = true;
finally:
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
  int result = -1;
  JsVal jsobj = python2js(obj);
  FAIL_IF_JS_ERROR(jsobj);
  JsVal jsresult =
    JsvObject_CallMethodId_OneArg(JsProxy_VAL(self), &JsId_includes, jsobj);
  FAIL_IF_JS_ERROR(jsresult);
  result = Jsv_to_bool(jsresult);

finally:
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
  int result = -1;
  JsVal jsobj = python2js(obj);
  FAIL_IF_JS_ERROR(jsobj);
  JsVal jsresult =
    JsvObject_CallMethodId_OneArg(JsProxy_VAL(self), &JsId_has, jsobj);
  FAIL_IF_JS_ERROR(jsresult);
  result = Jsv_to_bool(jsresult);

finally:
  return result;
}

EM_JS_VAL(JsVal, JsMap_GetIter_js, (JsVal obj), {
  let result;
  // clang-format off
  if(typeof obj.keys === 'function') {
    // clang-format on
    result = obj.keys();
  } else {
    result = obj[Symbol.iterator]();
  }
  return result;
})

/**
 * iter overload for maps. Present if IS_ITERABLE but not IS_ITERATOR (if the
 * IS_ITERATOR flag is present we use PyObject_SelfIter).
 * Prefers to iterate using map.keys() over map[Symbol.iterator]().
 */
static PyObject*
JsMap_GetIter(PyObject* self)
{
  JsVal iter = JsMap_GetIter_js(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(iter);
  return js2python(iter);
finally:
  return NULL;
}

static PyObject*
JsMap_keys(PyObject* self, PyObject* Py_UNUSED(ignored))
{
  return _PyObject_CallMethodIdOneArg(collections_abc, &PyId_KeysView, self);
}

static PyMethodDef JsMap_keys_MethodDef = {
  "keys",
  (PyCFunction)JsMap_keys,
  METH_NOARGS,
};

static PyObject*
JsMap_values(PyObject* self, PyObject* Py_UNUSED(ignored))
{
  return _PyObject_CallMethodIdOneArg(collections_abc, &PyId_ValuesView, self);
}

static PyMethodDef JsMap_values_MethodDef = {
  "values",
  (PyCFunction)JsMap_values,
  METH_NOARGS,
};

static PyObject*
JsMap_items(PyObject* self, PyObject* Py_UNUSED(ignored))
{
  return _PyObject_CallMethodIdOneArg(collections_abc, &PyId_ItemsView, self);
}

static PyMethodDef JsMap_items_MethodDef = {
  "items",
  (PyCFunction)JsMap_items,
  METH_NOARGS,
};

static PyObject*
JsMap_get(PyObject* self,
          PyObject* const* args,
          Py_ssize_t nargs,
          PyObject* kwnames)
{
  static const char* const _keywords[] = { "key", "default", 0 };
  static struct _PyArg_Parser _parser = {
    .format = "O|O:get",
    .keywords = _keywords,
  };
  PyObject* key;
  PyObject* default_ = Py_None;
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &key, &default_)) {
    return NULL;
  }

  PyObject* result = PyObject_GetItem(self, key);
  if (result != NULL) {
    return result;
  }
  PyErr_Clear();
  Py_INCREF(default_);
  return default_;
}

static PyMethodDef JsMap_get_MethodDef = {
  "get",
  (PyCFunction)JsMap_get,
  METH_FASTCALL | METH_KEYWORDS,
};

static PyObject*
JsMap_pop(PyObject* self,
          PyObject* const* args,
          Py_ssize_t nargs,
          PyObject* kwnames)
{
  static const char* const _keywords[] = { "key", "default", 0 };
  static struct _PyArg_Parser _parser = {
    .format = "O|O:pop",
    .keywords = _keywords,
  };
  PyObject* key;
  PyObject* default_ = NULL;
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &key, &default_)) {
    return NULL;
  }

  PyObject* result = PyObject_GetItem(self, key);
  if (result == NULL) {
    if (default_ == NULL) {
      return NULL;
    } else {
      PyErr_Clear();
      Py_INCREF(default_);
      return default_;
    }
  }
  if (PyObject_DelItem(self, key) == -1) {
    Py_CLEAR(result);
    return NULL;
  }
  return result;
}

static PyMethodDef JsMap_pop_MethodDef = {
  "pop",
  (PyCFunction)JsMap_pop,
  METH_FASTCALL | METH_KEYWORDS,
};

static PyObject*
JsMap_popitem(PyObject* self, PyObject* Py_UNUSED(ignored))
{
  return _PyObject_CallMethodIdOneArg(MutableMapping, &PyId_popitem, self);
}

static PyMethodDef JsMap_popitem_MethodDef = {
  "popitem",
  (PyCFunction)JsMap_popitem,
  METH_NOARGS,
};

EM_JS_NUM(int, JsMap_clear_js, (JsVal map), {
  // clang-format off
  if(map && typeof map.clear === "function") {
    // clang-format on
    map.clear();
    return 1;
  }
  return 0;
})

static PyObject*
JsMap_clear(PyObject* self, PyObject* Py_UNUSED(ignored))
{
  // If the map has a JavaScript "clear" function, use that.
  int status = JsMap_clear_js(JsProxy_VAL(self));
  if (status == -1) {
    return NULL;
  }
  if (status) {
    Py_RETURN_NONE;
  }
  // Otherwise iterate the map and delete the entries one at a time.
  return _PyObject_CallMethodIdOneArg(MutableMapping, &PyId_clear, self);
}

static PyMethodDef JsMap_clear_MethodDef = {
  "clear",
  (PyCFunction)JsMap_clear,
  METH_NOARGS,
};

PyObject*
JsMap_update(JsProxy* self, PyObject* args, PyObject* kwds)
{
  PyObject* arg = NULL;
  if (!PyArg_ParseTuple(args, "|O:update", &arg)) {
    return NULL;
  }
  if (arg != NULL) {
    PyObject* status = _PyObject_CallMethodIdObjArgs(
      MutableMapping, &PyId_update, self, arg, NULL);
    if (status == NULL) {
      return NULL;
    }
    Py_CLEAR(status);
  }
  if (kwds != NULL) {
    PyObject* status = _PyObject_CallMethodIdObjArgs(
      MutableMapping, &PyId_update, self, arg, NULL);
    if (status == NULL) {
      return NULL;
    }
    Py_CLEAR(status);
  }
  Py_RETURN_NONE;
}

static PyMethodDef JsMap_update_MethodDef = {
  "update",
  (PyCFunction)JsMap_update,
  METH_VARARGS | METH_KEYWORDS,
};

static PyObject*
JsMap_setdefault(PyObject* self,
                 PyObject* const* args,
                 Py_ssize_t nargs,
                 PyObject* kwnames)
{
  static const char* const _keywords[] = { "key", "default", 0 };
  static struct _PyArg_Parser _parser = {
    .format = "O|O:setdefault",
    .keywords = _keywords,
  };
  PyObject* key;
  PyObject* default_ = Py_None;
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &key, &default_)) {
    return NULL;
  }

  PyObject* result = PyObject_GetItem(self, key);
  if (result != NULL) {
    return result;
  }
  PyErr_Clear();
  if (PyObject_SetItem(self, key, default_) == -1) {
    return NULL;
  }
  Py_INCREF(default_);
  return default_;
}

static PyMethodDef JsMap_setdefault_MethodDef = {
  "setdefault",
  (PyCFunction)JsMap_setdefault,
  METH_FASTCALL | METH_KEYWORDS,
};

EM_JS_VAL(JsVal, JsProxy_Dir_js, (JsVal jsobj), {
  let result = [];
  do {
    // clang-format off
    const names = Object.getOwnPropertyNames(jsobj);
    result.push(...names.filter(
      s => {
        let c = s.charCodeAt(0);
        return c < 48 || c > 57; /* Filter out integer array indices */
      }
    )
    // If the word is a reserved word followed by 0 or more underscores, add an
    // extra underscore to reverse the transformation applied by normalizeReservedWords.
    .map(word => isReservedWord(word.replace(/_*$/, "")) ? word + "_" : word));
    // clang-format on
  } while (jsobj = Object.getPrototypeOf(jsobj));
  return result;
});

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
  JsVal jsdir = JS_ERROR;
  PyObject* pydir = NULL;
  PyObject* keys_str = NULL;

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
  jsdir = JsProxy_Dir_js(JsProxy_VAL(self));
  pydir = js2python(jsdir);
  FAIL_IF_NULL(pydir);
  // Merge and sort
  FAIL_IF_MINUS_ONE(_PySet_Update(result_set, pydir));
  if (JsvArray_Check(JsProxy_VAL(self))) {
    // See comment about Array.keys in GetAttr
    keys_str = PyUnicode_FromString("keys");
    FAIL_IF_NULL(keys_str);
    FAIL_IF_MINUS_ONE(PySet_Discard(result_set, keys_str));
  }
  result = PyList_New(0);
  FAIL_IF_NULL(result);
  FAIL_IF_MINUS_ONE(PyList_Extend(result, result_set));
  FAIL_IF_MINUS_ONE(PyList_Sort(result));

  success = true;
finally:
  Py_CLEAR(object__dir__);
  Py_CLEAR(keys);
  Py_CLEAR(result_set);
  Py_CLEAR(pydir);
  Py_CLEAR(keys_str);
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

static PyMethodDef JsProxy_Dir_MethodDef = {
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
  static const char* const _keywords[] = { "depth", "default_converter", 0 };
  static struct _PyArg_Parser _parser = {
    .format = "|$iO:to_py",
    .keywords = _keywords,
  };
  int depth = -1;
  PyObject* default_converter = NULL;
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &depth, &default_converter)) {
    return NULL;
  }
  JsVal default_converter_js = Jsv_undefined;
  if (default_converter != NULL) {
    default_converter_js = python2js(default_converter);
  }
  PyObject* result =
    js2python_convert(JsProxy_VAL(self), depth, default_converter_js);
  if (pyproxy_Check(default_converter_js)) {
    destroy_proxy(default_converter_js, NULL);
  }
  return result;
}

static PyMethodDef JsProxy_toPy_MethodDef = {
  "to_py",
  (PyCFunction)JsProxy_toPy,
  METH_FASTCALL | METH_KEYWORDS,
};

EM_JS_BOOL(bool, JsProxy_Bool_js, (JsVal val), {
  // clang-format off
  if (!val) {
    return false;
  }
  // We want to return false on container types with size 0.
  if (val.size === 0) {
    if(/HTML[A-Za-z]*Element/.test(getTypeTag(val))){
      // HTMLSelectElement and HTMLInputElement can have size 0 but we still
      // want to return true.
      return true;
    }
    // I think other things with a size are container types.
    return false;
  }
  if (val.length === 0 && JsvArray_Check(val)) {
    return false;
  }
  if (val.byteLength === 0) {
    return false;
  }
  return true;
  // clang-format on
});

/**
 * Overload for bool(proxy), implemented for every JsProxy. Return `False` if
 * the object is falsey in JavaScript, or if it has a `size` field equal to 0,
 * or if it has a `length` field equal to zero and is an array. Otherwise return
 * `True`. This last convention could be replaced with "has a length equal to
 * zero and is not a function". In JavaScript, `func.length` returns the number
 * of arguments `func` expects. We definitely don't want 0-argument functions to
 * be falsey.
 */
static int
JsProxy_Bool(PyObject* self)
{
  return JsProxy_Bool_js(JsProxy_VAL(self));
}

/**
 * Create a Future attached to the given Promise. When the promise is
 * resolved/rejected, the status of the future is set accordingly and
 * done_callback is called.
 */
PyObject*
wrap_promise(JsVal promise, JsVal done_callback, PyObject* js2py_converter)
{
  bool success = false;
  PyObject* loop = NULL;
  PyObject* helpers = NULL;
  PyObject* set_result = NULL;
  PyObject* set_exception = NULL;

  PyObject* result = NULL;

  loop = _PyObject_CallMethodIdNoArgs(asyncio_mod, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);

  result = _PyObject_CallMethodIdNoArgs(loop, &PyId_create_future);
  FAIL_IF_NULL(result);

  _Py_IDENTIFIER(get_future_resolvers);
  helpers = _PyObject_CallMethodIdOneArg(
    future_helper_mod, &PyId_get_future_resolvers, result);
  FAIL_IF_NULL(helpers);
  set_result = Py_XNewRef(PyTuple_GetItem(helpers, 0));
  FAIL_IF_NULL(set_result);
  set_exception = Py_XNewRef(PyTuple_GetItem(helpers, 1));
  FAIL_IF_NULL(set_exception);

  promise = JsvPromise_Resolve(promise);
  FAIL_IF_JS_ERROR(promise);
  JsVal promise_handles = create_promise_handles(
    set_result, set_exception, done_callback, js2py_converter);
  FAIL_IF_JS_ERROR(promise_handles);
  FAIL_IF_JS_ERROR(
    JsvObject_CallMethodId(promise, &JsId_then, promise_handles));

  success = true;
finally:
  Py_CLEAR(loop);
  Py_CLEAR(helpers);
  Py_CLEAR(set_result);
  Py_CLEAR(set_exception);
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
JsProxy_Await(PyObject* self)
{
  if (!JsvPromise_Check(JsProxy_VAL(self))) {
    // This error is unlikely to be hit except in cases of intentional mischief.
    // Such mischief is conducted in test_jsproxy:test_mixins_errors_2
    PyObject* str = PyObject_Repr(self);
    const char* str_utf8 = PyUnicode_AsUTF8(str);
    PyErr_Format(PyExc_TypeError,
                 "object %s can't be used in 'await' expression",
                 str_utf8);
    return NULL;
  }
  PyObject* fut = NULL;
  PyObject* result = NULL;

  fut = wrap_promise(JsProxy_VAL(self), Jsv_null, NULL);
  FAIL_IF_NULL(fut);
  result = _PyObject_CallMethodIdNoArgs(fut, &PyId___await__);

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
static PyObject*
JsProxy_then(JsProxy* self, PyObject* args, PyObject* kwds)
{
  PyObject* onfulfilled = NULL;
  PyObject* onrejected = NULL;

  static char* kwlist[] = { "onfulfilled", "onrejected", 0 };
  if (!PyArg_ParseTupleAndKeywords(
        args, kwds, "|OO:then", kwlist, &onfulfilled, &onrejected)) {
    return NULL;
  }

  PyObject* result = NULL;

  if (Py_IsNone(onfulfilled)) {
    Py_CLEAR(onfulfilled);
  }
  if (Py_IsNone(onrejected)) {
    Py_CLEAR(onrejected);
  }
  JsVal promise = JsvPromise_Resolve(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(promise);
  JsVal promise_handles =
    create_promise_handles(onfulfilled, onrejected, Jsv_null, NULL);
  FAIL_IF_JS_ERROR(promise_handles);
  JsVal result_promise =
    JsvObject_CallMethodId(promise, &JsId_then, promise_handles);
  if (JsvError_Check(result_promise)) {
    Py_CLEAR(onfulfilled);
    Py_CLEAR(onrejected);
    FAIL();
  }
  result = JsProxy_create(result_promise);

finally:
  // don't clear onfulfilled, onrejected, they are borrowed from arguments.
  return result;
}

static PyMethodDef JsProxy_then_MethodDef = {
  "then",
  (PyCFunction)JsProxy_then,
  METH_VARARGS | METH_KEYWORDS,
};

/**
 * Overload for `catch` for JsProxies with a `then` method.
 */
static PyObject*
JsProxy_catch(JsProxy* self, PyObject* onrejected)
{
  PyObject* result = NULL;

  JsVal promise = JsvPromise_Resolve(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(promise);
  // We have to use create_promise_handles so that the handler gets released
  // even if the promise resolves successfully.
  JsVal promise_handles =
    create_promise_handles(NULL, onrejected, Jsv_null, NULL);
  FAIL_IF_JS_ERROR(promise_handles);
  JsVal result_promise =
    JsvObject_CallMethodId(promise, &JsId_then, promise_handles);
  if (JsvError_Check(result_promise)) {
    Py_DECREF(onrejected);
    FAIL();
  }
  result = JsProxy_create(result_promise);

finally:
  return result;
}

static PyMethodDef JsProxy_catch_MethodDef = {
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
static PyObject*
JsProxy_finally(JsProxy* self, PyObject* onfinally)
{
  JsVal promise = JsvPromise_Resolve(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(promise);
  // Finally method is called no matter what so we can use
  // `create_once_callable`.
  JsVal proxy = create_once_callable(onfinally, true);
  FAIL_IF_JS_ERROR(proxy);
  JsVal result_promise =
    JsvObject_CallMethodId_OneArg(promise, &JsId_finally, proxy);
  if (JsvError_Check(result_promise)) {
    Py_DECREF(onfinally);
    FAIL();
  }

  return JsProxy_create(result_promise);
finally:
  return NULL;
}

static PyMethodDef JsProxy_finally_MethodDef = {
  "finally_",
  (PyCFunction)JsProxy_finally,
  METH_O,
};

static PyObject*
JsProxy_as_object_map(PyObject* self,
                      PyObject* const* args,
                      Py_ssize_t nargs,
                      PyObject* kwnames)
{
  static bool warned = false;
  if (!warned) {
    warned = true;
    // Use RuntimeWarning not DeprecationWarning because DeprecationWarning is
    // hidden by default and therefore useless.
    if (PyErr_WarnEx(
          PyExc_RuntimeWarning,
          "JsProxy.as_object_map() is deprecated. Use as_py_json() instead.",
          1) == -1) {
      return NULL;
    }
  }
  static const char* const _keywords[] = { "hereditary", 0 };
  static struct _PyArg_Parser _parser = {
    .format = "|$p:as_object_map",
    .keywords = _keywords,
  };
  bool hereditary = false;
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &hereditary)) {
    return NULL;
  }

  int type_flags = IS_OBJECT_MAP;
  PyObject* proxy = JsProxy_create_with_type(
    type_flags, JsProxy_VAL(self), JsMethod_THIS(self), NULL);
  FAIL_IF_NULL(proxy);
  JsObjMap_HEREDITARY(proxy) = hereditary;

finally:
  return proxy;
}

static PyMethodDef JsProxy_as_object_map_MethodDef = {
  "as_object_map",
  (PyCFunction)JsProxy_as_object_map,
  METH_FASTCALL | METH_KEYWORDS
};

static PyObject*
JsProxy_as_py_json(PyObject* self, PyObject* _unused)
{
  int flags = JsProxy_getflags(self);
  if (flags & (IS_ARRAY | IS_ARRAY_LIKE)) {
    flags |= IS_PY_JSON_SEQUENCE;
  } else {
    flags |= IS_PY_JSON_DICT;
  }
  return JsProxy_create_with_type(
    flags, JsProxy_VAL(self), JsMethod_THIS(self), NULL);
}

static PyMethodDef JsProxy_as_py_json_MethodDef = {
  "as_py_json",
  (PyCFunction)JsProxy_as_py_json,
  METH_NOARGS
};

EM_JS_VAL(JsVal, JsObjMap_GetIter_js, (JsVal obj), {
  return Module.iterObject(obj);
})

static PyObject*
JsObjMap_GetIter(PyObject* self)
{
  JsVal iter = JsObjMap_GetIter_js(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(iter);
  return js2python(iter);
finally:
  return NULL;
}

EM_JS_NUM(int, JsObjMap_length_js, (JsVal obj), {
  let length = 0;
  for (let _ of Module.iterObject(obj)) {
    length++;
  }
  return length;
})

static int
JsObjMap_length(PyObject* self)
{
  return JsObjMap_length_js(JsProxy_VAL(self));
}

// A helper method for JsObjMap_subscript.
EM_JS_VAL(JsVal, JsObjMap_subscript_js, (JsVal obj, JsVal key), {
  if (!Object.prototype.hasOwnProperty.call(obj, key)) {
    return Module.error;
  }
  return obj[key];
});

static PyObject*
JsObjMap_subscript(PyObject* self, PyObject* pyidx)
{
  if (!PyUnicode_Check(pyidx)) {
    PyErr_SetObject(PyExc_KeyError, pyidx);
    return NULL;
  }

  PyObject* pyresult = NULL;

  JsVal key = python2js(pyidx);
  FAIL_IF_JS_ERROR(key);
  JsVal result = JsObjMap_subscript_js(JsProxy_VAL(self), key);
  if (JsvError_Check(result)) {
    if (!PyErr_Occurred()) {
      PyErr_SetObject(PyExc_KeyError, pyidx);
    }
    FAIL();
  }
  pyresult = js2python_immutable(result);
  if (pyresult == NULL) {
    pyresult = JsProxy_create_objmap(result, JsProxy_get_objmap_flags(self));
  }

finally:
  return pyresult;
}

// A helper method for JsObjMap_ass_subscript.
// clang-format off
EM_JS_NUM(int,
JsObjMap_ass_subscript_js,
(JsVal obj, JsVal key, JsVal value),
{
  if(value === Module.error) {
    if (!Object.prototype.hasOwnProperty.call(obj, key)) {
      return -1;
    }
    delete obj[key];
  } else {
    obj[key] = value;
  }
  return 0;
});
// clang-format on

static int
JsObjMap_ass_subscript(PyObject* self, PyObject* pykey, PyObject* pyvalue)
{
  if (!PyUnicode_Check(pykey)) {
    if (pyvalue) {
      PyErr_SetString(
        PyExc_TypeError,
        "Can only assign keys of type string to JavaScript object map");
    } else {
      PyErr_SetObject(PyExc_KeyError, pykey);
    }
    return -1;
  }

  bool success = false;
  JsVal value = JS_ERROR;
  JsVal key = python2js(pykey);
  if (pyvalue != NULL) {
    value = python2js(pyvalue);
    FAIL_IF_JS_ERROR(value);
  }
  int status = JsObjMap_ass_subscript_js(JsProxy_VAL(self), key, value);
  if (status == -1) {
    if (!PyErr_Occurred()) {
      PyErr_SetObject(PyExc_KeyError, pykey);
    }
    FAIL();
  }
  success = true;
finally:
  return success ? 0 : -1;
}

EM_JS_NUM(int, JsObjMap_contains_js, (JsVal obj, JsVal key), {
  return Object.prototype.hasOwnProperty.call(obj, key);
});

static int
JsObjMap_contains(PyObject* self, PyObject* obj)
{
  if (!PyUnicode_Check(obj)) {
    // All keys are strings or symbols so if it's not a string don't check.
    // TODO: maybe support symbols??
    return 0;
  }
  JsVal jsobj = python2js(obj);
  FAIL_IF_JS_ERROR(jsobj);
  return JsObjMap_contains_js(JsProxy_VAL(self), jsobj);

finally:
  return -1;
}

// clang-format off
static PyNumberMethods JsProxy_NumberMethods = {
  .nb_bool = JsProxy_Bool
};
// clang-format on

static PyGetSetDef JsProxy_GetSet[] = { { "typeof", .get = JsProxy_typeof },
                                        { "js_id", .get = JsProxy_js_id },
                                        { NULL } };

static PyTypeObject JsProxyType = {
  .tp_name = "pyodide.ffi.JsProxy",
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
JsProxy_cinit(PyObject* obj, JsVal val, PyObject* sig)
{
  JsProxy* self = (JsProxy*)obj;
  self->js = hiwire_new_deduplicate(val);
  self->signature = Py_XNewRef(sig);
#ifdef DEBUG_F
  extern bool tracerefs;
  if (tracerefs) {
    printf("JsProxy cinit: %zd, object: %zd\n", (long)obj, (long)self->js);
  }
#endif
  return 0;
}

EM_JS_VAL(JsVal, JsModule_GetAll_js, (JsVal o), {
  return Object.getOwnPropertyNames(o);
});

// This is used by `from x import *` to look up the attributes of the Js module.
// Three possibilities:
//  - Set exception and return -1 to raise an exception
//  - Return 0 and do not set *all when it wasn't a JS object to allow the
//    normal "from x import *" logic to proceed
//  - Return 0 and set *all when it is a JsProxy and we successfully find the
//    attributes.
//
// See: cpython/patches/0009-Make-from-x-import-aware-of-jsproxy-modules.patch
int
JsModule_GetAll(PyObject* self, PyObject** all)
{
  if (!JsProxy_Check(self)) {
    return 0;
  }
  PyObject* pyresult;
  int success = -1;

  JsVal jsresult = JsModule_GetAll_js(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(jsresult);
  pyresult = js2python(jsresult);
  FAIL_IF_NULL(pyresult);
  *all = pyresult;

  success = 0;
finally:
  return success;
}

////////////////////////////////////////////////////////////
// JsMethod
//
// A subclass of JsProxy for methods

/**
 * __call__ overload for methods. Controlled by IS_CALLABLE.
 */
static PyObject*
JsMethod_Vectorcall(PyObject* self,
                    PyObject* const* pyargs,
                    size_t nargsf,
                    PyObject* kwnames)
{
  return JsMethod_Vectorcall_impl(JsProxy_VAL(self),
                                  JsMethod_THIS(self),
                                  JsProxy_SIG(self),
                                  pyargs,
                                  nargsf,
                                  kwnames);
}

/**
 * jsproxy.new implementation. Controlled by IS_CALLABLE.
 *
 * This does Reflect.construct(this, args). In other words, this treats the
 * JsMethod as a JavaScript class, constructs a new JavaScript object of that
 * class and returns a new JsProxy wrapping it. Similar to `new this(args)`.
 */
static PyObject*
JsMethod_Construct(PyObject* self,
                   PyObject* const* pyargs,
                   Py_ssize_t nargs,
                   PyObject* kwnames)
{
  return JsMethod_Construct_impl(
    JsProxy_VAL(self), JsProxy_SIG(self), pyargs, nargs, kwnames);
}

// clang-format off
static PyMethodDef JsMethod_Construct_MethodDef = {
  "new",
  (PyCFunction)JsMethod_Construct,
  METH_FASTCALL | METH_KEYWORDS
};
// clang-format on

static PyObject*
JsMethod_descr_get(PyObject* self, PyObject* obj, PyObject* type)
{
  PyObject* result = NULL;

  if (Py_IsNone(obj) || obj == NULL) {
    Py_INCREF(self);
    return self;
  }

  JsVal jsobj = python2js(obj);
  FAIL_IF_JS_ERROR(jsobj);
  result = JsProxy_create_with_this(JsProxy_VAL(self), jsobj, NULL, false);

finally:
  return result;
}

static int
JsMethod_cinit(PyObject* self, JsVal this_)
{
  JsMethod_THIS_REF(self) = JsRef_new(this_);
  JsMethod_VECTORCALL(self) = JsMethod_Vectorcall;
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

static void
Buffer_dealloc(PyObject* self)
{
  PyMem_Free(((Buffer*)self)->data);
  ((Buffer*)self)->data = NULL;
}

static int
Buffer_GetBuffer(PyObject* obj, Py_buffer* view, int flags)
{
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

  return 0;
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
 * This is a helper function to do error checking for JsBuffer_assign_to
 * and JsBuffer_assign.
 *
 * self -- The JavaScript buffer involved
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
  int byteLength = JsBuffer_BYTE_LENGTH(self);
  char* format = JsBuffer_FORMAT(self);
  Py_ssize_t itemsize = JsBuffer_ITEMSIZE(self);
  if (view.len != byteLength) {
    if (dir) {
      PyErr_Format(
        PyExc_ValueError,
        "cannot assign from TypedArray of length %d to buffer of length %d",
        byteLength,
        view.len);
    } else {
      PyErr_Format(
        PyExc_ValueError,
        "cannot assign to TypedArray of length %d from buffer of length %d",
        view.len,
        byteLength);
    }
    return -1;
  }
  if (safe) {
    bool compatible;
    if (view.format && format) {
      compatible = strcmp(view.format, format) != 0;
    } else {
      compatible = view.itemsize == itemsize;
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
 * buffer -- A PyObject which supports the buffer protocol and is writable.
 */
static PyObject*
JsBuffer_assign_to(PyObject* obj, PyObject* target)
{
  JsProxy* self = (JsProxy*)obj;
  bool success = false;
  Py_buffer view = { 0 };

  FAIL_IF_MINUS_ONE(
    PyObject_GetBuffer(target, &view, PyBUF_ANY_CONTIGUOUS | PyBUF_WRITABLE));
  bool safe = JsBuffer_CHECK_ASSIGNMENTS(self);
  bool dir = true;
  FAIL_IF_MINUS_ONE(check_buffer_compatibility(self, view, safe, dir));
  FAIL_IF_MINUS_ONE(JsvBuffer_assignToPtr(JsProxy_VAL(self), view.buf));

  success = true;
finally:
  PyBuffer_Release(&view);
  if (success) {
    Py_RETURN_NONE;
  }
  return NULL;
}

static PyMethodDef JsBuffer_assign_to_MethodDef = {
  "assign_to",
  (PyCFunction)JsBuffer_assign_to,
  METH_O,
};

/**
 * Assign from a py buffer to a js buffer
 * obj -- A JsBuffer (meaning a PyProxy of an ArrayBuffer or an ArrayBufferView)
 * buffer -- A PyObject which supports the buffer protocol (can be read only)
 */
static PyObject*
JsBuffer_assign(PyObject* obj, PyObject* source)
{
  JsProxy* self = (JsProxy*)obj;
  bool success = false;
  Py_buffer view = { 0 };

  FAIL_IF_MINUS_ONE(PyObject_GetBuffer(source, &view, PyBUF_ANY_CONTIGUOUS));
  bool safe = JsBuffer_CHECK_ASSIGNMENTS(self);
  bool dir = false;
  FAIL_IF_MINUS_ONE(check_buffer_compatibility(self, view, safe, dir));
  FAIL_IF_MINUS_ONE(JsvBuffer_assignFromPtr(JsProxy_VAL(self), view.buf));

  success = true;
finally:
  PyBuffer_Release(&view);
  if (success) {
    Py_RETURN_NONE;
  }
  return NULL;
}

static PyMethodDef JsBuffer_assign_MethodDef = {
  "assign",
  (PyCFunction)JsBuffer_assign,
  METH_O,
};

/**
 * Used from js2python for to_py and by to_memoryview. Make a new Python buffer
 * with the same data as jsbuffer.
 *
 * All other arguments are calculated from jsbuffer, but it's more convenient to
 * calculate them in JavaScript and pass them as arguments than to acquire them
 * from C.
 *
 * jsbuffer - An ArrayBuffer view or an ArrayBuffer
 * byteLength - the byteLength of jsbuffer
 * format - the appropriate format for jsbuffer, from get_buffer_datatype
 * itemsize - the appropriate itemsize for jsbuffer, from get_buffer_datatype
 */
// Used in js2python, intentionally not static
EMSCRIPTEN_KEEPALIVE PyObject*
JsBuffer_CopyIntoMemoryView(JsVal jsbuffer,
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
  FAIL_IF_MINUS_ONE(JsvBuffer_assignToPtr(jsbuffer, buffer->data));
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

/**
 * Used by to_bytes. Make a new bytes object and copy the data from the
 * ArrayBuffer into it.
 */
static PyObject*
JsBuffer_CopyIntoBytes(JsVal jsbuffer, Py_ssize_t byteLength)
{
  bool success = false;

  PyObject* result = PyBytes_FromStringAndSize(NULL, byteLength);
  FAIL_IF_NULL(result);
  char* data = PyBytes_AS_STRING(result);
  FAIL_IF_MINUS_ONE(JsvBuffer_assignToPtr(jsbuffer, data));
  success = true;
finally:
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

/**
 * Used by JsBuffer_ToString. Decode the ArrayBuffer into a Javascript string
 * using a TextDecoder with the given encoding. I have found no evidence that
 * the encoding argument ever matters...
 *
 * If a decoding error occurs, return 0 without setting error flag so we can
 * replace with a UnicodeDecodeError
 */
// clang-format off
EM_JS_VAL(JsVal,
JsBuffer_DecodeString_js,
(JsVal buffer, char* encoding),
{
  let encoding_js;
  if (encoding) {
    encoding_js = UTF8ToString(encoding);
  }
  const decoder = new TextDecoder(encoding_js, { fatal: true, ignoreBOM: true });
  let res;
  try {
    res = decoder.decode(buffer);
  } catch (e) {
    if (e instanceof TypeError) {
      // Decoding error
      return Module.error;
    }
    throw e;
  }
  return res;
})
// clang-format on

/**
 * Decode the ArrayBuffer into a PyUnicode object.
 */
static PyObject*
JsBuffer_ToString(JsVal jsbuffer, char* encoding)
{
  PyObject* result = NULL;

  JsVal jsresult = JsBuffer_DecodeString_js(jsbuffer, encoding);
  if (JsvError_Check(jsresult) && !PyErr_Occurred()) {
    PyErr_Format(PyExc_ValueError,
                 "Failed to decode Javascript TypedArray as %s",
                 encoding ? encoding : "utf8");
  }
  FAIL_IF_JS_ERROR(jsresult);
  result = js2python(jsresult);
  FAIL_IF_NULL(result);

finally:
  return result;
}

static PyObject*
JsBuffer_tomemoryview(PyObject* self, PyObject* _ignored)
{
  return JsBuffer_CopyIntoMemoryView(JsProxy_VAL(self),
                                     JsBuffer_BYTE_LENGTH(self),
                                     JsBuffer_FORMAT(self),
                                     JsBuffer_ITEMSIZE(self));
}

static PyMethodDef JsBuffer_tomemoryview_MethodDef = {
  "to_memoryview",
  (PyCFunction)JsBuffer_tomemoryview,
  METH_NOARGS,
};

static PyObject*
JsBuffer_tobytes(PyObject* self, PyObject* _ignored)
{
  return JsBuffer_CopyIntoBytes(JsProxy_VAL(self), JsBuffer_BYTE_LENGTH(self));
}

static PyMethodDef JsBuffer_tobytes_MethodDef = {
  "to_bytes",
  (PyCFunction)JsBuffer_tobytes,
  METH_NOARGS,
};

static long
get_fileno(PyObject* file)
{
  PyObject* pyfileno = _PyObject_CallMethodIdNoArgs(file, &PyId_fileno);
  if (pyfileno == NULL) {
    return -1;
  }
  return PyLong_AsLong(pyfileno);
}

static PyObject*
JsBuffer_write_to_file(PyObject* self, PyObject* file)
{
  int fd = get_fileno(file);
  FAIL_IF_MINUS_ONE(fd);
  FAIL_IF_MINUS_ONE(JsvBuffer_writeToFile(JsProxy_VAL(self), fd));
  Py_RETURN_NONE;
finally:
  return NULL;
}

static PyMethodDef JsBuffer_write_to_file_MethodDef = {
  "to_file",
  (PyCFunction)JsBuffer_write_to_file,
  METH_O,
};

static PyObject*
JsBuffer_read_from_file(PyObject* jsbuffer, PyObject* file)
{
  int fd = get_fileno(file);
  FAIL_IF_MINUS_ONE(fd);
  FAIL_IF_MINUS_ONE(JsvBuffer_readFromFile(JsProxy_VAL(jsbuffer), fd));
  Py_RETURN_NONE;
finally:
  return NULL;
}

static PyMethodDef JsBuffer_read_from_file_MethodDef = {
  "from_file",
  (PyCFunction)JsBuffer_read_from_file,
  METH_O,
};

static PyObject*
JsBuffer_into_file(PyObject* jsbuffer, PyObject* file)
{
  int fd = get_fileno(file);
  FAIL_IF_MINUS_ONE(fd);
  FAIL_IF_MINUS_ONE(JsvBuffer_intoFile(JsProxy_VAL(jsbuffer), fd));
  Py_RETURN_NONE;
finally:
  return NULL;
}

static PyMethodDef JsBuffer_into_file_MethodDef = {
  "_into_file",
  (PyCFunction)JsBuffer_into_file,
  METH_O,
};

static PyObject*
JsBuffer_tostring(PyObject* self,
                  PyObject* const* args,
                  Py_ssize_t nargs,
                  PyObject* kwnames)
{
  static const char* const _keywords[] = { "encoding", 0 };
  static struct _PyArg_Parser _parser = {
    .format = "|s:to_string",
    .keywords = _keywords,
  };
  char* encoding = NULL;
  if (!_PyArg_ParseStackAndKeywords(
        args, nargs, kwnames, &_parser, &encoding)) {
    return NULL;
  }
  return JsBuffer_ToString(JsProxy_VAL(self), encoding);
}

static PyMethodDef JsBuffer_tostring_MethodDef = {
  "to_string",
  (PyCFunction)JsBuffer_tostring,
  METH_FASTCALL | METH_KEYWORDS,
};

// clang-format off
EM_JS_UNCHECKED(void,
JsBuffer_get_info, (JsVal jsobj,
                    Py_ssize_t* byteLength_ptr,
                    char** format_ptr,
                    Py_ssize_t* size_ptr,
                    bool* checked_ptr),
{
  const [format_utf8, size, checked] = Module.get_buffer_datatype(jsobj);
  DEREF_U32(byteLength_ptr, 0) = jsobj.byteLength;
  DEREF_U32(format_ptr, 0) = format_utf8;
  DEREF_U32(size_ptr, 0) = size;
  DEREF_U8(checked_ptr, 0) = checked;
});
// clang-format on

int
JsBuffer_cinit(PyObject* self)
{
  bool success = false;
  // TODO: should logic here be any different if we're on wasm heap?
  // format string is borrowed from get_buffer_datatype, DO NOT DEALLOCATE!
  JsBuffer_get_info(JsProxy_VAL(self),
                    &JsBuffer_BYTE_LENGTH(self),
                    &JsBuffer_FORMAT(self),
                    &JsBuffer_ITEMSIZE(self),
                    &JsBuffer_CHECK_ASSIGNMENTS(self));
  if (JsBuffer_FORMAT(self) == NULL) {
    char* typename = Jsv_constructorName(JsProxy_VAL(self));
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

EM_JS_REF(PyObject*, JsDoubleProxy_unwrap_js, (JsVal id), {
  return Module.PyProxy_getPtr(id);
});

static PyObject*
JsDoubleProxy_unwrap(PyObject* obj, PyObject* _ignored)
{
  PyObject* result = JsDoubleProxy_unwrap_js(JsProxy_VAL(obj));
  Py_XINCREF(result);
  return result;
}

static PyMethodDef JsDoubleProxy_unwrap_MethodDef = {
  "unwrap",
  (PyCFunction)JsDoubleProxy_unwrap,
  METH_NOARGS,
};

EM_JS_VAL(JsVal, JsProxy_to_weakref_js, (JsVal pyproxy), {
  return new WeakRef(pyproxy);
});

static PyObject*
JsProxy_to_weakref(PyObject* self, PyObject* _ignored)
{
  JsVal jsresult = JsProxy_to_weakref_js(JsProxy_VAL(self));
  FAIL_IF_JS_ERROR(jsresult);
  return js2python(jsresult);
finally:
  return NULL;
}

static PyMethodDef JsProxy_to_weakref_MethodDef = {
  "to_weakref",
  (PyCFunction)JsProxy_to_weakref,
  METH_NOARGS,
};

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
  PyMethodDef methods[50];
  int cur_method = 0;
  PyMemberDef members[5];
  int cur_member = 0;
  PyGetSetDef getsets[5];
  int cur_getset = 0;

  methods[cur_method++] = JsProxy_bind_sig_MethodDef;
  methods[cur_method++] = JsProxy_bind_class_MethodDef;
  methods[cur_method++] = JsProxy_Dir_MethodDef;
  methods[cur_method++] = JsProxy_toPy_MethodDef;
  methods[cur_method++] = JsProxy_object_entries_MethodDef;
  methods[cur_method++] = JsProxy_object_keys_MethodDef;
  methods[cur_method++] = JsProxy_object_values_MethodDef;
  methods[cur_method++] = JsProxy_to_weakref_MethodDef;
  members[cur_member++] = (PyMemberDef){
    .name = "_sig",
    .type = T_OBJECT,
    .flags = READONLY,
    .offset = offsetof(JsProxy, signature),
  };

  int tp_flags = Py_TPFLAGS_DEFAULT;

  bool objmap = (flags & (IS_OBJECT_MAP | IS_PY_JSON_DICT));
  int mapping_flags = HAS_GET | HAS_LENGTH | IS_ITERABLE;
  bool mapping = (flags & mapping_flags) == mapping_flags;
  bool mutable_mapping = mapping && (flags & HAS_SET);
  char* type_name = "pyodide.ffi.JsProxy";
  int basicsize = sizeof(JsProxy);
  mapping = mapping || objmap;
  mutable_mapping = mutable_mapping || objmap;

  if (mapping) {
    methods[cur_method++] = JsMap_keys_MethodDef;
    methods[cur_method++] = JsMap_values_MethodDef;
    methods[cur_method++] = JsMap_items_MethodDef;
    methods[cur_method++] = JsMap_get_MethodDef;
  }
  if (mutable_mapping) {
    methods[cur_method++] = JsMap_pop_MethodDef;
    methods[cur_method++] = JsMap_popitem_MethodDef;
    methods[cur_method++] = JsMap_clear_MethodDef;
    methods[cur_method++] = JsMap_update_MethodDef;
    methods[cur_method++] = JsMap_setdefault_MethodDef;
  }

  if (objmap) {
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_iter, .pfunc = (void*)JsObjMap_GetIter };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_mp_length, .pfunc = (void*)JsObjMap_length };
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_mp_subscript,
                                       .pfunc = (void*)JsObjMap_subscript };
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_mp_ass_subscript,
                                       .pfunc = (void*)JsObjMap_ass_subscript };
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_sq_contains,
                                       .pfunc = (void*)JsObjMap_contains };
    goto skip_container_slots;
  }

  if ((flags & IS_ITERABLE) && !(flags & IS_ITERATOR)) {
    // If it is an iterator we should use SelfIter instead.
    if (mapping) {
      // Prefer `obj.keys()` over `obj[Symbol.iterator]()`
      slots[cur_slot++] =
        (PyType_Slot){ .slot = Py_tp_iter, .pfunc = (void*)JsMap_GetIter };
    } else {
      // Uses `obj[Symbol.iterator]()`
      slots[cur_slot++] =
        (PyType_Slot){ .slot = Py_tp_iter, .pfunc = (void*)JsProxy_GetIter };
    }
  }
  if ((flags & IS_ASYNC_ITERABLE) && !(flags & IS_ASYNC_ITERATOR)) {
    // This uses `obj[Symbol.asyncIterator]()`
    // If it is an iterator we should use SelfIter instead.
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_am_aiter,
                                       .pfunc = (void*)JsProxy_GetAsyncIter };
  }

  // If it's an iterator, we aren't sure whether it is an async iterator or a
  // sync iterator -- they both define a next method, you have to see whether
  // the result is  a promise or not to learn whether we are async. But most
  // iterators also define `Symbol.iterator` to return themself, and most async
  // iterators define `Symbol.asyncIterator` to return themself. So if one of
  // these is defined but not the other, we use this to decide what type we are.

  // Iterator methods
  if (flags & IS_ITERATOR) {
    // We're not sure whether it is an async iterator or a sync iterator. So add
    // both methods and raise at runtime if someone uses the wrong one.
    // JsProxy_GetIter would work just as well as PyObject_SelfIter
    // but PyObject_SelfIter avoids an unnecessary allocation.
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_iter, .pfunc = (void*)PyObject_SelfIter };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_iternext, .pfunc = (void*)JsProxy_IterNext };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_am_send, .pfunc = (void*)JsProxy_am_send };
    methods[cur_method++] = JsGenerator_send_MethodDef;
  }

  // Async iterator methods
  if (flags & IS_ASYNC_ITERATOR) {
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_am_aiter, .pfunc = (void*)PyObject_SelfIter };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_am_anext, .pfunc = (void*)JsGenerator_anext };
    // Send works okay on any js object that has a "next" method
    methods[cur_method++] = JsGenerator_asend_MethodDef;
  }
  if (flags & IS_GENERATOR) {
    // throw and close need "throw" and "return" methods to work. We currently
    // don't trust that an object with "next", "throw", and "return" is a
    // generator though -- we require that it actually have it's toStringTag set
    // to Generator.
    methods[cur_method++] = JsGenerator_throw_MethodDef;
    methods[cur_method++] = JsGenerator_close_MethodDef;
  }

  if (flags & IS_ASYNC_GENERATOR) {
    // throw and close need "throw" and "return" methods to work. We currently
    // don't trust that an object with "next", "throw", and "return" is a
    // generator though -- we require that it actually have it's toStringTag set
    // to Generator.
    methods[cur_method++] = JsGenerator_athrow_MethodDef;
    methods[cur_method++] = JsGenerator_aclose_MethodDef;
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
    tp_flags |= Py_TPFLAGS_MAPPING;
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
skip_container_slots:

  if (flags & IS_AWAITABLE) {
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_am_await, .pfunc = (void*)JsProxy_Await };
    methods[cur_method++] = JsProxy_then_MethodDef;
    methods[cur_method++] = JsProxy_catch_MethodDef;
    methods[cur_method++] = JsProxy_finally_MethodDef;
  }
  if (flags & IS_CALLABLE) {
    tp_flags |= Py_TPFLAGS_HAVE_VECTORCALL;
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_call, .pfunc = (void*)PyVectorcall_Call };
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_tp_descr_get,
                                       .pfunc = (void*)JsMethod_descr_get };
    // We could test separately for whether a function is constructable,
    // but it generates a lot of false positives.
    methods[cur_method++] = JsMethod_Construct_MethodDef;
    members[cur_member++] = (PyMemberDef){
      .name = "__vectorcalloffset__",
      .type = T_PYSSIZET,
      .flags = READONLY,
      .offset =
        offsetof(JsProxy, tf) + offsetof(struct MethodFields, vectorcall),
    };
  }
  if (flags & IS_ARRAY) {
    // If the object is an array (or an array like), then we want
    // subscripting `proxy[idx]` to go to `jsobj[idx]` instead of
    // `jsobj.get(idx)`. Hopefully anyone else who defines a custom array object
    // will subclass Array.
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_mp_subscript,
                                       .pfunc = (void*)JsArray_subscript };
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_mp_ass_subscript,
                                       .pfunc = (void*)JsArray_ass_subscript };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_inplace_concat,
                     .pfunc = (void*)JsArray_sq_inplace_concat };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_concat, .pfunc = (void*)JsArray_sq_concat };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_repeat, .pfunc = (void*)JsArray_sq_repeat };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_inplace_repeat,
                     .pfunc = (void*)JsArray_sq_inplace_repeat };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_length, .pfunc = (void*)JsProxy_length };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_item, .pfunc = (void*)JsArray_sq_item };
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_sq_ass_item,
                                       .pfunc = (void*)JsArray_sq_ass_item };
    methods[cur_method++] = JsArray_extend_MethodDef;
    methods[cur_method++] = JsArray_pop_MethodDef;
    methods[cur_method++] = JsArray_append_MethodDef;

    methods[cur_method++] = JsArray_index_MethodDef;
    methods[cur_method++] = JsArray_count_MethodDef;
    methods[cur_method++] = JsArray_reversed_MethodDef;
    methods[cur_method++] = JsArray_reverse_MethodDef;
    methods[cur_method++] = JsArray_insert_MethodDef;
    methods[cur_method++] = JsArray_remove_MethodDef;
  }
  if (flags & IS_TYPEDARRAY) {
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_mp_subscript,
                                       .pfunc = (void*)JsTypedArray_subscript };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_mp_ass_subscript,
                     .pfunc = (void*)JsTypedArray_ass_subscript };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_item, .pfunc = (void*)JsProxy_item_array };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_length, .pfunc = (void*)JsProxy_length };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_item, .pfunc = (void*)JsArray_sq_item };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_ass_item,
                     .pfunc = (void*)JsTypedArray_sq_ass_item };
    methods[cur_method++] = JsArray_index_MethodDef;
    methods[cur_method++] = JsArray_count_MethodDef;
    methods[cur_method++] = JsArray_reversed_MethodDef;
    methods[cur_method++] = JsArray_reverse_MethodDef;
  }
  if (flags & IS_ARRAY_LIKE) {
    slots[cur_slot++] = (PyType_Slot){ .slot = Py_mp_subscript,
                                       .pfunc = (void*)JsArrayLike_subscript };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_length, .pfunc = (void*)JsProxy_length };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_item, .pfunc = (void*)JsArray_sq_item };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_sq_concat, .pfunc = (void*)JsArray_sq_concat };
    methods[cur_method++] = JsArray_reversed_MethodDef;
  }
  if (flags & IS_BUFFER) {
    methods[cur_method++] = JsBuffer_assign_MethodDef;
    methods[cur_method++] = JsBuffer_assign_to_MethodDef;
    methods[cur_method++] = JsBuffer_tomemoryview_MethodDef;
    methods[cur_method++] = JsBuffer_tobytes_MethodDef;
    methods[cur_method++] = JsBuffer_tostring_MethodDef;
    methods[cur_method++] = JsBuffer_write_to_file_MethodDef;
    methods[cur_method++] = JsBuffer_read_from_file_MethodDef;
    methods[cur_method++] = JsBuffer_into_file_MethodDef;
  }
  if (flags & IS_DOUBLE_PROXY) {
    methods[cur_method++] = JsDoubleProxy_unwrap_MethodDef;
  }
  if (INCLUDE_OBJMAP_METHODS(flags)) {
    methods[cur_method++] = JsProxy_as_object_map_MethodDef;
    methods[cur_method++] = JsProxy_as_py_json_MethodDef;
  }
  if (flags & (IS_ARRAY | IS_ARRAY_LIKE)) {
    methods[cur_method++] = JsProxy_as_py_json_MethodDef;
  }
  if (flags & IS_ERROR) {
    type_name = "pyodide.ffi.JsException";
    methods[cur_method++] = JsException_reduce_MethodDef;
    getsets[cur_getset++] = (PyGetSetDef){
      .name = "js_error",
      .get = JsException_js_error_getter,
    };
    tp_flags |= Py_TPFLAGS_HAVE_GC;
    tp_flags |= Py_TPFLAGS_BASE_EXC_SUBCLASS;
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_traverse,
                     .pfunc =
                       (void*)((PyTypeObject*)PyExc_Exception)->tp_traverse };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_new, .pfunc = JsException_new };
    slots[cur_slot++] =
      (PyType_Slot){ .slot = Py_tp_init, .pfunc = JsException_init };
  }

  methods[cur_method++] = (PyMethodDef){ 0 };
  members[cur_member++] = (PyMemberDef){ 0 };
  getsets[cur_getset++] = (PyGetSetDef){ 0 };

  bool success = false;
  void* mem = NULL;
  PyObject* bases = NULL;
  PyObject* flags_obj = NULL;
  PyObject* result = NULL;

  // PyType_FromSpecWithBases copies "members" automatically into the end of the
  // type. It doesn't store the slots. But it just copies the pointer to
  // "methods" and "getsets" into the PyTypeObject, so if we give it stack
  // allocated methods or getsets there will be trouble. Instead, heap allocate
  // some memory and copy them over.
  //
  // If the type object were later deallocated, we would leak this memory. It's
  // unclear how to fix that, but we store the type in JsProxy_TypeDict forever
  // anyway so it will never be deallocated.
  mem = PyMem_Malloc(sizeof(PyMethodDef) * cur_method +
                     sizeof(PyGetSetDef) * cur_getset);
  PyMethodDef* methods_heap = (PyMethodDef*)mem;
  PyGetSetDef* getsets_heap = (PyGetSetDef*)(methods_heap + cur_method);
  if (methods_heap == NULL) {
    PyErr_NoMemory();
    FAIL();
  }
  memcpy(methods_heap, methods, sizeof(PyMethodDef) * cur_method);
  memcpy(getsets_heap, getsets, sizeof(PyGetSetDef) * cur_getset);

  slots[cur_slot++] =
    (PyType_Slot){ .slot = Py_tp_members, .pfunc = (void*)members };
  slots[cur_slot++] =
    (PyType_Slot){ .slot = Py_tp_methods, .pfunc = (void*)methods_heap };
  slots[cur_slot++] =
    (PyType_Slot){ .slot = Py_tp_getset, .pfunc = (void*)getsets_heap };
  slots[cur_slot++] = (PyType_Slot){ 0 };

  // clang-format off
  PyType_Spec spec = {
    .name = type_name,
    .basicsize = basicsize,
    .itemsize = 0,
    .flags = tp_flags,
    .slots = slots,
  };
  // clang-format on
  if (flags & IS_ERROR) {
    bases = PyTuple_Pack(2, &JsProxyType, PyExc_Exception);
    FAIL_IF_NULL(bases);
    // The multiple inheritance we are doing is not recognized as legal by
    // Python:
    //
    // 1. the solid_base of JsProxy is JsProxy.
    // 2. the solid_base of Exception is BaseException.
    // 3. Neither issubclass(JsProxy, BaseException) nor
    //    issubclass(BaseException, JsProxy).
    // 4. If you use multiple inheritance, the sold_bases of the different bases
    //    are required to be totally ordered (otherwise Python assumes there is
    //    a memory layout clash).
    //
    // So Python concludes that there is a memory layout clash. However, we have
    // carefully ensured that the memory layout is okay (with the
    // _Static_assert's at the top of this file) so now we need to trick the
    // subclass creation algorithm.
    //
    // We temporarily set the mro of JsProxy to be (BaseException,) so that
    // issubclass(JsProxy, BaseException) returns True. This convinces
    // PyType_FromSpecWithBases that everything is okay. Once we have created
    // the type, we restore the mro.
    PyObject* save_mro = JsProxyType.tp_mro;
    JsProxyType.tp_mro = PyTuple_Pack(1, PyExc_BaseException);
    result = PyType_FromSpecWithBases(&spec, bases);
    Py_CLEAR(JsProxyType.tp_mro);
    JsProxyType.tp_mro = save_mro;
  } else {
    bases = PyTuple_Pack(1, &JsProxyType);
    FAIL_IF_NULL(bases);
    result = PyType_FromSpecWithBases(&spec, bases);
  }
  FAIL_IF_NULL(result);
  PyObject* abc = NULL;
  if (flags & (IS_ARRAY | IS_TYPEDARRAY)) {
    abc = MutableSequence;
  } else if (flags & IS_ARRAY_LIKE) {
    abc = Sequence;
  } else if (mutable_mapping) {
    abc = MutableMapping;
  } else if (mapping) {
    abc = Mapping;
  } else if (flags & IS_OBJECT_MAP) {
    abc = MutableMapping;
  }
  if (abc) {
    PyObject* register_result =
      _PyObject_CallMethodIdOneArg(abc, &PyId_register, result);
    abc = NULL; // abc is borrowed, don't decref
    FAIL_IF_NULL(register_result);
    Py_CLEAR(register_result);
  }

  Py_SET_TYPE(result, (PyTypeObject*)JsProxy_metaclass);
  flags_obj = PyLong_FromLong(flags);
  FAIL_IF_NULL(flags_obj);
  FAIL_IF_MINUS_ONE(PyObject_SetAttr(
    result, _PyUnicode_FromId(&PyId__js_type_flags), flags_obj));

  success = true;
finally:
  Py_CLEAR(bases);
  Py_CLEAR(flags_obj);
  if (!success && mem != NULL) {
    PyMem_Free(mem);
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

#define SET_FLAG_IF(flag, cond)                                                \
  if (cond) {                                                                  \
    type_flags |= flag;                                                        \
  }

#define SET_FLAG_IF_HAS_METHOD(flag, meth)                                     \
  SET_FLAG_IF(flag, hasMethod(obj, meth))

// clang-format off
EM_JS_NUM(int, JsProxy_compute_typeflags, (JsVal obj, bool is_py_json), {
  let type_flags = 0;
  if (API.isPyProxy(obj) && !pyproxyIsAlive(obj)) {
    return 0;
  }

  // test_jsproxy.test_revoked_proxy stress tests this code.
  // Every single operation on a revoked proxy raises an error!

  const typeTag = getTypeTag(obj);

  function safeBool(cb) {
    try {
      return cb();
    } catch (e) {
      return false;
    }
  }
  const isBufferView = safeBool(() => ArrayBuffer.isView(obj));
  const isArray = safeBool(() => Array.isArray(obj));
  const constructorName = safeBool(() => obj.constructor.name) || "";
  const hasLength =
    isArray || (hasProperty(obj, "length") && typeof obj !== "function");

  // If we somehow set more than one of IS_CALLABLE, IS_BUFFER, and IS_ERROR,
  // we'll run into trouble. I think that for this to happen, someone would have
  // to pass in some weird and maliciously constructed object. Anyways for
  // maximum safety, we double check that only one of these is set.
  SET_FLAG_IF(IS_CALLABLE, typeof obj === "function");
  SET_FLAG_IF_HAS_METHOD(IS_AWAITABLE, "then");
  SET_FLAG_IF_HAS_METHOD(IS_ITERABLE, Symbol.iterator);
  SET_FLAG_IF_HAS_METHOD(IS_ASYNC_ITERABLE, Symbol.asyncIterator);
  SET_FLAG_IF(
    IS_ITERATOR,
    hasMethod(obj, "next") &&
      (hasMethod(obj, Symbol.iterator) || !hasMethod(obj, Symbol.asyncIterator))
  );
  SET_FLAG_IF(
    IS_ASYNC_ITERATOR,
    hasMethod(obj, "next") &&
      (!hasMethod(obj, Symbol.iterator) || hasMethod(obj, Symbol.asyncIterator))
  );
  SET_FLAG_IF(HAS_LENGTH, hasLength || hasProperty(obj, "size"));
  SET_FLAG_IF_HAS_METHOD(HAS_GET, "get");
  SET_FLAG_IF_HAS_METHOD(HAS_SET, "set");
  SET_FLAG_IF_HAS_METHOD(HAS_HAS, "has");
  SET_FLAG_IF_HAS_METHOD(HAS_INCLUDES, "includes");
  SET_FLAG_IF(
    IS_BUFFER,
    (isBufferView || typeTag === "[object ArrayBuffer]") &&
      !(type_flags & IS_CALLABLE)
  );
  SET_FLAG_IF(IS_DOUBLE_PROXY, API.isPyProxy(obj));
  SET_FLAG_IF(IS_ARRAY, isArray);
  SET_FLAG_IF(IS_TYPEDARRAY, isBufferView && typeTag !== "[object DataView]");
  SET_FLAG_IF(
    IS_ARRAY_LIKE,
    !isArray &&
      hasLength &&
      type_flags & IS_ITERABLE &&
      !(type_flags & (IS_ITERATOR | IS_TYPEDARRAY))
  );
  SET_FLAG_IF(IS_GENERATOR, typeTag === "[object Generator]");
  SET_FLAG_IF(IS_ASYNC_GENERATOR, typeTag === "[object AsyncGenerator]");

  /**
   * DOMException is a weird special case. According to WHATWG, there are two
   * types of Exception objects, simple exceptions and DOMExceptions. The spec
   * says:
   *
   * > if an implementation gives native Error objects special powers or
   * > nonstandard properties (such as a stack property), it should also expose
   * > those on DOMException objects
   *
   * Firefox respects this and has DOMException.stack. But Safari and Chrome do
   * not. Hence the special check here for DOMException.
   */
  SET_FLAG_IF(
    IS_ERROR,
    hasProperty(obj, "name") &&
      hasProperty(obj, "message") &&
      (hasProperty(obj, "stack") || constructorName === "DOMException") &&
      !(type_flags & (IS_CALLABLE | IS_BUFFER))
  );

  if (is_py_json && type_flags & (IS_ARRAY | IS_ARRAY_LIKE | IS_ITERATOR)) {
    // tagging IS_PY_JSON_SEQUENCE on IS_ITERATOR is a bit of a hack
    type_flags |= IS_PY_JSON_SEQUENCE;
  }
  if (is_py_json && INCLUDE_OBJMAP_METHODS(type_flags)) {
    type_flags |= IS_PY_JSON_DICT;
  }
  return type_flags;
});
// clang-format on
#undef SET_FLAG_IF

////////////////////////////////////////////////////////////
// Public functions

PyObject*
JsProxy_create_with_type(int type_flags,
                         JsVal object,
                         JsVal this,
                         PyObject* sig)
{
  bool success = false;
  PyTypeObject* type = NULL;
  PyObject* result = NULL;

  type = JsProxy_get_subtype(type_flags);
  FAIL_IF_NULL(type);

  result = type->tp_alloc(type, 0);
  FAIL_IF_NONZERO(JsProxy_cinit(result, object, sig));
  if (type_flags & IS_CALLABLE) {
    FAIL_IF_NONZERO(JsMethod_cinit(result, this));
  }
  if (type_flags & IS_BUFFER) {
    FAIL_IF_NONZERO(JsBuffer_cinit(result));
  }
  if (type_flags & IS_ERROR) {
    PyObject* arg =
      JsProxy_create_with_type(type_flags & (~IS_ERROR), object, this, NULL);
    FAIL_IF_NULL(arg);
    PyObject* args = PyTuple_Pack(1, arg);
    Py_CLEAR(arg);
    FAIL_IF_NULL(args);
    JsException_ARGS(result) = args;
  }

  success = true;
finally:
  Py_CLEAR(type);
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

EM_JS_BOOL(bool, is_comlink_proxy, (JsVal obj), {
  return !!(API.Comlink && value[API.Comlink.createEndpoint]);
});

/**
 * Create a JsProxy. In case it's a method, bind "this" to the argument. (In
 * most cases "this" will be NULL, `JsProxy_create` specializes to this case.)
 * We check what capabilities are present on the javascript object, set
 * appropriate flags, then we get the appropriate type with JsProxy_get_subtype.
 */
PyObject*
JsProxy_create_with_this(JsVal object,
                         JsVal this,
                         PyObject* sig,
                         bool is_py_json)
{
  int type_flags = 0;
  if (is_comlink_proxy(object)) {
    // Comlink proxies are weird and break our feature detection pretty badly.
    type_flags = IS_CALLABLE | IS_AWAITABLE | IS_ARRAY;
  } else {
    type_flags = JsProxy_compute_typeflags(object, is_py_json);
    if (type_flags == -1) {
      fail_test();
      PyErr_SetString(internal_error,
                      "Internal error occurred in JsProxy_compute_typeflags");
      return NULL;
    }
  }
  return JsProxy_create_with_type(type_flags, object, this, sig);
}

EMSCRIPTEN_KEEPALIVE PyObject*
JsProxy_create(JsVal object)
{
  return JsProxy_create_with_this(object, Jsv_undefined, NULL, false);
}

PyObject*
JsProxy_create_objmap(JsVal object, int flags)
{
  bool is_py_json = !!(flags & OBJMAP_PY_JSON);
  int typeflags = JsProxy_compute_typeflags(object, is_py_json);
  if ((flags & OBJMAP_HEREDITARY) && INCLUDE_OBJMAP_METHODS(typeflags)) {
    typeflags |= IS_OBJECT_MAP;
  }
  return JsProxy_create_with_type(typeflags, object, Jsv_undefined, NULL);
}

EMSCRIPTEN_KEEPALIVE bool
JsProxy_Check(PyObject* x)
{
  return PyObject_TypeCheck(x, &JsProxyType);
}

JsVal
JsProxy_Val(PyObject* x)
{
  return JsProxy_VAL(x);
}

int
JsProxy_init_docstrings(PyObject* _pyodide_core_docs)
{
  bool success = false;

  PyObject* _it = NULL;
  PyObject* JsProxy = NULL;
  PyObject* JsPromise = NULL;
  PyObject* JsBuffer = NULL;
  PyObject* JsArray = NULL;
  PyObject* JsMutableMap = NULL;
  PyObject* JsDoubleProxy = NULL;
  PyObject* JsGenerator = NULL;

  _it = PyObject_GetAttrString(_pyodide_core_docs, "_instantiate_token");
  FAIL_IF_NULL(_it);

#define GetProxyDocClass(A)                                                    \
  _Py_IDENTIFIER(A);                                                           \
  A = _PyObject_CallMethodIdOneArg(_pyodide_core_docs, &PyId_##A, _it);        \
  FAIL_IF_NULL(A);

  GetProxyDocClass(JsProxy);
  GetProxyDocClass(JsPromise);
  GetProxyDocClass(JsBuffer);
  GetProxyDocClass(JsArray);
  GetProxyDocClass(JsMutableMap);
  GetProxyDocClass(JsDoubleProxy);
  GetProxyDocClass(JsGenerator);
#undef GetProxyDocClass

  // Load the docstrings for JsProxy methods from the corresponding stubs in
  // _pyodide._core_docs.set_method_docstring uses
  // _pyodide.docstring.get_cmeth_docstring to generate the appropriate C-style
  // docstring from the Python-style docstring.
#define SET_DOCSTRING(mock, x) FAIL_IF_MINUS_ONE(set_method_docstring(&x, mock))
  SET_DOCSTRING(JsProxy, JsProxy_object_entries_MethodDef);
  SET_DOCSTRING(JsProxy, JsProxy_object_keys_MethodDef);
  SET_DOCSTRING(JsProxy, JsProxy_object_values_MethodDef);
  SET_DOCSTRING(JsProxy, JsProxy_toPy_MethodDef);
  SET_DOCSTRING(JsProxy, JsMethod_Construct_MethodDef);

  SET_DOCSTRING(JsDoubleProxy, JsDoubleProxy_unwrap_MethodDef);
  // SET_DOCSTRING(JsProxy, JsProxy_Dir_MethodDef);

  SET_DOCSTRING(JsPromise, JsProxy_then_MethodDef);
  SET_DOCSTRING(JsPromise, JsProxy_catch_MethodDef);
  SET_DOCSTRING(JsPromise, JsProxy_finally_MethodDef);

  SET_DOCSTRING(JsArray, JsArray_extend_MethodDef);
  SET_DOCSTRING(JsArray, JsArray_reverse_MethodDef);
  SET_DOCSTRING(JsArray, JsArray_reversed_MethodDef);
  SET_DOCSTRING(JsArray, JsArray_pop_MethodDef);
  SET_DOCSTRING(JsArray, JsArray_append_MethodDef);
  SET_DOCSTRING(JsArray, JsArray_index_MethodDef);
  SET_DOCSTRING(JsArray, JsArray_count_MethodDef);

  SET_DOCSTRING(JsMutableMap, JsMap_keys_MethodDef);
  SET_DOCSTRING(JsMutableMap, JsMap_values_MethodDef);
  SET_DOCSTRING(JsMutableMap, JsMap_items_MethodDef);
  SET_DOCSTRING(JsMutableMap, JsMap_get_MethodDef);
  SET_DOCSTRING(JsMutableMap, JsMap_pop_MethodDef);
  SET_DOCSTRING(JsMutableMap, JsMap_popitem_MethodDef);
  SET_DOCSTRING(JsMutableMap, JsMap_clear_MethodDef);
  SET_DOCSTRING(JsMutableMap, JsMap_update_MethodDef);
  SET_DOCSTRING(JsMutableMap, JsMap_setdefault_MethodDef);

  SET_DOCSTRING(JsBuffer, JsBuffer_assign_MethodDef);
  SET_DOCSTRING(JsBuffer, JsBuffer_assign_to_MethodDef);
  SET_DOCSTRING(JsBuffer, JsBuffer_tomemoryview_MethodDef);
  SET_DOCSTRING(JsBuffer, JsBuffer_tobytes_MethodDef);
  SET_DOCSTRING(JsBuffer, JsBuffer_tostring_MethodDef);
  SET_DOCSTRING(JsBuffer, JsBuffer_write_to_file_MethodDef);
  SET_DOCSTRING(JsBuffer, JsBuffer_read_from_file_MethodDef);
  SET_DOCSTRING(JsBuffer, JsBuffer_into_file_MethodDef);

  SET_DOCSTRING(JsGenerator, JsGenerator_send_MethodDef);
  SET_DOCSTRING(JsGenerator, JsGenerator_throw_MethodDef);
  SET_DOCSTRING(JsGenerator, JsGenerator_close_MethodDef);
#undef SET_DOCSTRING

  success = true;
finally:
  Py_CLEAR(_it);
  Py_CLEAR(JsProxy);
  Py_CLEAR(JsPromise);
  Py_CLEAR(JsBuffer);
  Py_CLEAR(JsArray);
  Py_CLEAR(JsMutableMap);
  Py_CLEAR(JsDoubleProxy);
  Py_CLEAR(JsGenerator);
  return success ? 0 : -1;
}

static int
add_flag(PyObject* dict, char* name, int value)
{
  PyObject* value_py = NULL;
  bool success = false;

  value_py = PyLong_FromLong(value);
  FAIL_IF_NULL(value_py);
  FAIL_IF_MINUS_ONE(PyDict_SetItemString(dict, name, value_py));

  success = true;
finally:
  Py_CLEAR(value_py);
  return success ? 0 : -1;
}

PyObject*
run_sync_not_supported(PyObject* mod, PyObject* Py_UNUSED(arg))
{
  PyErr_SetString(
    PyExc_RuntimeError,
    "WebAssembly stack switching not supported in this JavaScript runtime");
  return NULL;
}

PyObject*
run_sync(PyObject* self, PyObject* pyarg)
{
  if (!py_is_awaitable(pyarg)) {
    PyErr_Format(PyExc_TypeError,
                 "object %.100s is not awaitable",
                 Py_TYPE(pyarg)->tp_name);
    return NULL;
  }
  PyObject* ensured_future = NULL;
  PyObject* pyresult = NULL;

  // For reasons that I absolutely do not comprehend, we leak memory if use a
  // coroutine directly, but if we ensure_future it first we don't.
  ensured_future =
    _PyObject_CallMethodIdOneArg(asyncio_mod, &PyId_ensure_future, pyarg);
  JsVal jsarg = python2js(ensured_future);
  FAIL_IF_JS_ERROR(jsarg);
  JsVal jsresult = JsvPromise_Syncify(jsarg);
  if (JsvError_Check(jsresult)) {
    if (!PyErr_Occurred()) {
      PyErr_SetString(
        PyExc_RuntimeError,
        "Cannot stack switch because the Python entrypoint was a synchronous "
        "function. Use pyFunc.callPromising() to fix.");
    }
    FAIL();
  }
  pyresult = js2python(jsresult);

finally:
  if (pyproxy_Check(jsarg)) {
    destroy_proxy(jsarg, NULL);
  }
  if (pyproxy_Check(jsresult)) {
    destroy_proxy(jsresult, NULL);
  }
  Py_CLEAR(ensured_future);
  return pyresult;
}

EM_JS(int, can_run_sync_js, (), { return !!validSuspender.value; });

PyObject*
can_run_sync(PyObject* _mod, PyObject* _null)
{
  if (can_run_sync_js()) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

PyMethodDef methods[] = {
  {
    "run_sync",
    // We select the appropriate choice between run_sync and
    // run_sync_not_supported in jsproxy_init.
    (PyCFunction)NULL,
    METH_O,
  },
  {
    "can_run_sync",
    (PyCFunction)can_run_sync,
    METH_NOARGS,
  },
  { NULL } /* Sentinel */
};
static PyMethodDef* run_sync_MethodDef = &methods[0];

int
jsproxy_init(PyObject* core_module)
{
  bool success = false;
  PyObject* _pyodide_core_docs = NULL;
  PyObject* flag_dict = NULL;

  _pyodide_core_docs = PyImport_ImportModule("_pyodide._core_docs");
  FAIL_IF_NULL(_pyodide_core_docs);
  JsProxy_metaclass =
    PyObject_GetAttrString(_pyodide_core_docs, "_JsProxyMetaClass");
  FAIL_IF_NULL(JsProxy_metaclass);

  bool jspiSupported = EM_ASM_INT({ return jspiSupported; });
  if (jspiSupported) {
    run_sync_MethodDef->ml_meth = (PyCFunction)run_sync;
  } else {
    run_sync_MethodDef->ml_meth = (PyCFunction)run_sync_not_supported;
  }

  FAIL_IF_MINUS_ONE(
    add_methods_and_set_docstrings(core_module, methods, _pyodide_core_docs));

  collections_abc = PyImport_ImportModule("collections.abc");
  FAIL_IF_NULL(collections_abc);
  MutableSequence = PyObject_GetAttrString(collections_abc, "MutableSequence");
  FAIL_IF_NULL(MutableSequence);
  Sequence = PyObject_GetAttrString(collections_abc, "Sequence");
  FAIL_IF_NULL(Sequence);
  MutableMapping = PyObject_GetAttrString(collections_abc, "MutableMapping");
  FAIL_IF_NULL(MutableMapping);
  Mapping = PyObject_GetAttrString(collections_abc, "Mapping");
  FAIL_IF_NULL(Mapping);
  typing = PyImport_ImportModule("typing");
  FAIL_IF_NULL(typing);
  future_helper_mod = PyImport_ImportModule("_pyodide._future_helper");
  FAIL_IF_NULL(future_helper_mod);

  FAIL_IF_MINUS_ONE(JsProxy_init_docstrings(_pyodide_core_docs));

  flag_dict = PyDict_New();
  FAIL_IF_NULL(flag_dict);

#define AddFlag(flag) FAIL_IF_MINUS_ONE(add_flag(flag_dict, #flag, flag))

  AddFlag(IS_ITERABLE);
  AddFlag(IS_ITERATOR);
  AddFlag(HAS_LENGTH);
  AddFlag(HAS_GET);
  AddFlag(HAS_SET);
  AddFlag(HAS_HAS);
  AddFlag(HAS_INCLUDES);
  AddFlag(IS_AWAITABLE);
  AddFlag(IS_BUFFER);
  AddFlag(IS_CALLABLE);
  AddFlag(IS_ARRAY);
  AddFlag(IS_ARRAY_LIKE);
  AddFlag(IS_TYPEDARRAY);
  AddFlag(IS_DOUBLE_PROXY);
  AddFlag(IS_OBJECT_MAP);
  AddFlag(IS_ASYNC_ITERABLE);
  AddFlag(IS_GENERATOR);
  AddFlag(IS_ASYNC_GENERATOR);
  AddFlag(IS_ASYNC_ITERATOR);
  AddFlag(IS_ERROR);
  AddFlag(IS_PY_JSON_DICT);
  AddFlag(IS_PY_JSON_SEQUENCE);

#undef AddFlag
  FAIL_IF_MINUS_ONE(PyObject_SetAttrString(core_module, "js_flags", flag_dict));

  asyncio_mod = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_mod);

  JsProxy_TypeDict = PyDict_New();
  FAIL_IF_NULL(JsProxy_TypeDict);

  FAIL_IF_MINUS_ONE(
    PyModule_AddObject(core_module, "jsproxy_typedict", JsProxy_TypeDict));

  FAIL_IF_MINUS_ONE(PyType_Ready(&JsProxyType));
  FAIL_IF_MINUS_ONE(PyType_Ready(&BufferType));
  JsException = (PyObject*)JsProxy_get_subtype(IS_ERROR);
  FAIL_IF_NULL(JsException);
  FAIL_IF_MINUS_ONE(
    PyObject_SetAttrString(core_module, "JsException", JsException));
  FAIL_IF_MINUS_ONE(PyType_Ready(&JsMethodCallSingletonType));
  method_call_singleton = make_method_call_singleton();

  success = true;
finally:
  Py_CLEAR(_pyodide_core_docs);
  Py_CLEAR(flag_dict);
  return success ? 0 : -1;
}
