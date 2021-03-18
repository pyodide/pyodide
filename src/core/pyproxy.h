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
 * Wrap a Python object in a Javascript function that can be called once. After
 * being called, the reference count of the python object is automatically
 * decremented. The Proxy also has a "destroy" API that can decrement the
 * reference count without calling the function.
 */
JsRef
create_once_proxy(PyObject* obj);

int
pyproxy_init();

#endif /* PYPROXY_H */
