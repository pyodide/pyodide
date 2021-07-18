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

int
pyproxy_Check(JsRef x);

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
create_promise_handles(PyObject* onfulfilled, PyObject* onrejected);

int
pyproxy_init();

#endif /* PYPROXY_H */
