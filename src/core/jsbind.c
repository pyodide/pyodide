#define PY_SSIZE_T_CLEAN
#include "jsbind.h"
#include "Python.h"
#include "error_handling.h"
#include "js2python.h"
#include "jslib.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include "python2js.h"
#include "stddef.h"

// Py2JsConverter

typedef JsVal(Py2JsConvertFunc)(PyObject* self, PyObject* pyval, JsVal proxies);
// clang-format off
typedef struct
{
  PyObject_HEAD
  Py2JsConvertFunc* converter;
  PyObject* pre_convert;
} Py2JsConverter;
// clang-format on

#define Py2JsConverter_pre_convert(o) ((Py2JsConverter*)o)->pre_convert
#define Py2JsConverter_converter(o) ((Py2JsConverter*)o)->converter

static PyTypeObject Py2JsConverterType;

static PyObject*
Py2JsConverter_cnew(Py2JsConvertFunc* converter)
{
  PyObject* self = Py2JsConverterType.tp_alloc(&Py2JsConverterType, 0);
  Py2JsConverter_converter(self) = converter;
  Py2JsConverter_pre_convert(self) = NULL;
  return self;
}

static PyObject*
Py2JsConverter_copy(PyObject* self, PyObject* _unused)
{
  PyObject* result = Py2JsConverter_cnew(Py2JsConverter_converter(self));
  if (result == NULL) {
    return NULL;
  }
  Py2JsConverter_pre_convert(result) = Py2JsConverter_pre_convert(self);
  return result;
}

static int
Py2JsConverter_clear(PyObject* o)
{
  Py2JsConverter* self = (Py2JsConverter*)o;
  Py_CLEAR(self->pre_convert);
  return 0;
}

static void
Py2JsConverter_dealloc(PyObject* self)
{
  PyTypeObject* tp = Py_TYPE(self);
  PyObject_GC_UnTrack(self);
  tp->tp_clear(self);
  tp->tp_free(self);
}

static int
Py2JsConverter_traverse(PyObject* o, visitproc visit, void* arg)
{
  Py2JsConverter* self = (Py2JsConverter*)o;
  Py_VISIT(self->pre_convert);
  return 0;
}

static PyObject*
py2js_python_from_c(PyObject* self, PyObject* pyval)
{
  JsVal jsresult = Py2JsConverter_converter(self)(self, pyval, JS_ERROR);
  return js2python(jsresult);
}

static PyMethodDef Py2JsConverter_methods[] = {
  {
    "py2js_convert",
    py2js_python_from_c,
    METH_O,
  },
  {
    "copy",
    Py2JsConverter_copy,
    METH_NOARGS,
  },
  { NULL } /* Sentinel */
};

static PyMemberDef Py2JsConverter_members[] = {
  { .name = "pre_convert",
    .type = Py_T_OBJECT_EX,
    .flags = 0,
    .offset = offsetof(Py2JsConverter, pre_convert) },
  { NULL } /* Sentinel */
};

static PyTypeObject Py2JsConverterType = {
  .tp_name = "Py2JsConverter",
  .tp_basicsize = sizeof(Py2JsConverter),
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
  .tp_clear = Py2JsConverter_clear,
  .tp_dealloc = Py2JsConverter_dealloc,
  .tp_traverse = Py2JsConverter_traverse,
  .tp_methods = Py2JsConverter_methods,
  .tp_members = Py2JsConverter_members,
  .tp_doc = PyDoc_STR(
    "Represents a method for converting from Python objects to JS objects"),
};

JsVal
Py2JsConverter_convert(PyObject* converter, PyObject* pyval, JsVal proxies)
{
  PyObject* pre_converted = NULL;
  JsVal result = JS_ERROR;

  int status = PyObject_IsInstance(converter, (PyObject*)&Py2JsConverterType);
  if (status == 0) {
    PyErr_Format(
      PyExc_TypeError, "converter isn't of type Py2JsConverter %R", converter);
    FAIL();
  }
  FAIL_IF_MINUS_ONE(status);
  PyObject* pre_convert = Py2JsConverter_pre_convert(converter);
  if (pre_convert != NULL) {
    pre_converted = PyObject_CallOneArg(pre_convert, pyval);
    FAIL_IF_NULL(pre_converted);
  } else {
    pre_converted = Py_NewRef(pyval);
  }

  result =
    Py2JsConverter_converter(converter)(converter, pre_converted, proxies);
finally:
  Py_CLEAR(pre_converted);
  return result;
}

