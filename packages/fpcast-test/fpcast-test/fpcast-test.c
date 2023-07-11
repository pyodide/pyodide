#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject*
zero(void)
{
  Py_RETURN_NONE;
}

static PyObject*
one(PyObject* self)
{
  Py_RETURN_NONE;
}

static PyObject*
two(PyObject* self, PyObject* args)
{
  Py_RETURN_NONE;
}

static PyObject*
three(PyObject* self, PyObject* args, PyObject* kwargs)
{
  Py_RETURN_NONE;
}

static int
set_two(PyObject* self, PyObject* value)
{
  return 0;
}

/**
 * This get-set pair test that the getter/setter call trampolines interact
 * correctly with stack switching. They are used in `src/tests/test_syncify.py`.
 * We see that the descriptor trampoline is used because the signatures don't
 * take a closure argument. We assign `getset_func` to be a function that calls
 * `syncify()` so that if the trampoline uses JS frames then the stack switch
 * would fail.
 */
PyObject* getset_func = NULL;

static PyObject*
get_one_call(PyObject* self)
{
  return PyObject_CallNoArgs(getset_func);
}

static int
set_two_call(PyObject* self, PyObject* value)
{
  Py_CLEAR(getset_func);
  Py_INCREF(value);
  getset_func = value;
  if (value == Py_None) {
    return 0;
  }
  PyObject* result = PyObject_CallNoArgs(value);
  Py_XDECREF(result);
  return result ? 0 : -1;
}

// These two structs are the same but it's important that they have to be
// duplicated here or else we miss test coverage.
static PyMethodDef Test_Functions[] = {
  { "noargs0", (PyCFunction)zero, METH_NOARGS },
  { "noargs1", (PyCFunction)one, METH_NOARGS },
  { "noargs2", (PyCFunction)two, METH_NOARGS },
  { "noargs3", (PyCFunction)three, METH_NOARGS },

  { "varargs0", (PyCFunction)zero, METH_VARARGS },
  { "varargs1", (PyCFunction)one, METH_VARARGS },
  { "varargs2", (PyCFunction)two, METH_VARARGS },
  { "varargs3", (PyCFunction)three, METH_VARARGS },

  { "kwargs0", (PyCFunction)zero, METH_VARARGS | METH_KEYWORDS },
  { "kwargs1", (PyCFunction)one, METH_VARARGS | METH_KEYWORDS },
  { "kwargs2", (PyCFunction)two, METH_VARARGS | METH_KEYWORDS },
  { "kwargs3", (PyCFunction)three, METH_VARARGS | METH_KEYWORDS },
  { NULL, NULL, 0, NULL }
};

static PyMethodDef Test_Methods[] = {
  { "noargs0", (PyCFunction)zero, METH_NOARGS },
  { "noargs1", (PyCFunction)one, METH_NOARGS },
  { "noargs2", (PyCFunction)two, METH_NOARGS },
  { "noargs3", (PyCFunction)three, METH_NOARGS },

  { "varargs0", (PyCFunction)zero, METH_VARARGS },
  { "varargs1", (PyCFunction)one, METH_VARARGS },
  { "varargs2", (PyCFunction)two, METH_VARARGS },
  { "varargs3", (PyCFunction)three, METH_VARARGS },

  { "kwargs0", (PyCFunction)zero, METH_VARARGS | METH_KEYWORDS },
  { "kwargs1", (PyCFunction)one, METH_VARARGS | METH_KEYWORDS },
  { "kwargs2", (PyCFunction)two, METH_VARARGS | METH_KEYWORDS },
  { "kwargs3", (PyCFunction)three, METH_VARARGS | METH_KEYWORDS },
  { NULL, NULL, 0, NULL }
};

static PyGetSetDef Test_GetSet[] = {
  { "getset0", .get = (getter)zero },
  { "getset1", .get = (getter)one, .set = (setter)set_two },
  { "getset_jspi_test",
    .get = (getter)get_one_call,
    .set = (setter)set_two_call },
  { NULL }
};

static PyTypeObject TestType = {
  .tp_name = "TestType",
  .tp_basicsize = sizeof(PyObject),
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = PyDoc_STR("A test type"),
  .tp_methods = Test_Functions,
  .tp_getset = Test_GetSet,
  .tp_new = PyType_GenericNew,
};

static PyTypeObject Callable0 = {
  .tp_name = "Callable0",
  .tp_basicsize = sizeof(PyObject),
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = PyDoc_STR("A test type"),
  .tp_call = (ternaryfunc)zero,
  .tp_new = PyType_GenericNew,
};

static PyTypeObject Callable1 = {
  .tp_name = "Callable1",
  .tp_basicsize = sizeof(PyObject),
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = PyDoc_STR("A test type"),
  .tp_call = (ternaryfunc)one,
  .tp_new = PyType_GenericNew,
};

static PyTypeObject Callable2 = {
  .tp_name = "Callable2",
  .tp_basicsize = sizeof(PyObject),
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = PyDoc_STR("A test type"),
  .tp_call = (ternaryfunc)two,
  .tp_new = PyType_GenericNew,
};

static PyTypeObject Callable3 = {
  .tp_name = "Callable3",
  .tp_basicsize = sizeof(PyObject),
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = PyDoc_STR("A test type"),
  .tp_call = (ternaryfunc)three,
  .tp_new = PyType_GenericNew,
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "fpcast_test",                   /* name of module */
  "Tests for the fpcast handling", /* module documentation, may be NULL */
  -1, /* size of per-interpreter state of the module,
         or -1 if the module keeps state in global variables. */
  Test_Methods
};

PyMODINIT_FUNC
PyInit_fpcast_test(void)
{
  PyObject* module_object = PyModule_Create(&module);
  PyModule_AddType(module_object, &TestType);
  PyModule_AddType(module_object, &Callable0);
  PyModule_AddType(module_object, &Callable1);
  PyModule_AddType(module_object, &Callable2);
  PyModule_AddType(module_object, &Callable3);
  return module_object;
}
