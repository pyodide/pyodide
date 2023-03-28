#define PY_SSIZE_T_CLEAN

#include "Python.h"
#include <emscripten.h>

long counter = 0;

void
inner_loop(void)
{
  if (counter < 100) {
    counter += 1;
  }
}

static PyObject*
main_loop(void)
{
  emscripten_set_main_loop(inner_loop, 0, 1);
  Py_RETURN_NONE;
}

static PyObject*
get_counter(void)
{
  return PyLong_FromLong(counter);
}

static PyMethodDef Methods[] = {
  { "main_loop", (PyCFunction)main_loop, METH_NOARGS },
  { "get_counter", (PyCFunction)get_counter, METH_NOARGS },
  { NULL, NULL, 0, NULL } /* Sentinel */
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "emscripten_loop_test",                   /* name of module */
  "Tests for the emscripten loop handling", /* module documentation, may be NULL
                                             */
  -1, /* size of per-interpreter state of the module,
         or -1 if the module keeps state in global variables. */
  Methods
};

PyMODINIT_FUNC
PyInit_emscripten_loop_test(void)
{
  PyObject* module_object = PyModule_Create(&module);
  return module_object;
}
