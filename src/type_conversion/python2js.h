#ifndef PYTHON2JS_H
#define PYTHON2JS_H

/** Utilities to convert Python objects to Javascript.
 */

#include <Python.h>

/** Convert the active Python exception into a Javascript Error object.
 *  \return A Javascript Error object
 */
int
pythonexc2js();

/** Convert a Python object to a Javascript object.
 *  \param The Python object
 *  \return The Javascript object -- might be an Error object in the case of an
 *     exception.
 */
int
python2js_copy(PyObject* x);


/** Will python2js_copy do anything different than python2js_nocopy? 
 *  \param The Python object
 *  \return boolean, whether python2js_copy will make any progress. 
 */
int
python2js_can_copy(PyObject* x);

/** Convert a Python object to a Javascript object.
 *  \param The Python object
 *  \return The Javascript object -- might be an Error object in the case of an
 *     exception.
 */
int
python2js_nocopy(PyObject* x);

/** Set up the global state for this module.
 */
int
python2js_init();

#endif /* PYTHON2JS_H */
