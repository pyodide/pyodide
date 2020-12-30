#include "jsimport.h"

#include <emscripten.h>

#include "js2python.h"
#include "jsref.h"

static PyObject* js_module = NULL;

static PyObject*
JsImport_GetAttr(PyObject* self, PyObject* attr)
{
  const char* c = PyUnicode_AsUTF8(attr);
  if (c == NULL) {
    return NULL;
  }
  JsRef idval = Js_get_global(c);
  if (idval == Js_ERROR) {
    PyErr_Format(PyExc_AttributeError, "Unknown attribute '%s'", c);
    return NULL;
  }
  PyObject* result = js2python(idval);
  Js_decref(idval);
  return result;
}

static PyObject*
JsImport_Dir()
{
  JsRef idwindow = Js_get_global("self");
  JsRef iddir = Js_dir(idwindow);
  Js_decref(idwindow);
  PyObject* pydir = js2python(iddir);
  Js_decref(iddir);
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
  PyObject* module_dict = PyImport_GetModuleDict();
  if (module_dict == NULL) {
    return 1;
  }

  js_module = PyModule_Create(&JsModule);
  if (js_module == NULL) {
    return 1;
  }

  if (PyDict_SetItemString(module_dict, "js", js_module)) {
    Py_DECREF(js_module);
    return 1;
  }

  return 0;
}
