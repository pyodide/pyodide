#ifndef PYTHON2JS_H
#define PYTHON2JS_H

/** Translate Python objects to Javascript.
 */
// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "hiwire.h"

/**
 * Convert a Python object to a Javascript object.
 *  \param x The Python object
 *  \return The Javascript object -- might be an Error object in the case of an
 *     exception.
 */
JsRef
python2js(PyObject* x);

/**
 * Convert a Python object to a Javascript object, copying standard collections
 * into javascript down to specified depth \param x The Python object \param
 * depth The maximum depth to copy \return The Javascript object -- might be an
 * Error object in the case of an exception.
 */
JsRef
python2js_with_depth(PyObject* x, int depth);

#endif /* PYTHON2JS_H */
