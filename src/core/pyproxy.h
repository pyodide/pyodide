#ifndef PYPROXY_H
#define PYPROXY_H
#include "Python.h"

/** Makes Python objects usable from Javascript.
 */

// This implements the Javascript Proxy handler interface as defined here:
//     https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy

JsRef
pyproxy_use(PyObject* obj);

JsRef
pyproxy_new(PyObject* obj);

int
pyproxy_init();

#endif /* PYPROXY_H */
