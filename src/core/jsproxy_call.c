#include "Python.h"
#include "error_handling.h"
#include "js2python.h"
#include "jslib.h"
#include "pyproxy.h"
#include "python2js.h"

_Py_IDENTIFIER(create_future);
_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(set_exception);
_Py_IDENTIFIER(set_result);
Js_IDENTIFIER(then);
extern PyObject* asyncio_mod;

Js_static_string(PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL,
                 "This borrowed proxy was automatically destroyed at the "
                 "end of a function call. Try using "
                 "create_proxy or create_once_callable.");

/**
 * Create a Future attached to the given Promise. When the promise is
 * resolved/rejected, the status of the future is set accordingly and
 * done_callback is called.
 */
PyObject*
wrap_promise(JsVal promise, JsVal done_callback)
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

  promise = JsvPromise_Resolve(promise);
  FAIL_IF_JS_NULL(promise);
  JsVal promise_handles =
    create_promise_handles(set_result, set_exception, done_callback);
  FAIL_IF_JS_NULL(promise_handles);
  FAIL_IF_JS_NULL(JsvObject_CallMethodId(promise, &JsId_then, promise_handles));

  success = true;
finally:
  Py_CLEAR(loop);
  Py_CLEAR(set_result);
  Py_CLEAR(set_exception);
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

/**
 * Prepare arguments from a `METH_FASTCALL | METH_KEYWORDS` Python function to a
 * JavaScript call. We call `python2js` on each argument. Any PyProxy *created*
 * by `python2js` is stored into the `proxies` list to be destroyed later (if
 * the argument is a PyProxy created with `create_proxy` it won't be recorded
 * for destruction).
 */
static JsVal
JsMethod_ConvertArgs(PyObject* const* pyargs,
                     Py_ssize_t nargs,
                     PyObject* kwnames,
                     JsVal proxies)
{
  JsVal jsargs = JS_NULL;
  JsVal kwargs;

  jsargs = JsvArray_New();
  for (Py_ssize_t i = 0; i < nargs; ++i) {
    JsVal arg = python2js_track_proxies(pyargs[i], proxies, false);
    FAIL_IF_JS_NULL(arg);
    JsvArray_Push(jsargs, arg);
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
    goto finally;
  }

  // store kwargs into an object which we'll use as the last argument.
  kwargs = JsvObject_New();
  FAIL_IF_JS_NULL(kwargs);
  Py_ssize_t nkwargs = PyTuple_Size(kwnames);
  for (Py_ssize_t i = 0, k = nargs; i < nkwargs; ++i, ++k) {
    PyObject* pyname = PyTuple_GET_ITEM(kwnames, i); /* borrowed! */
    JsVal jsname = python2js(pyname);
    JsVal arg = python2js_track_proxies(pyargs[k], proxies, false);
    FAIL_IF_JS_NULL(arg);
    FAIL_IF_MINUS_ONE(JsvObject_SetAttr(kwargs, jsname, arg));
  }
  JsvArray_Push(jsargs, kwargs);

finally:
  return jsargs;
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

/**
 * __call__ overload for methods. Controlled by IS_CALLABLE.
 */
PyObject*
JsMethod_Vectorcall_impl(JsVal target,
                         JsVal thisarg,
                         PyObject* const* pyargs,
                         size_t nargsf,
                         PyObject* kwnames)
{
  bool success = false;
  JsVal jsresult = JS_NULL;
  bool destroy_args = true;
  PyObject* pyresult = NULL;
  JsVal proxies = JsvArray_New();

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" while calling a JavaScript object"));
  JsVal jsargs =
    JsMethod_ConvertArgs(pyargs, PyVectorcall_NARGS(nargsf), kwnames, proxies);
  FAIL_IF_JS_NULL(jsargs);
  jsresult = JsvFunction_CallBound(target, thisarg, jsargs);
  FAIL_IF_JS_NULL(jsresult);
  // various cases where we want to extend the lifetime of the arguments:
  // 1. if the return value is a promise we extend arguments lifetime until the
  //    promise resolves.
  // 2. If the return value is a sync or async generator we extend the lifetime
  //    of the arguments until the generator returns.
  bool is_promise = JsvPromise_Check(jsresult);
  bool is_generator = !is_promise && JsvGenerator_Check(jsresult);
  bool is_async_generator =
    !is_promise && !is_generator && JsvAsyncGenerator_Check(jsresult);
  destroy_args = (!is_promise) && (!is_generator) && (!is_async_generator);
  if (is_generator) {
    jsresult = wrap_generator(jsresult, proxies);
  } else if (is_async_generator) {
    jsresult = wrap_async_generator(jsresult, proxies);
  }
  FAIL_IF_JS_NULL(jsresult);
  if (is_promise) {
    // Since we will destroy the result of the Promise when it resolves we deny
    // the user access to the Promise (which would destroyed proxy exceptions).
    // Instead we return a Future. When the promise is ready, we resolve the
    // Future with the result from the Promise and destroy the arguments and
    // result.
    pyresult = wrap_promise(jsresult, get_async_js_call_done_callback(proxies));
  } else {
    pyresult = js2python(jsresult);
  }
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  Py_LeaveRecursiveCall(/* " in JsMethod_Vectorcall" */);
  if (!success || destroy_args) {
    // If we succeeded and the result was a promise then we destroy the
    // arguments in async_done_callback instead of here. Otherwise, destroy the
    // arguments and return value now.
    if (!JsvNull_Check(jsresult) && pyproxy_Check(jsresult)) {
      // TODO: don't destroy proxies with roundtrip = true?
      JsvArray_Push(proxies, jsresult);
    }
    destroy_proxies(proxies, &PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL);
  } else {
    gc_register_proxies(proxies);
  }
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

/**
 * jsproxy.new implementation. Controlled by IS_CALLABLE.
 *
 * This does Reflect.construct(this, args). In other words, this treats the
 * JsMethod as a JavaScript class, constructs a new JavaScript object of that
 * class and returns a new JsProxy wrapping it. Similar to `new this(args)`.
 */
PyObject*
JsMethod_Construct_impl(JsVal target,
                        PyObject* const* pyargs,
                        Py_ssize_t nargs,
                        PyObject* kwnames)
{
  bool success = false;
  PyObject* pyresult = NULL;
  JsVal proxies = JsvArray_New();

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" in JsMethod_Construct"));

  JsVal jsargs = JsMethod_ConvertArgs(pyargs, nargs, kwnames, proxies);
  FAIL_IF_JS_NULL(jsargs);
  JsVal jsresult = JsvFunction_Construct(target, jsargs);
  FAIL_IF_JS_NULL(jsresult);
  pyresult = js2python(jsresult);
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  Py_LeaveRecursiveCall(/* " in JsMethod_Construct" */);
  Js_static_string(msg,
                   "This borrowed proxy was automatically destroyed. Try using "
                   "create_proxy or create_once_callable.");
  destroy_proxies(proxies, &msg);
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}
