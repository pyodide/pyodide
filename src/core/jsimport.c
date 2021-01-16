#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "jsimport.h"
#include "jsproxy.h"
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"

static PyObject* js_module = NULL;
static PyObject* globalThis = NULL;
_Py_IDENTIFIER(__dir__);

static PyObject*
JsImport_GetAttr(PyObject* self, PyObject* attr)
{
  return PyObject_GetAttr(globalThis, attr);
}

static PyObject*
JsImport_Dir()
{
  return _PyObject_CallMethodIdObjArgs(globalThis, &PyId___dir__, NULL);
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
  JsRef globalThis_ref = hiwire_get_global("globalThis");
  globalThis = JsProxy_create(globalThis_ref);
  hiwire_decref(globalThis_ref);

  PyObject* module_dict = PyImport_GetModuleDict();
  if (module_dict == NULL) {
    return -1;
  }

  js_module = PyModule_Create(&JsModule);
  if (js_module == NULL) {
    return -1;
  }

  if (PyDict_SetItemString(module_dict, "js", js_module)) {
    Py_DECREF(js_module);
    return -1;
  }

  return 0;
}
