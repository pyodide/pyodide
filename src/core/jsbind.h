#include "Python.h"
#include "jslib.h"

JsVal
Py2JsConverter_convert(PyObject* converter, PyObject* pyval, JsVal proxies);

PyObject*
Js2PyConverter_convert(PyObject* converter, JsVal jsval, JsVal proxies);

extern PyObject* jsbind;
extern PyObject* default_signature;
extern PyObject* no_default;
