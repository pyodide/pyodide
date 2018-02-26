#include "pylocals.hpp"
#include "js2python.hpp"

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>

using emscripten::val;

////////////////////////////////////////////////////////////
// PyLocals
//
// This is an object designed to be used as a "locals" namespace dictionary.
// It first looks for things in its own internal dictionary, and failing that,
// looks in the Javascript global namespace.  This is a way of merging the
// Python and Javascript namespaces without fullying copying either one.

PyObject *locals = NULL;
PyObject *globals = NULL;
PyObject *original_globals = NULL;

typedef struct {
  PyObject_HEAD
  PyObject *locals;
} PyLocals;

static void PyLocals_dealloc(PyLocals *self) {
  Py_DECREF(self->locals);
  Py_TYPE(self)->tp_free((PyObject *)self);
}

static Py_ssize_t PyLocals_length(PyObject *o) {
  PyLocals *self = (PyLocals *)o;

  return PyDict_Size(self->locals);
}

PyObject* PyLocals_get(PyObject *o, PyObject *key) {
  PyLocals *self = (PyLocals *)o;

  {
    PyObject *str = PyObject_Str(key);
    if (str == NULL) {
      return NULL;
    }
    char *c = PyUnicode_AsUTF8(str);
    Py_DECREF(str);
  }

  PyObject *py_val = PyDict_GetItem(self->locals, key);
  if (py_val != NULL) {
    Py_INCREF(py_val);
    return py_val;
  }

  PyObject *str = PyObject_Str(key);
  if (str == NULL) {
    return NULL;
  }
  char *c = PyUnicode_AsUTF8(str);
  val v = val::global(c);
  Py_DECREF(str);
  return jsToPython(v);
}

int PyLocals_set(PyObject *o, PyObject *k, PyObject *v) {
  PyLocals *self = (PyLocals *)o;

  if (v == NULL) {
    // TODO: This might not actually be here to delete...
    return PyDict_DelItem(self->locals, k);
  } else {
    return PyDict_SetItem(self->locals, k, v);
  }
}

static PyMappingMethods PyLocals_as_mapping = {
  PyLocals_length,
  PyLocals_get,
  PyLocals_set
};

static PyTypeObject PyLocalsType = {
  .tp_name = "PyLocals",
  .tp_basicsize = sizeof(PyLocals),
  .tp_dealloc = (destructor)PyLocals_dealloc,
  .tp_as_mapping = &PyLocals_as_mapping,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = "A proxy that looks in a dict first, otherwise in the global JS namespace"
};

static PyObject *PyLocals_cnew(PyObject *d)
{
  PyLocals *self;
  self = (PyLocals *)PyLocalsType.tp_alloc(&PyLocalsType, 0);
  if (self != NULL) {
    Py_INCREF(d);
    self->locals = d;
  }

  return (PyObject *)self;
}

int PyLocals_Ready() {
  if (PyType_Ready(&PyLocalsType) < 0)
    return 1;

  PyObject *m = PyImport_AddModule("__main__");
  if (m == NULL)
    return 1;
  globals = PyModule_GetDict(m);

  m = PyImport_AddModule("builtins");
  PyDict_Update(globals, PyModule_GetDict(m));

  original_globals = PyDict_Copy(globals);

  locals = PyLocals_cnew(globals);
  if (locals == NULL)
    return 1;

  return 0;
}
