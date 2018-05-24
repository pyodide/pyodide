#ifndef PYTHON2JS_H
#define PYTHON2JS_H

/** Utilities to convert Python objects to Javascript.
 */

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>
#include <Python.h>

/** Convert the active Python exception into a Javascript Error object.
 *  \return A Javascript Error object
 */
emscripten::val pythonExcToJs();

/** Convert a Python object to a Javascript object.
 *  \param The Python object
 *  \return The Javascript object -- might be an Error object in the case of an exception.
 */
emscripten::val pythonToJs(PyObject *x);

/** Set up the global state for this module.
 */
int pythonToJs_Ready();

#endif /* PYTHON2JS_H */
