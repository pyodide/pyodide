#include "jsimport.h"
#include "Python.h"
#include "jsproxy.h"
#include "stdbool.h"

#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"

#define QUIT_IF_NULL(x)                                                        \
  do {                                                                         \
    if (x == NULL) {                                                           \
      goto finally;                                                            \
    }                                                                          \
  } while (0)

#define QUIT_IF_NZ(x)                                                          \
  do {                                                                         \
    if (x) {                                                                   \
      goto finally;                                                            \
    }                                                                          \
  } while (0)

static struct PyModuleDef JsModule;

_Py_IDENTIFIER(__dir__);
_Py_IDENTIFIER(__spec__);
_Py_IDENTIFIER(jsproxy);
// For indexing the javascript object:
_Py_IDENTIFIER(get);
_Py_IDENTIFIER(keys);

static bool
is_jsproxy_map(PyObject* proxy)
{
  // If the javascript object has a "get" method, we will consider it to be a
  // map.
  PyObject* getfunc = _PyObject_GetAttrId(proxy, &PyId_get);
  if (getfunc) {
    Py_CLEAR(getfunc);
    return true;
  } else {
    PyErr_Clear();
    return false;
  }
}

// helper method for JsImport_Dir
PyObject*
JsImport_Dir_object(PyObject* self, PyObject* jsproxy)
{
  PyObject* dirfunc = NULL;
  // result:
  PyObject* result = NULL;

  dirfunc = _PyObject_GetAttrId(jsproxy, &PyId___dir__);
  QUIT_IF_NULL(dirfunc);
  result = _PyObject_CallNoArg(dirfunc);
  QUIT_IF_NULL(result);

finally:
  Py_CLEAR(dirfunc);
  return result;
}

// helper method for JsImport_Dir
PyObject*
JsImport_Dir_map(PyObject* self, PyObject* jsproxy)
{
  PyObject* keysfunc = NULL;
  // result:
  PyObject* keys = NULL;

  keysfunc = _PyObject_GetAttrId(jsproxy, &PyId_keys);
  QUIT_IF_NULL(keysfunc);
  keys = _PyObject_CallNoArg(keysfunc);
  QUIT_IF_NULL(keys);

finally:
  Py_CLEAR(keysfunc);
  if (keys != NULL) {
    return keys;
  }
  _PyErr_FormatFromCause(
    PyExc_RuntimeError,
    "Object has a 'get' method but its keys method failed.");
  return NULL;
}

// module_dir does not automatically report object.__dir__(module) as part of
// the answer constrast module_getattro which first tries getattr(object, name)
// and only then uses JsImport_GetAttr if getattr(object, name) fails.
static PyObject*
JsImport_Dir(PyObject* self)
{
  bool success = false;
  PyObject* object__dir__ = NULL;
  PyObject* pykeys = NULL;
  PyObject* result_set = NULL;
  PyObject* jsproxy = NULL;
  PyObject* jskeys = NULL;
  PyObject* null_or_pynone = NULL;
  // result:
  PyObject* result = NULL;

  object__dir__ =
    _PyObject_GetAttrId((PyObject*)&PyBaseObject_Type, &PyId___dir__);
  QUIT_IF_NULL(object__dir__);
  pykeys = PyObject_CallFunctionObjArgs(object__dir__, self, NULL);
  QUIT_IF_NULL(pykeys);
  result_set = PySet_New(pykeys);
  QUIT_IF_NULL(result_set);

  jsproxy = _PyObject_GetAttrId(self, &PyId_jsproxy);
  QUIT_IF_NULL(jsproxy);

  // TODO: add support for maps to jsproxy and use that here.
  if (is_jsproxy_map(jsproxy)) {
    jskeys = JsImport_Dir_map(self, jsproxy);
  } else {
    jskeys = JsImport_Dir_object(self, jsproxy);
  }
  QUIT_IF_NULL(jskeys);
  QUIT_IF_NZ(_PySet_Update(result_set, pykeys));
  result = PyList_New(0);
  QUIT_IF_NULL(result);
  null_or_pynone = _PyList_Extend((PyListObject*)result, result_set);
  QUIT_IF_NULL(null_or_pynone);
  QUIT_IF_NZ(PyList_Sort(result));

  success = true;
finally:
  Py_CLEAR(object__dir__);
  Py_CLEAR(pykeys);
  Py_CLEAR(result_set);
  Py_CLEAR(jskeys);
  Py_CLEAR(null_or_pynone);
  if (!success) {
    Py_CLEAR(result);
  }
  return result;
}

// helper method for JsImport_GetAttr
static PyObject*
JsImport_GetAttr_Map(PyObject* self, PyObject* attr, PyObject* getfunc)
{
  // we consider that it's a map in this case and use "get" to find the
  // attribute.
  // TODO: move support of this to JsProxy
  PyObject* result = PyObject_CallFunctionObjArgs(getfunc, attr, NULL);
  if (result == Py_None) {
    const char* name_utf8 = PyModule_GetName(self);
    const char* attr_utf8 = PyUnicode_AsUTF8(attr);
    PyErr_Format(PyExc_AttributeError,
                 "module '%s' has no attribute '%s'",
                 name_utf8,
                 attr_utf8);
    return NULL;
  }
  return result;
}

// TODO: Temporary hack: rather than actually using the JsProxy to index,
// we will just pull off the JsRef. When #768, #788, #461 are resolved,
// we will get rid of this.
// clang-format off
typedef struct
{
  PyObject_HEAD
  JsRef js;
  PyObject* bytes;
} JsProxy;
// clang-format on

