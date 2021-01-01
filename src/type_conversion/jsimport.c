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
_Py_IDENTIFIER(jsproxy);
_Py_IDENTIFIER(ModuleSpec);

// Temporary hack: rather than actually using the JsProxy to index,
// we will just pull off the JsRef. When #768, #788, #461 are resolved,
// we will get rid of this.
typedef struct
{
  PyObject_HEAD JsRef js;
  PyObject* bytes;
} JsProxy;

static void
_JsImport_setHiwireObject(PyObject* module, JsRef id)
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
  const char *name = PyModule_GetName(self);
  const char* attr_utf8 = PyUnicode_AsUTF8(attr);
  PyObject* jsproxy = _JsImport_getJsProxy(self);
  PyObject* getfunc = _PyObject_GetAttrId(jsproxy, &PyId_get);
  if(getfunc){
    // we consider that it's a map in this case and use "get" to find the attribute.
    // TODO: move support of this to JsProxy
    PyObject* result = PyObject_CallFunctionObjArgs(getfunc, attr, NULL);
    if(result == NULL){
      return NULL;
    }
    Py_CLEAR(getfunc);
    if(result == Py_None){
      const char* attr_utf8 = PyUnicode_AsUTF8(attr);
      PyErr_Format(PyExc_AttributeError, "module '%s' has no attribute '%s'", name, attr_utf8);
      return NULL;
    }
    return result;
  } else {
    PyErr_Clear(); // clear error set by GetAttr(jsproxy, &PyId_get)
    const char* attr_utf8 = PyUnicode_AsUTF8(attr);
    // TODO: remove access to private field of jsproxy
    JsRef jsproxy_ref = ((JsProxy*)jsproxy) -> js;
    JsRef idval = hiwire_get_member_string(jsproxy_ref, attr_utf8);
    if (idval == Js_ERROR) {
      PyErr_Format(PyExc_AttributeError, "module '%s' has no attribute '%s'", name, attr_utf8);
      return NULL;
    }
    PyObject* result = js2python(idval);
    hiwire_decref(idval);
    return result;
  }
}


int JsModule_traverse(PyObject *self, visitproc visit, void *arg){
  PyObject** proxy = (PyObject**)PyModule_GetState(self);
  if(proxy == NULL){
    // In python 3.8, JsModule_traverse can be called when module state is NULL.
    // In python 3.9 this is fixed and we don't need this check.
    return 0;
  }
  Py_VISIT(*proxy);
  return 0;
}

static int
JsModule_clear(PyObject *self){
  PyObject** proxy = (PyObject**)PyModule_GetState(self);
  if(proxy == NULL){
    return 0;
  }
  Py_CLEAR(*proxy);
  return 0;
}

static void
JsModule_free(void *self){
  // cf https://docs.python.org/3.8/c-api/typeobj.html#c.PyTypeObject.tp_clear
  // "it may be convenient to clear all contained Python objects, and write the type’s tp_dealloc function to invoke tp_clear."
  // m_free <==> tp_dealloc I think?
  JsModule_clear((PyObject*)self);
}

