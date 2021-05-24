#ifndef PYPROXY_H
#define PYPROXY_H
#define PY_SSIZE_T_CLEAN
#include "Python.h"

/**
 * Makes Python objects usable from Javascript.
 */

// This implements the Javascript Proxy handler interface as defined here:
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy

JsRef
pyproxy_new(PyObject* obj);

/**
 * Check if x is a PyProxy.
 *
 * Will fatally fail if x is not NULL or a valid JsRef.
 */
int
pyproxy_Check(JsRef x);

/**
 * Destroy a list of PyProxies. Steals the reference to the list.
 */
errcode
destroy_proxies(JsRef proxies_id, char* msg);

/**
 * Mark a PyProxy as borrowed. Will disable user attempts to destroy it.
 */
int
pyproxy_mark_borrowed(JsRef proxy);

/**
 * Mark a list of PyProxies as borrowed.
 */
int
pyproxies_mark_borrowed(JsRef proxies);

/**
 * Does hiwire_decref on x and also if x is a PyProxy destroy x.
 *
 * Used in finally blocks. Since it would be inconvenient to check for errors in
 * this context, will raise a fatal error if x not a valid JsRef.
 */
void
pyproxy_destroy_and_decref(JsRef x);

/**
 * Variant of hiwire_CLEAR that also destroys a PyProxy if x is one.
 *
 * x must either be a valid JsRef or NULL, otherwise will raise a fatal error.
 */
#define pyproxy_CLEAR(x)                                                       \
  do {                                                                         \
    pyproxy_destroy_and_decref(x);                                             \
    x = NULL;                                                                  \
  } while (0)

/**
 * Wrap a Python callable in a Javascript function that can be called once.
 * After being called, the reference count of the python object is automatically
 * decremented. The Proxy also has a "destroy" API that can decrement the
 * reference count without calling the function.
 */
JsRef
create_once_callable(PyObject* obj);

/**
 * Wrap a pair of Python callables in a Javascript function that can be called
 * once between the two of them. After being called, the reference counts of
 * both python objects are automatically decremented. The wrappers also have a
 * "destroy" API that can decrement the reference counts without calling the
 * function. Intended for use with `promise.then`.
 */
JsRef
create_promise_handles(PyObject* onfulfilled,
                       PyObject* onrejected,
                       JsRef done_callback_id);

int
pyproxy_init();

#endif /* PYPROXY_H */
