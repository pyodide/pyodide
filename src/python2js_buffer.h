#ifndef PYTHON2JS_BUFFER_H
#define PYTHON2JS_BUFFER_H

/** Utilities to convert Python buffer objects to Javascript.
 */

#include <Python.h>

/** Convert a Python buffer object to a Javascript object.
 *
 *  \param The Python object
 *  \return The Javascript object -- might be an Error object in the case of an
 *     exception.
 */
int
_python2js_buffer(PyObject* x);

#endif /* PYTHON2JS_BUFFER_H */