// Js2PyConverter

typedef PyObject*(Js2PyConvertFunc)(PyObject* self, JsVal jsval, JsVal proxies);

typedef struct
{
  PyObject_HEAD Js2PyConvertFunc* converter;
  PyObject* post_convert;
  PyObject* extra;
} Js2PyConverter;

#define Js2PyConverter_converter(o) ((Js2PyConverter*)o)->converter
#define Js2PyConverter_post_convert(o) ((Js2PyConverter*)o)->post_convert
#define Js2PyConverter_extra(o) ((Js2PyConverter*)o)->extra

static PyTypeObject Js2PyConverterType;

static PyObject*
Js2PyConverter_cnew(Js2PyConvertFunc* converter)
{
  PyObject* self = Js2PyConverterType.tp_alloc(&Js2PyConverterType, 0);
  Js2PyConverter_converter(self) = converter;
  Js2PyConverter_post_convert(self) = NULL;
  return self;
}

static PyObject*
Js2PyConverter_copy(PyObject* self, PyObject* _unused)
{
  PyObject* result = Js2PyConverter_cnew(Js2PyConverter_converter(self));
  Js2PyConverter_post_convert(result) = Js2PyConverter_post_convert(self);
  return result;
}

static int
Js2PyConverter_clear(PyObject* o)
{
  Js2PyConverter* self = (Js2PyConverter*)o;
  Py_CLEAR(self->post_convert);
  Py_CLEAR(self->extra);
  return 0;
}

static void
Js2PyConverter_dealloc(PyObject* self)
{
  PyTypeObject* tp = Py_TYPE(self);
  PyObject_GC_UnTrack(self);
  tp->tp_clear(self);
  tp->tp_free(self);
}

static int
Js2PyConverter_traverse(PyObject* o, visitproc visit, void* arg)
{
  Js2PyConverter* self = (Js2PyConverter*)o;
  Py_VISIT(self->post_convert);
  Py_VISIT(self->extra);
  return 0;
}

static PyObject*
js2py_python_from_c(PyObject* self, PyObject* pyval)
{
  JsVal jsval = python2js(pyval);
  return Js2PyConverter_converter(self)(self, jsval, JS_ERROR);
}

static PyMethodDef Js2PyConverter_methods[] = {
  {
    "js2py_convert",
    js2py_python_from_c,
    METH_O,
  },
  {
    "copy",
    Js2PyConverter_copy,
    METH_NOARGS,
  },
  { NULL } /* Sentinel */
};

static PyMemberDef Js2PyConverter_members[] = {
  { .name = "post_convert",
    .type = Py_T_OBJECT_EX,
    .flags = 0,
    .offset = offsetof(Js2PyConverter, post_convert) },
  { NULL } /* Sentinel */
};

static PyTypeObject Js2PyConverterType = {
  .tp_name = "Js2PyConverter",
  .tp_basicsize = sizeof(Js2PyConverter),
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
  .tp_clear = Js2PyConverter_clear,
  .tp_dealloc = Js2PyConverter_dealloc,
  .tp_traverse = Js2PyConverter_traverse,
  .tp_methods = Js2PyConverter_methods,
  .tp_members = Js2PyConverter_members,
  .tp_doc = PyDoc_STR(
    "Represents a method for converting from JS objects to Python objects"),
};

PyObject*
Js2PyConverter_convert(PyObject* converter, JsVal jsval, JsVal proxies)
{
  int status = PyObject_IsInstance(converter, (PyObject*)&Js2PyConverterType);
  if (status == 0) {
    PyErr_Format(
      PyExc_TypeError, "converter isn't of type Js2PyConverter %R", converter);
  }
  if (status != 1) {
    return NULL;
  }
  PyObject* result =
    Js2PyConverter_converter(converter)(converter, jsval, proxies);
  FAIL_IF_NULL(result);

  PyObject* post_convert = Js2PyConverter_post_convert(converter);
  if (!post_convert) {
    return result;
  }

  PyObject* post_converted = PyObject_CallOneArg(post_convert, result);
  Py_CLEAR(result);
  return post_converted;
finally:
  return NULL;
}

