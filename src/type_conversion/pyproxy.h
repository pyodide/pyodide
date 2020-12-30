#ifndef PYPROXY_H
#define PYPROXY_H

/** Makes Python objects usable from Javascript.
 */

// This implements the Javascript Proxy handler interface as defined here:
//     https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy

HwRef
pyproxy_use(PyObject* obj);

HwRef
pyproxy_new(PyObject* obj);

int
pyproxy_init();

#endif /* PYPROXY_H */
