#define PY_SSIZE_T_CLEAN
#include "jsproxy_call.h"
#include "error_handling.h"
#include "js2python.h"
#include "jsbind.h"
#include "jslib.h"
#include "pyproxy.h"
#include "python2js.h"
#include "python_unexposed.h"
#include "stddef.h"

Js_static_string(PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL,
                 "This borrowed proxy was automatically destroyed at the "
                 "end of a function call. Try using "
                 "create_proxy or create_once_callable.");

// JsFuncSignature
//
// This holds signature data for functions. It's instantiated in
// func_to_sig_inner in _pyodide.jsbind.py.
//
// This is laid out to make argument conversion as fast and easy in C as
// possible. jsbind.py transposes a bunch of data for us towards this end.
//
// The default argument converter is Py2Js_func_default. The default result
// converter is Js2Py_func_default_call_result.
//
// The default signature is held in default_signature which is loaded by
// jsbind_init(). It has no posparams or kwparams, and the default converters
// for varpos, varkwd, and result.
//

// clang-format off
typedef struct {
  PyObject_HEAD
  // The function we made this from. We call it when there are bad args in order
  // to make a TypeError that exactly matches the standard Python TypeError.
  PyObject* func;
  bool should_construct;
  // Number of mandatory positional arguments
  int posparams_nmandatory;
  // A tuple of Py2JsConverters.
  PyObject* posparams;
  // A tuple of default values for each non mandatory positional parameter. of
  // length len(posparams) - posparams_nmandatory
  PyObject* posparams_defaults;
  // The *args Py2JsConverter or None if we don't accept varargs
  PyObject* varpos;
  // The tuple of names of the keyword only arguments
  PyObject* kwparam_names;
  // The tuple of converters of the keyword only arguments
  PyObject* kwparam_converters;
  // The tuple of defaults of the keyword only arguments. If the argument has no
  // default, it has inspect.Parameter.empty.
  PyObject* kwparam_defaults;
  // A bit flag indicating which arguments have defaults. The same as checking
  // whether `kwparam_defaults[i] == inspect.Parameter.empty` but faster and
  // less painful in C.
  uint64_t kwparam_has_default;
  // The **kwargs converter or None if we don't accept kwargs.
  PyObject* varkwd;
  // The result Js2PyConverter
  PyObject* result;
} JsFuncSignature;
// clang-format on

// Now a lot of boilerplate to set up JsFuncSignature. It's opaque from Python.
static int
JsFuncSignature_init(PyObject* o, PyObject* args, PyObject* kwds)
{
  JsFuncSignature* self = (JsFuncSignature*)o;
  static char* kwlist[] = { "func",
                            "should_construct",
                            "posparams_nmandatory",
                            "posparams",
                            "posparams_defaults",
                            "varpos",
                            "kwparam_names",
                            "kwparam_converters",
                            "kwparam_defaults",
                            "varkwd",
                            "result",
                            0 };
  if (!PyArg_ParseTupleAndKeywords(args,
                                   kwds,
                                   "OpiOOOOOOOO:__init__",
                                   kwlist,
                                   &self->func,
                                   &self->should_construct,
                                   &self->posparams_nmandatory,
                                   &self->posparams,
                                   &self->posparams_defaults,
                                   &self->varpos,
                                   &self->kwparam_names,
                                   &self->kwparam_converters,
                                   &self->kwparam_defaults,
                                   &self->varkwd,
                                   &self->result)) {
    return -1;
  }
  Py_INCREF(self->func);
  Py_INCREF(self->posparams);
  Py_INCREF(self->posparams_defaults);
  Py_INCREF(self->varpos);
  Py_INCREF(self->kwparam_names);
  Py_INCREF(self->kwparam_converters);
  Py_INCREF(self->kwparam_defaults);
  Py_INCREF(self->varkwd);
  Py_INCREF(self->result);
  return 0;
}

static int
JsFuncSignature_clear(PyObject* o)
{
  JsFuncSignature* self = (JsFuncSignature*)o;
  Py_CLEAR(self->func);
  Py_CLEAR(self->posparams);
  Py_CLEAR(self->posparams_defaults);
  Py_CLEAR(self->varpos);
  Py_CLEAR(self->kwparam_names);
  Py_CLEAR(self->kwparam_converters);
  Py_CLEAR(self->kwparam_defaults);
  Py_CLEAR(self->varkwd);
  Py_CLEAR(self->result);
  return 0;
}

