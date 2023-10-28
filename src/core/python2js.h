#ifndef PYTHON2JS_H
#define PYTHON2JS_H

/** Translate Python objects to JavaScript.
 */
// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "hiwire.h"

/**
 * Do a shallow conversion from python to JavaScript. Convert immutable types
 * with equivalent JavaScript immutable types, but all other types are proxied.
 */
JsVal
python2js(PyObject* x);

/**
 * Like python2js except in the handling of PyProxy creation.
 *
 * If proxies is NULL, will throw an error instead of creating a PyProxy.
 * Otherwise, proxies should be an Array and python2js_track_proxies will add
 * the proxy to the array if one is created.
 */
JsVal
python2js_track_proxies(PyObject* x, JsVal proxies, bool gc_register);

/**
 * Convert a Python object to a JavaScript object, copying standard collections
 * into javascript down to specified depth
 * \param x The Python object
 * \param depth The maximum depth to copy
 * \param proxies If this is Null, will raise an error if we have no JavaScript
 *        conversion for a Python object. If not NULL, should be a JavaScript
 *        list. We will add all PyProxies created to the list.
 * \return The JavaScript object -- might be an Error object in the case of an
 *         exception.
 */
JsVal
python2js_with_depth(PyObject* x, int depth, JsVal proxies);

/**
 * dict_converter should be a JavaScript function that converts an Iterable of
 * pairs into the desired JavaScript object. If dict_converter is NULL, we use
 * python2js_with_depth which converts dicts to Map (the default)
 */
JsVal
python2js_custom(PyObject* x,
                 int depth,
                 JsVal proxies,
                 JsVal dict_converter,
                 JsVal default_converter);

int
python2js_init(PyObject* core);

#endif /* PYTHON2JS_H */