// Py2Js conversion functions get as arguments:
// - self: the converter object
// - pyval: the value to convert
// - proxies: if we create a PyProxy, we add it to this list unless we are
//   managing the lifetime in some custom way. Ideally we should also not
//   gc_register them...

static JsVal
Py2Js_func_default(PyObject* self, PyObject* pyval, JsVal proxies)
{
  return python2js_track_proxies(pyval, proxies, /* gc_register=*/false);
}

// clang-format off
EM_JS(JsVal, my_dict_converter, (void), {
  return Object.fromEntries;
});
// clang-format on

// Deep conversion with Object.fromEntries as the dict converter.
//
// TODO: we should probably allow the user to specify their own dict_converter,
// default_converter, and perhaps depth. Also, I think this gc_registers the
// proxies but it would be better if we didn't.
static JsVal
Py2Js_func_deep(PyObject* self, PyObject* pyval, JsVal proxies)
{
  return python2js_custom(pyval,
                          /* depth=*/-1,
                          proxies,
                          my_dict_converter(),
                          /*default_converter=*/JS_ERROR,
                          /*eager_converter=*/JS_ERROR);
}

JsVal
python2js_inner(PyObject* x,
                JsVal proxies,
                bool track_proxies,
                bool gc_register,
                bool is_json_adaptor);

static JsVal
Py2Js_func_as_js_json(PyObject* self, PyObject* pyval, JsVal proxies)
{
  return python2js_inner(pyval,
                         proxies,
                         /* track_proxies=*/true,
                         /* gc_register=*/false,
                         /*is_json_adaptor=*/true);
}

// Js2Py conversion functions get as arguments:
// - self: the converter object
// - jsval: the value to convert
// - proxies: if null, we are converting an attribute, if not null it's a Js
//   Array of proxies. We are responsible for destroying these when we're done
//   with them, either immediately after the function call or possibly later if
//   the result is a Promise or a Future. If we don't destroy them immediately,
//   we have to call gc_register_proxies(proxies). If we raise an error, we
//   don't need to destroy the proxies since the call function will do it for
//   us.

Js_static_string(PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL,
                 "This borrowed proxy was automatically destroyed at the "
                 "end of a function call. Try using "
                 "create_proxy or create_once_callable.");

static void
maybe_destroy_proxies(JsVal jsval, JsVal proxies)
{
  if (JsvError_Check(proxies)) {
    return;
  }
  if (!JsvError_Check(jsval) && pyproxy_Check(jsval)) {
    // TODO: don't destroy proxies with roundtrip = true?
    JsvArray_Push(proxies, jsval);
  }
  destroy_proxies(proxies, &PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL);
}

// Default js2py conversion.
static PyObject*
Js2Py_func_default(PyObject* self, JsVal jsval, JsVal proxies)
{
  PyObject* result = js2python(jsval);
  maybe_destroy_proxies(jsval, proxies);
  return result;
}

// Deep js2py conversion for attribute lookup.
static PyObject*
Js2Py_func_deep(PyObject* self, JsVal jsval, JsVal proxies)
{
  PyObject* result = js2python_convert(jsval, -1, Jsv_undefined);
  maybe_destroy_proxies(jsval, proxies);
  return result;
}

static PyObject*
Js2Py_func_as_py_json(PyObject* self, JsVal jsval, JsVal proxies)
{
  PyObject* result = js2python_as_py_json(jsval);
  maybe_destroy_proxies(jsval, proxies);
  return result;
}

/**
 * This is a helper function for calling asynchronous js functions. proxies_id
 * is an Array of proxies to destroy, it returns a JsRef to a function that
 * destroys them and the result of the Promise.
 */
EM_JS_VAL(JsVal, get_async_js_call_done_callback, (JsVal proxies), {
  return function(result)
  {
    let msg = "This borrowed proxy was automatically destroyed " +
              "at the end of an asynchronous function call. Try " +
              "using create_proxy or create_once_callable.";
    for (let px of proxies) {
      Module.pyproxy_destroy(px, msg, false);
    }
    if (API.isPyProxy(result)) {
      Module.pyproxy_destroy(result, msg, false);
    }
  };
});