static void
JsFuncSignature_dealloc(PyObject* self)
{
  PyObject_GC_UnTrack(self);
  JsFuncSignature_clear(self);
  Py_TYPE(self)->tp_free(self);
}

static int
JsFuncSignature_traverse(PyObject* o, visitproc visit, void* arg)
{
  JsFuncSignature* self = (JsFuncSignature*)o;
  Py_VISIT(self->func);
  Py_VISIT(self->posparams);
  Py_VISIT(self->posparams_defaults);
  Py_VISIT(self->varpos);
  Py_VISIT(self->kwparam_names);
  Py_VISIT(self->kwparam_converters);
  Py_VISIT(self->kwparam_defaults);
  Py_VISIT(self->varkwd);
  Py_VISIT(self->result);
  return 0;
}

// In Python this would be:
// "<JsSignature {}>".format(inspect.signature(self->func))
static PyObject*
JsFuncSignature_repr(PyObject* o)
{
  JsFuncSignature* self = (JsFuncSignature*)o;
  FAIL_RETURN_VALUE(NULL);

  DECLARE_PY_OBJECT(inspect);
  inspect = PyImport_ImportModule("inspect");
  FAIL_IF_NULL(inspect);
  _Py_IDENTIFIER(signature);
  DECLARE_PY_OBJECT(sig);
  sig = _PyObject_CallMethodIdOneArg(inspect, &PyId_signature, self->func);
  FAIL_IF_NULL(sig);

  return PyUnicode_FromFormat("<JsSignature %S>", sig);
}

static PyTypeObject JsFuncSignatureType = {
  .tp_name = "JsFuncSignature",
  .tp_new = PyType_GenericNew,
  .tp_init = JsFuncSignature_init,
  .tp_clear = JsFuncSignature_clear,
  .tp_dealloc = JsFuncSignature_dealloc,
  .tp_traverse = JsFuncSignature_traverse,
  .tp_basicsize = sizeof(JsFuncSignature),
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
  .tp_repr = JsFuncSignature_repr,
  .tp_doc =
    PyDoc_STR("A signature that we use to inform how we call a JS function"),
};

static Py_ssize_t
find_keyword(PyObject* kwarg_names, PyObject* key)
{
  Py_ssize_t nkwargs = PyTuple_GET_SIZE(kwarg_names);
  for (Py_ssize_t i = 0; i < nkwargs; i++) {
    PyObject* kwname = PyTuple_GET_ITEM(kwarg_names, i);

    /* kwname == key will normally find a match in since keyword keys
        should be interned strings; if not retry below in a new loop. */
    if (kwname == key) {
      return i;
    }
  }

  for (Py_ssize_t i = 0; i < nkwargs; i++) {
    PyObject* kwname = PyTuple_GET_ITEM(kwarg_names, i);
    assert(PyUnicode_Check(kwname));
    if (PyUnicode_Equal(kwname, key)) {
      return i;
    }
  }
  return -1;
}

/**
 * Prepare arguments from a `METH_FASTCALL | METH_KEYWORDS` Python function to a
 * JavaScript call. We call `python2js` on each argument. Any PyProxy *created*
 * by `python2js` is stored into the `proxies` list to be destroyed later (if
 * the argument is a PyProxy created with `create_proxy` it won't be recorded
 * for destruction).
 */
