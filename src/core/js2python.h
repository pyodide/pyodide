#ifndef JS2PYTHON_H
#define JS2PYTHON_H

/**
 * Translate JavaScript objects to Python objects.
 */
#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "jslib.h"

/**
 * Convert a JavaScript object to a Python object.
 *  \param x The JavaScript object.
 *  \return The Python object resulting from the conversion. Returns NULL and
 *    sets the Python error indicator if a conversion error occurs.
 */
PyObject*
js2python(JsVal x);

PyObject*
js2python_immutable(JsVal x);

PyObject*
js2python_convert(JsVal x, int depth, JsVal defaultConverter);

/** Initialize any global variables used by this module. */
int
js2python_init();

extern int compat_null_to_none;

#endif /* JS2PYTHON_H */