static PyMethodDef JsModule_Methods[] = {
  { "__getattr__",
    (PyCFunction)JsImport_GetAttr,
    METH_O,
    "Get an object from the Javascript namespace" },
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
  .m_free=JsModule_free,
  .m_methods=JsModule_Methods,
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
JsImport_mount(char* name_utf8, JsRef package_id){
  bool success = false;
  // Note: these are all of the objects that we will own.
  // If a function returns a borrow, we incref the result so that
  // we can free it in the finally block.
  // Reference counting is hard, so it's good to be as explicit and consistent
  // as possible.
  PyObject* name;
  PyObject* sys_modules = NULL;
  PyObject* importlib_machinery = NULL;
  PyObject* ModuleSpec = NULL;
  PyObject* spec = NULL;
  PyObject* module = NULL;
  PyObject* __dir__ = NULL;
  PyObject* module_dict = NULL;
  PyObject* jsproxy = NULL;


  name = PyUnicode_FromString(name_utf8);
  QUIT_IF_NULL(name);
  sys_modules = PyImport_GetModuleDict();
  QUIT_IF_NULL(sys_modules);
  // make cleanup code more consistent by increfing sys_modules.
  Py_INCREF(sys_modules);
  module = PyDict_GetItemWithError(sys_modules, name);
  Py_XINCREF(module);
  if(module && !JsImport_Check(module)){
    PyErr_Format(PyExc_KeyError,
      "Cannot mount with name '%s': there is an existing module by this name that was not mounted with 'pyodide.mountPackage'."
      , name
    );
    goto finally;
  }
  if(PyErr_Occurred()){
    goto finally;
  }

  // We can't use PyModule_Create because that assumes that we will create only one
  // module from the PyModuleDef. On the other hand, PyModule_FromDefAndSpec / PyModule_ExecDef
  // make no such assumption. The docs specifically suggest using them "when creating module objects dynamically".
  // The name of the module comes from a ModuleSpec. First we need to create the ModuleSpec.
  importlib_machinery = PyImport_ImportModule("importlib.machinery");
  QUIT_IF_NULL(importlib_machinery);
  ModuleSpec = _PyObject_GetAttrId(importlib_machinery, &PyId_ModuleSpec);
  QUIT_IF_NULL(ModuleSpec);
  // The ModuleSpec init function takes two arguments, name and loader.
  // PyModule_FromDefAndSpec uses name for the name of the generated module
  // It never uses loader argument and doesn't store the ModuleSpec, so it's fine to pass None
  // for this.
  spec = PyObject_CallFunctionObjArgs(ModuleSpec, name, Py_None, NULL);
  QUIT_IF_NULL(spec);
  module = PyModule_FromDefAndSpec(&JsModule, spec);
  QUIT_IF_NULL(module);
  QUIT_IF_NZ(PyModule_ExecDef(module, &JsModule));

  _JsImport_setHiwireObject(module, package_id);

  __dir__ = PyObject_CallFunctionObjArgs(JsImportDirObject, module, NULL);
  QUIT_IF_NULL(__dir__);
  module_dict = PyModule_GetDict(module);
  // make cleanup code more consistent by increfing module_dict.
  Py_INCREF(module_dict);
  // "PyDict_SetItem DOES NOT steal a reference to the object"
  // So that means it increfs the value automatically.
  QUIT_IF_NZ(_PyDict_SetItemId(module_dict, &PyId___dir__, __dir__));

  jsproxy = _JsImport_getJsProxy(module);
  // make cleanup code more consistent by increfing jsproxy.
  Py_INCREF(jsproxy);
  QUIT_IF_NZ(_PyDict_SetItemId(module_dict, &PyId_jsproxy, jsproxy));
  QUIT_IF_NZ(PyDict_SetItem(sys_modules, name, module));

  success = true;
finally:
  Py_CLEAR(name);
  Py_CLEAR(sys_modules);
  Py_CLEAR(importlib_machinery);
  Py_CLEAR(ModuleSpec);
  Py_CLEAR(spec);
  Py_CLEAR(module);
  Py_CLEAR(__dir__);
  Py_CLEAR(module_dict);
  Py_CLEAR(jsproxy);
  return success ? 0 : -1;
}

int
JsImport_dismount(char* name_utf8){
  bool success = false;
  PyObject* name = PyUnicode_FromString(name_utf8);
  PyObject* sys_modules = PyImport_GetModuleDict();
  if(sys_modules == NULL){
    goto finally;
  }
  PyObject* module = PyDict_GetItemWithError(sys_modules, name);
  if(module == NULL){
    PyErr_Format(PyExc_KeyError,
      "Cannot dismount module '%s': no such module exists.", name
    );
    goto finally;
  }
  if(!JsImport_Check(module)){
    PyErr_Format(PyExc_KeyError,
      "Cannot dismount module '%s': it was not mounted with 'pyodide.mountPackage',"
      "rather it is an actual Python module.", name
    );
    goto finally;
  }
  if(PyDict_DelItem(sys_modules, name)){
    goto finally;
  }

  success = true;
finally:
  Py_CLEAR(name);
  return success ? 0 : -1;
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