static JsVal
JsMethod_ConvertArgs(JsFuncSignature* sig,
                     PyObject* const* pyargs,
                     Py_ssize_t nargsf,
                     PyObject* kwnames,
                     JsVal proxies)
{
  FAIL_RETURN_VALUE(JS_ERROR);
  ON_FAIL({
    if (!PyErr_Occurred()) {
      PyErr_SetString(PyExc_SystemError, "Oops");
    }
  });

  int nargs = PyVectorcall_NARGS(nargsf);
  int pos_params_size = PyTuple_GET_SIZE(sig->posparams);
  int pos_args = nargs < pos_params_size ? nargs : pos_params_size;
  if (nargs < sig->posparams_nmandatory) {
    goto set_args_error;
  }
  JsVal jsargs = JsvArray_New();
  // present positional arguments
  for (Py_ssize_t i = 0; i < pos_args; ++i) {
    PyObject* converter = PyTuple_GET_ITEM(sig->posparams, i); /* borrowed! */
    JsVal arg = Py2JsConverter_convert(converter, pyargs[i], proxies);
    FAIL_IF_JS_ERROR(arg);
    JsvArray_Push(jsargs, arg);
  }
  // default positional arguments
  for (Py_ssize_t i = pos_args; i < pos_params_size; ++i) {
    PyObject* converter = PyTuple_GET_ITEM(sig->posparams, i); /* borrowed! */
    PyObject* pyarg = PyTuple_GET_ITEM(
      sig->posparams_defaults, i - sig->posparams_nmandatory); /* borrowed! */
    JsVal arg = Py2JsConverter_convert(converter, pyarg, proxies);
    FAIL_IF_JS_ERROR(arg);
    JsvArray_Push(jsargs, arg);
  }
  // positional varargs
  if (pos_args < nargs) {
    if (Py_IsNone(sig->varpos)) {
      goto set_args_error;
    }
    // varargs argument
    PyObject* converter = sig->varpos; /* borrowed! */
    for (Py_ssize_t i = pos_args; i < nargs; ++i) {
      JsVal arg = Py2JsConverter_convert(converter, pyargs[i], proxies);
      FAIL_IF_JS_ERROR(arg);
      JsvArray_Push(jsargs, arg);
    }
  }
  // Keyword arguments
  // Can skip if there are no keyword arguments and no keyword params (except a
  // possible **kwargs)
  Py_ssize_t nkwargs = kwnames == NULL ? 0 : PyTuple_GET_SIZE(kwnames);
  bool has_kwargs = (nkwargs > 0) || (PyTuple_GET_SIZE(sig->kwparam_names) > 0);
  if (!has_kwargs) {
    return jsargs;
  }
  // store kwargs into an object which we'll use as the last argument.
  JsVal kwargs = JsvObject_New();
  FAIL_IF_JS_ERROR(kwargs);
  uint64_t found_indices = 0;
  for (uint64_t i = 0, k = nargs; i < nkwargs; ++i, ++k) {
    PyObject* pyname = PyTuple_GET_ITEM(kwnames, i); /* borrowed! */
    Py_ssize_t kw_idx = find_keyword(sig->kwparam_names, pyname);
    PyObject* converter = NULL;
    if (kw_idx != -1) {
      // Found a designated keyword argument with this name
      converter =
        PyTuple_GET_ITEM(sig->kwparam_converters, kw_idx); /* borrowed! */
      found_indices |= (1Ull << kw_idx);
    } else if (!Py_IsNone(sig->varkwd)) {
      // Use **kwargs converter
      converter = sig->varkwd;
    } else {
      // Unknown keyword argument
      goto set_args_error;
    }
    JsVal jsname = python2js(pyname);
    FAIL_IF_JS_ERROR(jsname);
    JsVal arg = Py2JsConverter_convert(converter, pyargs[k], proxies);
    FAIL_IF_JS_ERROR(arg);
    FAIL_IF_MINUS_ONE(JsvObject_SetAttr(kwargs, jsname, arg));
  }
  // Fill in defaults for keyword parameters and check for missing param w/ no
  // default. Hypothetically could skip this loop if all missing params have
  // None default.
  for (uint64_t i = 0; i < PyTuple_GET_SIZE(sig->kwparam_names); i++) {
    if (found_indices & (1Ull << i)) {
      // user provided this argument
      continue;
    }
    PyObject* default_ =
      PyTuple_GET_ITEM(sig->kwparam_defaults, i); /* borrowed */
    if (default_ == no_default) {
      goto set_args_error;
    }
    if (Py_IsNone(default_)) {
      // Optimization: None default is same as leaving out key...
      // Perhaps we should also check the converter here?
      continue;
    }
    PyObject* pyname = PyTuple_GET_ITEM(sig->kwparam_names, i);
    PyObject* converter =
      PyTuple_GET_ITEM(sig->kwparam_converters, i); /* borrowed */
    JsVal jsname = python2js(pyname);
    FAIL_IF_JS_ERROR(jsname);
    JsVal arg = Py2JsConverter_convert(converter, default_, proxies);
    FAIL_IF_JS_ERROR(arg);
    FAIL_IF_MINUS_ONE(JsvObject_SetAttr(kwargs, jsname, arg));
  }
  JsvArray_Push(jsargs, kwargs);

  FAIL_IF_ERR_OCCURRED();
  return jsargs;
set_args_error: {
  // Calling the template function with the same args should raise an
  // appropriate error
  PyObject* res = PyObject_Vectorcall(sig->func, pyargs, nargsf, kwnames);
  if (res) {
    Py_CLEAR(res);
    PyErr_SetString(PyExc_SystemError, "Expected an error but none was raised");
    FAIL();
  }
  if (PyErr_ExceptionMatches(PyExc_TypeError)) {
    FAIL();
  }
  PyErr_SetString(PyExc_SystemError,
                  "Expected a TypeError but other type of error was raised");
  FAIL();
}
}

