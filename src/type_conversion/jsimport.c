#include "jsimport.h"
#include "Python.h"
#include "jsproxy.h"
#include "stdbool.h"

#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"

_Py_IDENTIFIER(__dir__);

static void
_JsImport_setHiwireObject(PyObject* module, int id)
{
  PyObject** proxy = (PyObject**)PyModule_GetState(module);
  // JsProxy_cnew can memory error but that's the only error it throws.
  // Our current plan is to crash and burn if that ever happens.
  *proxy = JsProxy_cnew(id);
}

static PyObject*
_JsImport_getJsProxy(PyObject* module)
{
  PyObject** proxy = (PyObject**)PyModule_GetState(module);
  return *proxy;
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
  printf("JsImportDir_init!\n");
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
  PyObject* jsproxy = _JsImport_getJsProxy(self->module);

  _Py_IDENTIFIER(__dir__);
  PyObject* dirfunc = _PyDict_GetItemIdWithError(dict, &PyId___dir__);
  if (dirfunc) {
    result = _PyObject_CallNoArg(dirfunc);
  }
  return result;
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
  PyObject* jsproxy = _JsImport_getJsProxy(self);
  PyObject* result = PyObject_GetAttr(jsproxy, attr);
  // Looking at CPython source, it seems that result of PyModule_GetName is borrowed.
  // It can return an error if the module has an invalid __name__ field, but we should have a valid one.
  const char *name = PyModule_GetName(self);
  if(name == NULL){
    return NULL;
  }
  if(result == NULL && PyErr_ExceptionMatches(PyExc_AttributeError)){
    // Better attribute error.
    PyErr_Format(PyExc_AttributeError, "module '%s' has no attribute '%s'", name, attr);
  }
  return result;
}

static PyObject*
JsImport_getproxy(PyObject* self, PyObject* _args)
{
  PyObject* jsproxy = _JsImport_getJsProxy(self);
  Py_INCREF(jsproxy);
  return jsproxy;
}

static PyMethodDef JsModule_Methods[] = {
  { "__getattr__",
    (PyCFunction)JsImport_GetAttr,
    METH_O,
    "Get an object from the Javascript namespace" },
  { "getproxy", (PyCFunction)JsImport_GetAttr, METH_NOARGS},
  { NULL }
};

// The slots are callbacks that will get called for lazy initialization on first import.
// We are going to initialize our module when it is created with "pyodide.mount".
// Thus, we don't need any slots. However, various python stuff assumes that the
// module was created with "PyModule_Create()" if .m_slots is null, so to signal
// that we were created by PyModule_FromDefAndSpec/PyModule_ExecDef and our PyModuleDef
// is shared with other modules, we set .m_slots to an empty slot list.
static PyModuleDef_Slot JsModule_slots[] = {
    {0, NULL}
};

static struct PyModuleDef JsModule = {
  PyModuleDef_HEAD_INIT,
  .m_name=NULL, // The name will be pulled from the ModuleSpec.
  .m_doc="Provides access to Javascript variables from Python",
  .m_slots = JsModule_slots,
  // we store the hiwire id for the js object in m_size.
  .m_size=sizeof(PyObject*),
  JsModule_Methods
};

bool
JsImport_Check(PyObject* module){
  PyModuleDef* def = PyModule_GetDef(module);
  if(def == NULL){
    PyErr_Clear();
    return false;
  }
  return def == &JsModule;
}

#define QUIT_IF_NULL(x) \
  do {                  \
    if(x == NULL){      \
      goto finally;     \
    }                   \
  } while(0)

#define QUIT_IF_NZ(x)   \
  do {                  \
    if(x){              \
      goto finally;     \
    }                   \
  } while(0)

