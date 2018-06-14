#ifndef JS2PYTHON_H
#define JS2PYTHON_H

/**
 * Utilities to convert Javascript objects to Python objects.
 */

#include <Python.h>

/** Convert a Javascript object to a Python object.
 *  \param x The Javascript object.
 *  \return The Python object. New reference. If NULL, a Python exception
 *    occurred during the conversion, and the Python exception API should be
 *    used to obtain the exception.
 */
PyObject*
js2python(int x);

/** Initialize any global variables used by this module. */
int
js2python_init();

#endif /* JS2PYTHON_H */
