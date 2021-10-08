#ifndef PYTHON2JS_BUFFER_H
#define PYTHON2JS_BUFFER_H

/** Utilities to convert Python buffer objects to JavaScript.
 */
// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include "hiwire.h"

/** Convert a Python buffer object to a JavaScript object.
 *
 *  \param The Python object
 *  \return The JavaScript object -- might be an Error object in the case of an
 *     exception.
 */
JsRef
_python2js_buffer(PyObject* x);

errcode
python2js_buffer_init();

#endif /* PYTHON2JS_BUFFER_H */
