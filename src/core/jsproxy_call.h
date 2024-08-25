#include "Python.h"
#include "jslib.h"

PyObject*
JsMethod_Vectorcall_impl(JsVal func,
                         JsVal receiver,
                         PyObject* sig,
                         PyObject* const* pyargs,
                         size_t nargsf,
                         PyObject* kwnames);

PyObject*
JsMethod_Construct_impl(JsVal func,
                        PyObject* sig,
                        PyObject* const* pyargs,
                        size_t nargs,
                        PyObject* kwnames);
