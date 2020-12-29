#include "jsimport.h"
#include "Python.h"
#include "jsproxy.h"
#include "stdbool.h"

#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"

_Py_IDENTIFIER(__dict__);
_Py_IDENTIFIER(__dir__);
_Py_IDENTIFIER(get);
_Py_IDENTIFIER(keys);

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

static bool
is_jsproxy_map(PyObject* proxy)
{
  PyObject* getfunc = _PyObject_GetAttrId(proxy, &PyId_get);
  if (getfunc) {
    Py_CLEAR(getfunc);
    return true;
  } else {
    PyErr_Clear();
    return false;
  }
}

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

  PyObject* dict = _PyObject_GetAttrId(self->module, &PyId___dict__);
  PyObject* own_keys = PyDict_Keys(dict);

  PyObject* jsproxy = _JsImport_getJsProxy(self->module);
  PyObject* result = NULL;

  // TODO: add support for maps to jsproxy and use that here.
  if (is_jsproxy_map(jsproxy)) {
    PyObject* keysfunc = NULL;
    PyObject* keys = NULL;

    keysfunc = _PyObject_GetAttrId(jsproxy, &PyId_keys);
    if (keysfunc == NULL) {
      goto finally_map;
    }
    keys = _PyObject_CallNoArg(keysfunc);
    if (keys == NULL) {
      goto finally_map;
    }
    result = PySequence_InPlaceConcat(own_keys, keys);
    if (result == NULL) {
      goto finally_map;
    }
  finally_map:
    Py_CLEAR(keysfunc);
    Py_CLEAR(own_keys);
    Py_CLEAR(keys);
    if (result != NULL) {
      return result;
    }
    _PyErr_FormatFromCause(
      PyExc_RuntimeError,
      "Object has a 'get' method but its keys method failed.");
    return NULL;
  }

  PyObject* dirfunc = _PyObject_GetAttrId(jsproxy, &PyId___dir__);
  if (dirfunc) {
    result = _PyObject_CallNoArg(dirfunc);
  }
  // Let errors in dir propagate up.
  return result;
}

// clang-format off
static PyTypeObject JsImportDirType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  .tp_doc = "A closure to work around the fact that module __dir__ does not get called with a reference to the module.",
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
  PyObject* result = NULL;
  const char *name = PyModule_GetName(self);

  // TODO: add support for maps to jsproxy and use that here.
  PyObject* getfunc = _PyObject_GetAttrId(jsproxy, &PyId_get);
  if(getfunc){ // we consider that it's a map in this case and use get to find the attribute.
    result = PyObject_CallFunctionObjArgs(getfunc, attr, NULL);
    Py_CLEAR(getfunc);
    if(result == Py_None){
      char* attr_utf8 = PyUnicode_AsUTF8(attr);
      PyErr_Format(PyExc_AttributeError, "module '%s' has no attribute '%s'", name, attr_utf8);
      return NULL;
    }
    return result;
  } else {
    PyErr_Clear(); // clear error set by GetAttr
    result = PyObject_GetAttr(jsproxy, attr);

    if(result == NULL && PyErr_ExceptionMatches(PyExc_AttributeError)){
      if(name == NULL){
        return NULL;
      }
      // Better attribute error.1
      _PyErr_FormatFromCause(PyExc_AttributeError, "module '%s' has no attribute '%s'", name, attr);
    }
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
  {
    "jsproxy",
    (PyCFunction)JsImport_getproxy,
    METH_NOARGS,
    "Get the Javascript object wrapped by this module."
  },
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

  PyObject* sys_modules = PyImport_GetModuleDict();
  QUIT_IF_NULL(sys_modules);
  {
    PyObject* module = PyDict_GetItemString(sys_modules, name);
    if(module && !JsImport_Check(module)){
      PyErr_Format(PyExc_KeyError,
        "Cannot mount with name '%s': there is an existing module by this name that was not mounted with 'pyodide.mountPackage'."
        , name
      );
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
  PyObject* module_dict = PyModule_GetDict(module);
  QUIT_IF_NZ(_PyDict_SetItemId(module_dict, &PyId___dir__, __dir__));
  QUIT_IF_NZ(PyDict_SetItemString(sys_modules, name, module));

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
  PyObject* sys_modules = PyImport_GetModuleDict();
  if(sys_modules == NULL){
    return -1;
  }
  PyObject* module = PyDict_GetItemString(sys_modules, name);
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
  if(PyDict_DelItemString(sys_modules, name)){
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
