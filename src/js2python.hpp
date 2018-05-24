#ifndef JS2PYTHON_H
#define JS2PYTHON_H

/**
 * Utilities to convert Javascript objects to Python objects.
 */

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>
#include <Python.h>

/** Convert a Javascript object to a Python object.
 *  \param x The Javascript object.
 *  \return The Python object. New reference. If NULL, a Python exception
 *    occurred during the conversion, and the Python exception API should be used
 *    to obtain the exception.
 */
PyObject *jsToPython(emscripten::val x);

/** Convert an Array of Javascript arguments to a Python tuple of arguments.
 *  \param args A Javascript Array of arguments
 *  \return The tuple of Python objects. New reference. If NULL, a Python exception
 *    occurred during the conversion, and the Python exception API should be used
 *    to obtain the exception.
 */
PyObject *jsToPythonArgs(emscripten::val args);

/** Convert an Object of Javascript "keyword arguments" to a Python dictionary of arguments.
 *  \param kwargs A Javascript Object of arguments
 *  \return The dict of Python objects. New reference. If NULL, a Python exception
 *    occurred during the conversion, and the Python exception API should be used
 *    to obtain the exception.
 */
PyObject *jsToPythonKwargs(emscripten::val kwargs);

/** Initialize any global variables used by this module. */
int jsToPython_Ready();

#endif /* JS2PYTHON_H */
