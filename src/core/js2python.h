#ifndef JS2PYTHON_H
#define JS2PYTHON_H

/**
 * Translate JavaScript objects to Python objects.
 */
#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "hiwire.h"

/** Convert a JavaScript object to a Python object.
 *  \param x The JavaScript object.
 *  \return The Python object. New reference. If NULL, a Python exception
 *    occurred during the conversion, and the Python exception API should be
 *    used to obtain the exception.
 */
PyObject*
js2python(JsRef x);

PyObject*
js2python_convert(JsRef x, int depth);

/** Initialize any global variables used by this module. */
int
js2python_init();

#endif /* JS2PYTHON_H */
