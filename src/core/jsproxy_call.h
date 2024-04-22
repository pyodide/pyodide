#include "Python.h"
#include "jslib.h"

PyObject*
wrap_promise(JsVal promise, JsVal done_callback);

PyObject*
JsMethod_Vectorcall_impl(JsVal target,
                         JsVal thisarg,
                         PyObject* const* pyargs,
                         size_t nargsf,
                         PyObject* kwnames);

PyObject*
JsMethod_Construct_impl(JsVal target,
                        PyObject* const* pyargs,
                        Py_ssize_t nargs,
                        PyObject* kwnames);
