#ifndef PYPROXY_H
#define PYPROXY_H
#define PY_SSIZE_T_CLEAN
#include "Python.h"

/**
 * Makes Python objects usable from JavaScript.
 */

// This implements the JavaScript Proxy handler interface as defined here:
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy

JsVal
pyproxy_new_ex(PyObject* obj,
               bool capture_this,
               bool roundtrip,
               bool register,
               bool is_json_adaptor);

JsVal
pyproxy_new(PyObject* obj);

/**
 * Check if x is a PyProxy.
 *
 * Fatally fails if x is not NULL or a valid JsRef.
 */
int
pyproxy_Check(JsVal x);

/**
 * If x is a PyProxy, return a borrowed version of the wrapped PyObject. Returns
 * NULL if x is NULL or a valid JsRef which is not a pyproxy. Fatally fails if x
 * is not NULL or a valid JsRef.
 */
PyObject*
pyproxy_AsPyObject(JsVal x);

/**
 * Destroy a list of PyProxies.
 */
void
destroy_proxies(JsVal proxies, Js_Identifier* msg);

void
gc_register_proxies(JsVal proxies);

/**
 * Destroy a PyProxy.
 */
void
destroy_proxy(JsVal proxy, Js_Identifier* msg);

/**
 * Wrap a Python callable in a JavaScript function that can be called once.
 * After being called, the reference count of the python object is automatically
 * decremented. The Proxy also has a "destroy" API that can decrement the
 * reference count without calling the function.
 */
JsVal
create_once_callable(PyObject* obj, bool may_syncify);

/**
 * Wrap a pair of Python callables in a JavaScript function that can be called
 * once between the two of them. After being called, the reference counts of
 * both python objects are automatically decremented. The wrappers also have a
 * "destroy" API that can decrement the reference counts without calling the
 * function. Intended for use with `promise.then`.
 */
JsVal
create_promise_handles(PyObject* onfulfilled,
                       PyObject* onrejected,
                       JsVal done_callback,
                       PyObject* js2py_converter);

int
pyproxy_init(PyObject* core);

bool
py_is_awaitable(PyObject* o);

// These are defined as an enum in Python.h but we want to use them in
// pyproxy.ts.
#define PYGEN_NEXT 1
#define PYGEN_RETURN 0
#define PYGEN_ERROR -1

#endif /* PYPROXY_H */