// helper method for JsImport_GetAttr
static PyObject*
JsImport_GetAttr_Object(PyObject* self, PyObject* attr, PyObject* jsproxy)
{
  // TODO: Fix JsProxy_GetAttr (Issues #768, #788, #461) and use that here.
  const char* attr_utf8 = PyUnicode_AsUTF8(attr);
  JsRef jsproxy_ref = ((JsProxy*)jsproxy)->js;
  JsRef idval = hiwire_get_member_string(jsproxy_ref, attr_utf8);
  if (idval == NULL) {
    const char* name_utf8 = PyModule_GetName(self);
    PyErr_Format(PyExc_AttributeError,
                 "module '%s' has no attribute '%s'",
                 name_utf8,
                 attr_utf8);
    return NULL;
  }
  PyObject* result = js2python(idval);
  hiwire_decref(idval);
  return result;
}

// module_getattro which first tries getattr(object, name) and only then uses
// JsImport_GetAttr if getattr(object, name) fails.
// contrast module_dir does not automatically report object.__dir__(module) as
// part of the answer
static PyObject*
JsImport_GetAttr(PyObject* self, PyObject* attr)
{
  PyObject* jsproxy = NULL;
  PyObject* getfunc = NULL;
  // result:
  PyObject* result = NULL;

  const char* name = PyModule_GetName(self);
  const char* attr_utf8 = PyUnicode_AsUTF8(attr);
  jsproxy = _PyObject_GetAttrId(self, &PyId_jsproxy);
  QUIT_IF_NULL(jsproxy);
  getfunc = _PyObject_GetAttrId(jsproxy, &PyId_get);
  if (getfunc) {
    result = JsImport_GetAttr_Map(self, attr, getfunc);
  } else {
    PyErr_Clear(); // clear error set by GetAttr(jsproxy, &PyId_get)
    result = JsImport_GetAttr_Object(self, attr, jsproxy);
  }
  QUIT_IF_NULL(result);

finally:
  Py_CLEAR(jsproxy);
  Py_CLEAR(getfunc);
  return result;
}

PyObject*
JsImport_CreateModule(PyObject* parent_module, PyObject* args)
{
  // Guard and arguments
  PyObject* spec;
  PyObject* jsproxy;
  if (!PyArg_UnpackTuple(args, "create_module", 2, 2, &spec, &jsproxy)) {
    return NULL;
  }
  if (!JsProxy_Check(jsproxy)) {
    // TODO: which error type?
    PyErr_SetString(PyExc_TypeError, "package is not an instance of jsproxy");
    return NULL;
  }

  // Try header
  bool success = false;
  PyObject* __dir__ = NULL;
  // result:
  PyObject* module = NULL;

  // Body
  module = PyModule_FromDefAndSpec(&JsModule, spec);
  PyObject* md_dict = PyModule_GetDict(module);
  // QUIT_IF_NZ(_PyDict_SetItemId(md_dict, &PyId___package__, Py_None));
  // QUIT_IF_NZ(_PyDict_SetItemId(md_dict, &PyId___loader__, Py_None));
  QUIT_IF_NZ(_PyDict_SetItemId(md_dict, &PyId___spec__, spec));
  QUIT_IF_NZ(_PyDict_SetItemId(md_dict, &PyId_jsproxy, jsproxy));

  // Finally
  success = true;
finally:
  if (success) {
    return module;
  }
  Py_CLEAR(module);
  return NULL;
}

bool
JsImport_Check(PyObject* module)
{
  PyModuleDef* def = PyModule_GetDef(module);
  if (def == NULL) {
    PyErr_Clear();
    return false;
  }
  return def == &JsModule;
}

static PyMethodDef JsModule_Methods[] = {
  { "__getattr__",
    (PyCFunction)JsImport_GetAttr,
    METH_O,
    "Get an object from the Javascript namespace" },
  { "__dir__",
    (PyCFunction)JsImport_Dir,
    METH_NOARGS,
    "Get an object from the Javascript namespace" },
  { NULL }
};

// The slots are callbacks that will get called for lazy initialization on first
// import. We are going to initialize our module when it is created with
// "pyodide.mount". Thus, we don't need any slots. However, various python stuff
// assumes that the module was created with "PyModule_Create()" if .m_slots is
// null, so to signal that we were created by
// PyModule_FromDefAndSpec/PyModule_ExecDef and our PyModuleDef is shared with
// other modules, we set .m_slots to an empty slot list.
static PyModuleDef_Slot JsModule_slots[] = { { 0, NULL } };

static struct PyModuleDef JsModule = {
  PyModuleDef_HEAD_INIT,
  .m_name = NULL, // The name will be pulled from the ModuleSpec.
  .m_doc = "Provides access to Javascript variables from Python",
  .m_slots = JsModule_slots,
  .m_methods = JsModule_Methods,
};

// To add to pyodide._importhooks
static PyMethodDef Pyodide_ImportHooks_Methods[] = {
  { "create_module_inner",
    (PyCFunction)JsImport_CreateModule,
    METH_VARARGS,
    "Get an object from the Javascript namespace" },
  { NULL }
};

int
JsImport_init()
{
  bool success = false;
  PyObject* mod_importhooks = NULL;

  mod_importhooks = PyImport_ImportModule("pyodide._importhooks");
  QUIT_IF_NULL(mod_importhooks);
  QUIT_IF_NZ(
    PyModule_AddFunctions(mod_importhooks, Pyodide_ImportHooks_Methods));

  success = true;
finally:
  Py_CLEAR(mod_importhooks);
  return success ? 0 : -1;
}
