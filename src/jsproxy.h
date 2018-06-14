#ifndef JSPROXY_H
#define JSPROXY_H

/** A Python object that a Javascript object inside. Used for any non-standard
 *  data types that are passed from Javascript to Python.
 */

#include <Python.h>

/** Make a new JsProxy.
 *  \param v The Javascript object.
 *  \return The Python object wrapping the Javascript object.
 */
PyObject*
JsProxy_cnew(int v);

/** Check if a Python object is a JsProxy object.
 *  \param x The Python object
 *  \return 1 if the object is a JsProxy object.
 */
int
JsProxy_Check(PyObject* x);

/** Grab the underlying Javascript object from the JsProxy object.
 *  \param x The JsProxy object.  Must confirm that it is a JsProxy object using
 *    JsProxy_Check. \return The Javascript object.
 */
int
JsProxy_AsJs(PyObject* x);

/** Initialize global state for the JsProxy functionality. */
int
JsProxy_init();

#endif /* JSPROXY_H */