// Promise conversion. We use "extra" to record the converter we want to use for
// the promise result.
static PyObject*
Js2Py_func_promise(PyObject* self, JsVal jsresult, JsVal proxies)
{
  bool is_promise = JsvPromise_Check(jsresult);

  if (!is_promise) {
    PyErr_SetString(PyExc_TypeError, "Expected js func to return a promise");
    return NULL;
  }

  JsVal done_callback = Jsv_null;
  if (!JsvNull_Check(proxies)) {
    gc_register_proxies(proxies);
    done_callback = get_async_js_call_done_callback(proxies);
  }
  return wrap_promise(jsresult, done_callback, Js2PyConverter_extra(self));
}

// Make a promise_converter. Store result_converter into Js2PyConverter_extra.
static PyObject*
create_promise_converter(PyObject* self, PyObject* result_converter)
{
  PyObject* result = Js2PyConverter_cnew(Js2Py_func_promise);
  if (result == NULL) {
    return NULL;
  }
  if (!Py_IsNone(result_converter)) {
    Js2PyConverter_extra(result) = Py_NewRef(result_converter);
  }
  return result;
}

// clang-format off
EM_JS_VAL(JsVal, wrap_generator, (JsVal gen, JsVal proxies), {
  proxies = new Set(proxies);
  const msg =
    "This borrowed proxy was automatically destroyed " +
    "when a generator completed execution. Try " +
    "using create_proxy or create_once_callable.";
  function cleanup() {
    proxies.forEach((px) => Module.pyproxy_destroy(px, msg));
  }
  function wrap(funcname) {
    return function (val) {
      if(API.isPyProxy(val)) {
        val = val.copy();
        proxies.add(val);
      }
      let res;
      try {
        res = gen[funcname](val);
      } catch (e) {
        cleanup();
        throw e;
      }
      if (res.done) {
        // Don't destroy the return value!
        proxies.delete(res.value);
        cleanup();
      }
      return res;
    };
  }
  return {
    get [Symbol.toStringTag]() {
      return "Generator";
    },
    [Symbol.iterator]() {
      return this;
    },
    next: wrap("next"),
    throw: wrap("throw"),
    return: wrap("return"),
  };
});

EM_JS_VAL(JsVal, wrap_async_generator, (JsVal gen, JsVal proxies), {
  proxies = new Set(proxies);
  const msg =
    "This borrowed proxy was automatically destroyed " +
    "when an asynchronous generator completed execution. Try " +
    "using create_proxy or create_once_callable.";
  function cleanup() {
    proxies.forEach((px) => Module.pyproxy_destroy(px, msg));
  }
  function wrap(funcname) {
    return async function (val) {
      if(API.isPyProxy(val)) {
        val = val.copy();
        proxies.add(val);
      }
      let res;
      try {
        res = await gen[funcname](val);
      } catch (e) {
        cleanup();
        throw e;
      }
      if (res.done) {
        // Don't destroy the return value!
        proxies.delete(res.value);
        cleanup();
      }
      return res;
    };
  }
  return {
    get [Symbol.toStringTag]() {
      return "AsyncGenerator";
    },
    [Symbol.asyncIterator]() {
      return this;
    },
    next: wrap("next"),
    throw: wrap("throw"),
    return: wrap("return"),
  };
});
// clang-format on