int
JsImport_mount(char* name, int package_id){
  bool success = false;
  PyObject* importlib_machinery = NULL;
  PyObject* ModuleSpec = NULL;
  PyObject* spec = NULL;
  PyObject* module = NULL;
  PyObject* __dir__ = NULL;

  PyObject* module_dict = PyImport_GetModuleDict();
  QUIT_IF_NULL(module_dict);
  {
    PyObject* check_if_module_exists = PyDict_GetItemString(module_dict, name);
    if(check_if_module_exists){
      PyErr_Format(PyExc_ValueError, "A python module named '%s' was already imported.");
      goto finally;
    }
  }

  // We can't use PyModule_Create because that assumes that we will create only one
  // module from the PyModuleDef. On the other hand, PyModule_FromDefAndSpec / PyModule_ExecDef
  // make no such assumption. The docs specifically suggest using them "when creating module objects dynamically".
  // The name of the module comes from a ModuleSpec. First we need to create the ModuleSpec.
  importlib_machinery = PyImport_ImportModule("importlib.machinery");
  QUIT_IF_NULL(importlib_machinery);
  ModuleSpec = PyObject_GetAttrString(importlib_machinery, "ModuleSpec");
  QUIT_IF_NULL(ModuleSpec);
  // The ModuleSpec init function takes two arguments, name and loader.
  // PyModule_FromDefAndSpec uses name for the name of the generated module
  // It never uses loader argument and doesn't store the ModuleSpec, so it's fine to pass None
  // for this.
  spec = PyObject_CallFunction(ModuleSpec, "sO", name, Py_None);
  QUIT_IF_NULL(spec);
  module = PyModule_FromDefAndSpec(&JsModule, spec);
  QUIT_IF_NULL(module);
  QUIT_IF_NZ(PyModule_ExecDef(module, &JsModule));

  _JsImport_setHiwireObject(module, package_id);

  __dir__ = PyObject_CallFunctionObjArgs(JsImportDirObject, module, NULL);
  QUIT_IF_NULL(__dir__);
  QUIT_IF_NZ(PyModule_AddObject(module, "__dir__", __dir__));
  QUIT_IF_NZ(PyDict_SetItemString(module_dict, name, module));

  success = true;
finally:
  Py_CLEAR(importlib_machinery);
  Py_CLEAR(ModuleSpec);
  Py_CLEAR(spec);
  Py_CLEAR(module);
  Py_CLEAR(__dir__);
  return success ? 0 : -1;
}

int
JsImport_dismount(char* name){
  // Everything is borrowed =D
  PyObject* module_dict = PyImport_GetModuleDict();
  if(module_dict == NULL){
    return -1;
  }
  PyObject* module = PyDict_GetItemString(module_dict, name);
  if(module == NULL){
    PyErr_Format(PyExc_KeyError,
      "Cannot dismount module '%s': no such module exists.", name
    );
    return -1;
  }
  if(!JsImport_Check(module)){
    PyErr_Format(PyExc_KeyError,
      "Cannot dismount module '%s': it was not mounted with 'pyodide.mountPackage',"
      "rather it is an actual Python module.", name
    );
    return -1;
  }
  if(PyDict_DelItemString(module_dict, name)){
    return -1;
  }
  return 0;
}


int
JsImport_init()
{
  if(
    EM_ASM_INT({
      try {
        Module.mountPackage = function(name, obj){
          let obj_id = Module.hiwire.new_value(obj);
          // TODO: Do we need to free name or does the module take ownership of it?
          let name_utf8 = stringToNewUTF8(name);
          if(_JsImport_mount(name_utf8, obj_id)){
            _pythonexc2js();
          }
          _free(name_utf8);
        };

        Module.dismountPackage = function(name){
          let name_utf8 = stringToNewUTF8(name);
          if(_JsImport_dismount(name_utf8)){
            _pythonexc2js();
          }
          _free(name_utf8);
        };

        return 0;
      } catch(e){
        return -1;
      }
    })
  ){
    return -1;
  }
  return PyType_Ready(&JsImportDirType);
}
