#ifndef PYTHON2JS_H
#define PYTHON2JS_H

/** Utilities to convert Python objects to Javascript.
 */
// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "hiwire.h"

JsRef
wrap_exception();

/** Convert the active Python exception into a Javascript Error object
 *  and print it to the console.
 */
void
pythonexc2js();

/** Convert a Python object to a Javascript object.
 *  \param The Python object
 *  \return The Javascript object -- might be an Error object in the case of an
 *     exception.
 */
JsRef
python2js(PyObject* x);

/** Set up the global state for this module.
 */
int
python2js_init();

#endif /* PYTHON2JS_H */
