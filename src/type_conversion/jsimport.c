#include "jsimport.h"
#include "Python.h"
#include "stdbool.h"

#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"

static void
_JsImport_setObjectId(PyObject* module, int id)
{
  int* module_id = (int*)PyModule_GetState(module);
  *module_id = id;
}

static int
_JsImport_getObjectId(PyObject* module)
{
  int* module_id = (int*)PyModule_GetState(module);
  return *module_id;
}

// Annoyingly the __dir__ method does NOT get a self parameter.
// We need to wrap it in a closure with a reference to our js object.
// First we make the Python type that does this closure.

// clang-format off
typedef struct
{
  PyObject_HEAD
  PyObject* module;
} JsImportDir;
// clang-format on

static int
JsImportDir_init(PyObject* o, PyObject* args, PyObject* kwargs)
{
  JsImportDir* self = (JsImportDir*)o;
  PyObject* module;
  if (!PyArg_UnpackTuple(args, "__init__", 1, 1, &module)) {
    return -1;
  }
  self->module = module;
  return 0;
}

static PyObject*
JsImportDir_Call(PyObject* o, PyObject* args, PyObject* kwargs)
{
  JsImportDir* self = (JsImportDir*)o;
  int js_obj_id = _JsImport_getObjectId(self->module);
  int dir_id = hiwire_dir(js_obj_id);
  PyObject* pydir = js2python(dir_id);
  hiwire_decref(dir_id);
  return pydir;
}

// clang-format off
static PyTypeObject JsImportDirType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  .tp_doc = "Custom objects",
  .tp_name = "pyodide.JsImportDir",
  .tp_basicsize = sizeof(JsImportDir),
  .tp_new = PyType_GenericNew,
  .tp_init = (initproc) JsImportDir_init,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_call = JsImportDir_Call,
};
PyObject* JsImportDirObject = (PyObject*)&JsImportDirType;
// clang-format off

static PyObject*
JsImport_GetAttr(PyObject* self, PyObject* attr)
{
  char* attr_utf8 = PyUnicode_AsUTF8(attr);
  if (attr_utf8 == NULL) {
    return NULL;
  }
  int idpkg = _JsImport_getObjectId(self);
  if (idpkg == -1) {
    PyErr_Format(PyExc_RuntimeError, "Invalid package internal id");
    return NULL;
  }
  int idval = hiwire_get_member_string(idpkg, attr_utf8);
  if (idval == -1) {
    PyErr_Format(PyExc_AttributeError, "Unknown attribute '%s'", attr_utf8);
    return NULL;
  }
  PyObject* result = js2python(idval);
  hiwire_decref(idval);
  // if js2python returns an error, it is automatically passed up.
  return result;
}

static PyMethodDef JsModule_Methods[] = {
  { "__getattr__",
    (PyCFunction)JsImport_GetAttr,
    METH_O,
    "Get an object from the Javascript namespace" },
  { NULL }
};

static struct PyModuleDef JsModule = {
  PyModuleDef_HEAD_INIT,
  .m_name=NULL,// fill in later
  .m_doc="Provides access to Javascript variables from Python",
  // we store the hiwire id for the js object in m_size.
  .m_size=sizeof(int),
  JsModule_Methods
};

int
JsImport_mount(char* name, int package_id){
  bool success = false;
  PyObject* module_dict = NULL;
  PyObject* module = NULL;
  PyObject* __dir__ = NULL;
  printf("Mount name : %s\n", name);
  module_dict = PyImport_GetModuleDict();
  if (module_dict == NULL) {
    goto finally;
  }

  JsModule.m_name = name;
  module = PyModule_Create(&JsModule);
  if (module == NULL) {
    goto finally;
  }
  _JsImport_setObjectId(module, package_id);

  __dir__ = PyObject_CallFunctionObjArgs(JsImportDirObject, module, NULL);
  if(__dir__ == NULL){
    goto finally;
  }
  if(PyObject_SetAttrString(module, "__dir__", __dir__)){
    goto finally;
  }

  if (PyDict_SetItemString(module_dict, name, module)) {
    goto finally;
  }

  success = true;
finally:
  Py_CLEAR(module_dict);
  Py_CLEAR(module);
  Py_CLEAR(__dir__);
  return success ? 0 : -1;
}

void
JsImport_GetModule(char *name_utf8){
  PyObject * name = PyUnicode_FromString(name_utf8);
  PyObject* module = PyImport_GetModule(name);
  if(PyErr_Occurred()){
    PyErr_Print();
  } else {
    PyObject_Print(module, stdout, 0);
  }
}

int
JsImport_init()
{
  if(EM_ASM_INT({
    try {
      Module.mountPackage = function(name, obj){
        let obj_id = Module.hiwire.new_value(obj);
        // TODO: Do we need to free name or does the module take ownership of it?
        let name_utf8 = stringToNewUTF8(name);
        console.log("mountPackage", name, obj);
        if(_JsImport_mount(name_utf8, obj_id)){
          pythonexc2js();
        }
      };

      return 0;
    } catch(e){
      return -1;
    }
  })){
    return -1;
  }
  return PyType_Ready(&JsImportDirType);
}
