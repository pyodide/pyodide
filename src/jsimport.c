#include "jsimport.h"

#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"

static PyObject*
JsImport_GetAttr(PyObject* self, PyObject* attr)
{
  const char* c = PyUnicode_AsUTF8(attr);
  if (c == NULL) {
    return NULL;
  }
  int idval = hiwire_get_global((int)c);
  PyObject* result = js2python(idval);
  hiwire_decref(idval);
  return result;
}

static PyObject*
JsImport_Dir()
{
  int idwindow = hiwire_get_global("self");
  int iddir = hiwire_dir(idwindow);
  hiwire_decref(idwindow);
  PyObject* pydir = js2python(iddir);
  hiwire_decref(iddir);
  return pydir;
}

static PyMethodDef JsModule_Methods[] = {
  { "__getattr__",
    (PyCFunction)JsImport_GetAttr,
    METH_O,
    "Get an object from the global Javascript namespace" },
  { "__dir__",
    (PyCFunction)JsImport_Dir,
    METH_NOARGS,
    "Returns a list of object name in the global Javascript namespace" },
  { NULL }
};

static struct PyModuleDef JsModule = {
  PyModuleDef_HEAD_INIT,
  "js",
  "Provides access to Javascript global variables from Python",
  0,
  JsModule_Methods
};

int
JsImport_init()
{
  PyObject* sys = PyImport_AddModule("sys");
  if (sys == NULL) {
    return 1;
  }

  PyObject* sysd = PyModule_GetDict(sys);
  if (sysd == NULL) {
    return 1;
  }

  PyObject* modules = PyDict_GetItemString(sysd, "modules");
  if (modules == NULL) {
    return 1;
  }

  PyObject* module = PyModule_Create(&JsModule);
  if (module == NULL) {
    return 1;
  }

  if (PyDict_SetItemString(modules, "js", module)) {
    Py_DECREF(module);
    return 1;
  }

  Py_DECREF(module);

  return 0;
}
