#include <Python.h>

// Dummy function implementation
static PyObject* dummy(PyObject* self, PyObject* args) {
    return PyUnicode_FromString("dummy");
}

// Method definition table
static PyMethodDef DummyMethods[] = {
    {"dummy", dummy, METH_NOARGS, "Return a dummy string"},
    {NULL, NULL, 0, NULL}  // Sentinel
};

static PyModuleDef simplemodule = {
    PyModuleDef_HEAD_INIT,
    "dummy_nonpure",   // name of module
    NULL,       // module documentation, may be NULL
    -1,         // size of per-interpreter state of the module,
                // or -1 if the module keeps state in global variables.
    DummyMethods  // methods table
};

PyMODINIT_FUNC PyInit_dummy_nonpure(void) {
    return PyModule_Create(&simplemodule);
}