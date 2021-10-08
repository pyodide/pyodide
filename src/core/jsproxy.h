#ifndef JSPROXY_H
#define JSPROXY_H
// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "hiwire.h"

/** A Python object that a JavaScript object inside. Used for any non-standard
 *  data types that are passed from JavaScript to Python.
 */

/** Make a new JsProxy.
 *  \param v The JavaScript object.
 *  \return The Python object wrapping the JavaScript object.
 */
PyObject*
JsProxy_create(JsRef v);

PyObject*
JsProxy_create_with_this(JsRef object, JsRef this);

/** Check if a Python object is a JsProxy object.
 *  \param x The Python object
 *  \return true if the object is a JsProxy object.
 */
bool
JsProxy_Check(PyObject* x);

/** Grab the underlying JavaScript object from the JsProxy object.
 *  \param x The JsProxy object.  Must confirm that it is a JsProxy object using
 *    JsProxy_Check. \return The JavaScript object.
 */
JsRef
JsProxy_AsJs(PyObject* x);

/**
 * obj must be a JsProxy of a buffer (we do no checking!)
 * Make a new Python Buffer object and copy the data from obj into
 *
 */
PyObject*
JsBuffer_CloneIntoPython(JsRef jsbuffer,
                         Py_ssize_t byteLength,
                         char* format,
                         Py_ssize_t itemsize);

/** Check if a Python object is a JsException object.
 *  \param x The Python object
 *  \return 1 if the object is a JsException object.
 */
bool
JsException_Check(PyObject* x);

/** Grab the underlying JavaScript error from the JsException object.
 *  \param x The JsProxy object.  Must confirm that it is a JsException object
 * using JsProxy_Check. \return The JavaScript object.
 */
JsRef
JsException_AsJs(PyObject* x);

/** Initialize global state for the JsProxy functionality. */
int
JsProxy_init(PyObject* core_module);

#endif /* JSPROXY_H */
