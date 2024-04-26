#include "Python.h"
#include "error_handling.h"
#include "js2python.h"
#include "jsproxy.h"
#include "pyproxy.h"

Js_static_string(PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL,
                 "This borrowed proxy was automatically destroyed at the "
                 "end of a function call. Try using "
                 "create_proxy or create_once_callable.");

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

// Deep js2py conversion for function call result.
PyObject*
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
  if (JsvNull_Check(proxies)) {
    // Nothing to do.
  } else if (destroy_args) {
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
finally:
  return pyresult;
}
