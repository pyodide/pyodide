/**
 * A Python object that wraps a JavaScript object. Used to allow JavaScript
 * objects to be passed into Python.
 */
#ifndef JSPROXY_H
#define JSPROXY_H
// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "hiwire.h"

/**
 *
 */
int
JsProxy_compute_typeflags(JsRef obj);

PyObject*
JsProxy_create_with_type(int type_flags, JsRef object, JsRef this);

PyObject*
JsProxy_create_objmap(JsRef object, bool objmap);

/**
 * Make a new JsProxy.
 * @param object The JavaScript object.
 * @param this If object is a function, the value of this to be used when
 *        calling it.
 * @return The Python object wrapping the JavaScript object.
 */
PyObject*
JsProxy_create_with_this(JsRef object, JsRef this);

/**
 * Make a new JsProxy.
 * @param v The JavaScript object.
 * @return The Python object wrapping the JavaScript object.
 */
PyObject*
JsProxy_create(JsRef v);

/**
 * Check if a Python object is a JsProxy.
 * @param x The Python object
 * @return true if the object is a JsProxy.
 */
bool
JsProxy_Check(PyObject* x);

/**
 * Grab the underlying JavaScript object from the JsProxy.
 * @param x The JsProxy object. Will fatally fail if it isn't a JsProxy.
 * @return The JavaScript object.
 */
JsRef
JsProxy_AsJs(PyObject* x);

/** Initialize global state for JsProxy functionality. */
int
JsProxy_init(PyObject* core_module);

#endif /* JSPROXY_H */
