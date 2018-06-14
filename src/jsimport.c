#include "jsimport.h"

#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"

static PyObject* original__import__;
PyObject* globals = NULL;
PyObject* original_globals = NULL;

typedef struct
{
  PyObject_HEAD
} JsImport;

static PyObject*
JsImport_Call(PyObject* self, PyObject* args, PyObject* kwargs)
{
  PyObject* name = PyTuple_GET_ITEM(args, 0);
  if (PyUnicode_CompareWithASCIIString(name, "js") == 0) {
    PyObject* locals = PyTuple_GET_ITEM(args, 2);
    PyObject* fromlist = PyTuple_GET_ITEM(args, 3);
    Py_ssize_t n = PySequence_Size(fromlist);
    PyObject* jsmod = PyModule_New("js");
    PyObject* d = PyModule_GetDict(jsmod);

    int is_star = 0;
    if (n == 1) {
      PyObject* firstfromlist = PySequence_GetItem(fromlist, 0);
      if (PyUnicode_CompareWithASCIIString(firstfromlist, "*") == 0) {
        is_star = 1;
      }
      Py_DECREF(firstfromlist);
    }

    if (is_star) {
      PyErr_SetString(PyExc_ImportError, "'import *' not supported for js");
      return NULL;
    } else {
      for (Py_ssize_t i = 0; i < n; ++i) {
        PyObject* key = PySequence_GetItem(fromlist, i);
        if (key == NULL) {
          return NULL;
        }
        char* c = PyUnicode_AsUTF8(key);
        if (c == NULL) {
          Py_DECREF(key);
          return NULL;
        }
        int jsval = hiwire_get_global((int)c);
        PyObject* pyval = js2python(jsval);
        hiwire_decref(jsval);
        if (PyDict_SetItem(d, key, pyval)) {
          Py_DECREF(key);
          Py_DECREF(pyval);
          return NULL;
        }
        Py_DECREF(key);
        Py_DECREF(pyval);
      }
    }

    return jsmod;
  } else {
    // Fallback to the standard Python import
    return PyObject_Call(original__import__, args, kwargs);
  }
}

static PyTypeObject JsImportType = {
  .tp_name = "JsImport",
  .tp_basicsize = sizeof(JsImport),
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_call = JsImport_Call,
  .tp_doc = "An import hook that imports things from Javascript."
};

static PyObject*
JsImport_New()
{
  JsImport* self;
  self = (JsImport*)JsImportType.tp_alloc(&JsImportType, 0);
  return (PyObject*)self;
}

int
JsImport_init()
{
  if (PyType_Ready(&JsImportType)) {
    return 1;
  }

  PyObject* m = PyImport_AddModule("builtins");
  if (m == NULL) {
    return 1;
  }

  PyObject* d = PyModule_GetDict(m);
  if (d == NULL) {
    return 1;
  }

  original__import__ = PyDict_GetItemString(d, "__import__");
  if (original__import__ == NULL) {
    return 1;
  }
  Py_INCREF(original__import__);

  PyObject* importer = JsImport_New();
  if (importer == NULL) {
    return 1;
  }

  if (PyDict_SetItemString(d, "__import__", importer)) {
    return 1;
  }

  m = PyImport_AddModule("__main__");
  if (m == NULL) {
    return 1;
  }

  globals = PyModule_GetDict(m);
  if (globals == NULL) {
    return 1;
  }

  if (PyDict_Update(globals, d)) {
    return 1;
  }

  return 0;
}
