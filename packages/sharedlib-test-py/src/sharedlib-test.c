#define PY_SSIZE_T_CLEAN
#include "sharedlibtest.h"
#include <Python.h>

static PyObject*
one(PyObject* self)
{
  Py_RETURN_NONE;
}

static PyObject*
do_the_thing_pywrapper(PyObject* self, PyObject* args)
{
  int a, b;
  if (!PyArg_ParseTuple(args, "ii:do_the_thing", &a, &b)) {
    return NULL;
  }
  int res = do_the_thing(a, b);
  return PyLong_FromLong(res);
}

// These two structs are the same but it's important that they have to be
// duplicated here or else we miss test coverage.
static PyMethodDef Test_Functions[] = {
  { "do_the_thing", do_the_thing_pywrapper, METH_VARARGS },
  { 0 },
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "sharedlib_test",                   /* name of module */
  "Tests for shared library loading", /* module documentation, may be NULL */
  -1, /* size of per-interpreter state of the module,
         or -1 if the module keeps state in global variables. */
  Test_Functions
};

PyMODINIT_FUNC
PyInit_sharedlib_test(void)
{
  return PyModule_Create(&module);
}