// Deep js2py conversion for function call result.
static PyObject*
Js2Py_func_default_call_result(PyObject* self, JsVal jsresult, JsVal proxies)
{
  PyObject* pyresult = NULL;
  // various cases where we want to extend the lifetime of the arguments:
  // 1. if the return value is a promise we extend arguments lifetime until the
  //    promise resolves.
  // 2. If the return value is a sync or async generator we extend the lifetime
  //    of the arguments until the generator returns.
  bool is_promise = JsvPromise_Check(jsresult);
  bool is_generator = !is_promise && JsvGenerator_Check(jsresult);
  bool is_async_generator =
    !is_promise && !is_generator && JsvAsyncGenerator_Check(jsresult);
  bool destroy_args = !is_promise && !is_generator && !is_async_generator;
  if (is_generator) {
    jsresult = wrap_generator(jsresult, proxies);
  } else if (is_async_generator) {
    jsresult = wrap_async_generator(jsresult, proxies);
  }
  FAIL_IF_JS_ERROR(jsresult);
  if (is_promise) {
    // Since we will destroy the result of the Promise when it resolves we deny
    // the user access to the Promise (which would destroyed proxy exceptions).
    // Instead we return a Future. When the promise is ready, we resolve the
    // Future with the result from the Promise and destroy the arguments and
    // result.
    pyresult =
      wrap_promise(jsresult, get_async_js_call_done_callback(proxies), NULL);
  } else {
    pyresult = js2python(jsresult);
  }
  FAIL_IF_NULL(pyresult);
  if (JsvError_Check(proxies)) {
    // Nothing to do.
  } else if (destroy_args) {
    // If we succeeded and the result was a promise then we destroy the
    // arguments in async_done_callback instead of here. Otherwise, destroy the
    // arguments and return value now.
    if (!JsvError_Check(jsresult) && pyproxy_Check(jsresult)) {
      // TODO: don't destroy proxies with roundtrip = true?
      JsvArray_Push(proxies, jsresult);
    }
    destroy_proxies(proxies, &PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL);
  } else {
    gc_register_proxies(proxies);
  }
finally:
  return pyresult;
}

static int
add_py2js_converter(PyObject* core_mod,
                    const char* name,
                    Py2JsConvertFunc* func)
{
  bool success = false;

  PyObject* converter = Py2JsConverter_cnew(func);
  FAIL_IF_NULL(converter);
  FAIL_IF_MINUS_ONE(PyObject_SetAttrString(core_mod, name, converter));

  success = true;
finally:
  Py_CLEAR(converter);
  return success ? 0 : -1;
}

static int
add_js2py_converter(PyObject* core_mod,
                    const char* name,
                    Js2PyConvertFunc* func)
{
  bool success = false;

  PyObject* converter = Js2PyConverter_cnew(func);
  FAIL_IF_NULL(converter);
  FAIL_IF_MINUS_ONE(PyObject_SetAttrString(core_mod, name, converter));

  success = true;
finally:
  Py_CLEAR(converter);
  return success ? 0 : -1;
}

#define ADD_TYPE(type)                                                         \
  FAIL_IF_MINUS_ONE(PyType_Ready(&type##Type));                                \
  FAIL_IF_MINUS_ONE(                                                           \
    PyObject_SetAttrString(core_mod, #type, (PyObject*)&type##Type));

#define ADD_PY2JS(name)                                                        \
  FAIL_IF_MINUS_ONE(                                                           \
    add_py2js_converter(core_mod, "py2js_" #name, Py2Js_func_##name))

#define ADD_JS2PY(name)                                                        \
  FAIL_IF_MINUS_ONE(                                                           \
    add_js2py_converter(core_mod, "js2py_" #name, Js2Py_func_##name))

PyObject* jsbind = NULL;
PyObject* no_default = NULL;
PyObject* default_signature = NULL;

static PyMethodDef methods[] = {
  {
    "create_promise_converter",
    (PyCFunction)create_promise_converter,
    METH_O,
  },
  { NULL } /* Sentinel */
};

int
jsbind_init(PyObject* core_mod)
{
  bool success = false;
  ADD_TYPE(Py2JsConverter);
  ADD_TYPE(Js2PyConverter);

  ADD_PY2JS(as_js_json);
  ADD_PY2JS(deep);
  ADD_PY2JS(default);

  ADD_JS2PY(deep);
  ADD_JS2PY(as_py_json);
  ADD_JS2PY(default);
  ADD_JS2PY(default_call_result);
  ADD_JS2PY(promise);

  FAIL_IF_MINUS_ONE(PyModule_AddFunctions(core_mod, methods));

  jsbind = PyImport_ImportModule("_pyodide.jsbind");
  FAIL_IF_NULL(jsbind);
  no_default = PyObject_GetAttrString(jsbind, "no_default");
  FAIL_IF_NULL(no_default);
  default_signature = PyObject_GetAttrString(jsbind, "default_signature");
  FAIL_IF_NULL(default_signature);

  success = true;
finally:
  return success ? 0 : -1;
}
