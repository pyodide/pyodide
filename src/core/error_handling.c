void
PyodideErr_SetJsError(JsRef err)
{
  PyObject* py_err = JsProxy_new_error(err);
  PyErr_SetObject((PyObject*)(py_err->ob_type), py_err);
}