/**
 * __call__ overload for methods. Controlled by IS_CALLABLE.
 */
PyObject*
JsMethod_Vectorcall_impl(JsVal func,
                         JsVal receiver,
                         PyObject* sig,
                         PyObject* const* pyargs,
                         size_t nargsf,
                         PyObject* kwnames)
{
  FAIL_RETURN_VALUE(NULL);

  JsFuncSignature* call_sig = NULL;
  _Defer
  {
    Py_CLEAR(call_sig);
  };
  if (sig) {
    _Py_IDENTIFIER(func_to_sig);
    call_sig = (JsFuncSignature*)_PyObject_CallMethodIdOneArg(
      jsbind, &PyId_func_to_sig, sig);
    FAIL_IF_NULL(call_sig);
  }
  if (Py_IsNone((PyObject*)call_sig)) {
    Py_CLEAR(call_sig);
  }
  if (!call_sig) {
    call_sig = (JsFuncSignature*)Py_NewRef(default_signature);
  }

  JsVal jsresult = JS_ERROR;
  JsVal proxies = JsvArray_New();
  ON_FAIL({
    if (!JsvError_Check(jsresult) && pyproxy_Check(jsresult)) {
      // TODO: don't destroy proxies with roundtrip = true?
      JsvArray_Push(proxies, jsresult);
    }
    destroy_proxies(proxies, &PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL);
  });

  JsVal jsargs =
    JsMethod_ConvertArgs(call_sig, pyargs, nargsf, kwnames, proxies);
  FAIL_IF_JS_ERROR(jsargs);

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" while calling a JavaScript object"));
  _Defer
  {
    Py_LeaveRecursiveCall(/* " in JsMethod_Vectorcall" */);
  };

  if (call_sig->should_construct) {
    jsresult = JsvFunction_Construct(func, jsargs);
  } else {
    jsresult = JsvFunction_CallBound(func, receiver, jsargs);
  }
  FAIL_IF_JS_ERROR(jsresult);
  PyObject* result_converter = ((JsFuncSignature*)call_sig)->result;
  PyObject* pyresult =
    Js2PyConverter_convert(result_converter, jsresult, proxies);
  FAIL_IF_NULL(pyresult);

  return pyresult;
}

PyObject*
JsMethod_Construct_impl(JsVal func,
                        PyObject* sig,
                        PyObject* const* pyargs,
                        size_t nargs,
                        PyObject* kwnames)
{
  FAIL_RETURN_VALUE(NULL);
  JsVal proxies = JsvArray_New();
  _Defer
  {
    Py_LeaveRecursiveCall(/* " in JsMethod_Construct" */);
    Js_static_string(
      msg,
      "This borrowed proxy was automatically destroyed. Try using "
      "create_proxy or create_once_callable.");
    destroy_proxies(proxies, &msg);
  };

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" in JsMethod_Construct"));

  JsVal jsargs = JsMethod_ConvertArgs(
    (JsFuncSignature*)default_signature, pyargs, nargs, kwnames, proxies);
  FAIL_IF_JS_ERROR(jsargs);
  JsVal jsresult = JsvFunction_Construct(func, jsargs);
  FAIL_IF_JS_ERROR(jsresult);

  return js2python(jsresult);
}

int
jsproxy_call_init(PyObject* core_mod)
{
  FAIL_RETURN_VALUE(-1);
  FAIL_IF_MINUS_ONE(PyType_Ready(&JsFuncSignatureType));
  FAIL_IF_MINUS_ONE(PyObject_SetAttrString(
    core_mod, "JsFuncSignature", (PyObject*)&JsFuncSignatureType));

  return 0;
}
