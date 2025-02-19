#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "error_handling.h"
#include "jslib.h"
#include "python2js.h"
#include <emscripten.h>
#include <stdbool.h>

#define FATAL_ERROR(args...)                                                   \
  do {                                                                         \
    if (PyErr_Occurred()) {                                                    \
      _PyErr_FormatFromCause(PyExc_ImportError, args);                         \
    } else {                                                                   \
      PyErr_Format(PyExc_ImportError, args);                                   \
    }                                                                          \
    FAIL();                                                                    \
  } while (0)

#define FAIL_IF_STATUS_EXCEPTION(status)                                       \
  if (PyStatus_Exception(status)) {                                            \
    goto finally;                                                              \
  }

#define TRY_INIT(mod)                                                          \
  do {                                                                         \
    int mod##_init();                                                          \
    if (mod##_init()) {                                                        \
      FATAL_ERROR("Failed to initialize module %s.", #mod);                    \
    }                                                                          \
  } while (0)

#define TRY_INIT_WITH_CORE_MODULE(mod)                                         \
  do {                                                                         \
    int mod##_init(PyObject* mod);                                             \
    if (mod##_init(core_module)) {                                             \
      FATAL_ERROR("Failed to initialize module %s.", #mod);                    \
    }                                                                          \
  } while (0)

static struct PyModuleDef core_module_def = {
  PyModuleDef_HEAD_INIT,
  .m_name = "_pyodide_core",
  .m_doc = "Pyodide C builtins",
  .m_size = -1,
};

void
pyodide_export(void);
void
set_new_cframe(void* frame);
// Force _pyodide_pre.gen.o, and pystate.o to be included by
// using a symbol from each of them.
void* pyodide_export_ = pyodide_export;
void* set_new_cframe_ = set_new_cframe;

// clang-format off
EM_JS(void, set_pyodide_module, (JsVal mod), {
  API._pyodide = mod;
})
// clang-format on

int
init_pyodide_proxy()
{
  EM_ASM({
    // sourmash needs open64 to mean the same thing as open.
    // Emscripten 3.1.44 seems to have removed it??
    wasmImports["open64"] = wasmImports["open"];
  });
  bool success = false;
  // Enable JavaScript access to the _pyodide module.
  PyObject* _pyodide = PyImport_ImportModule("_pyodide");
  FAIL_IF_NULL(_pyodide);
  JsVal _pyodide_proxy = python2js(_pyodide);
  FAIL_IF_JS_NULL(_pyodide_proxy);
  set_pyodide_module(_pyodide_proxy);

  success = true;
finally:
  Py_CLEAR(_pyodide);
  return success ? 0 : -1;
}

EM_JS_DEPS(pyodide_core_deps, "stackAlloc,stackRestore,stackSave");
PyObject*
PyInit__pyodide_core(void)
{
  bool success = false;
  PyObject* _pyodide = NULL;
  PyObject* core_module = NULL;

  _pyodide = PyImport_ImportModule("_pyodide");
  if (_pyodide == NULL) {
    FATAL_ERROR("Failed to import _pyodide module.");
  }

  core_module = PyModule_Create(&core_module_def);
  if (core_module == NULL) {
    FATAL_ERROR("Failed to create core module.");
  }
  PyObject* module_dict = PyImport_GetModuleDict(); /* borrowed */
  if (PyDict_SetItemString(module_dict, "_pyodide_core", core_module)) {
    FATAL_ERROR("Failed to add '_pyodide_core' module to modules dict.");
    FAIL();
  }

  TRY_INIT_WITH_CORE_MODULE(error_handling);
  TRY_INIT(jslib);
  TRY_INIT(docstring);
  TRY_INIT_WITH_CORE_MODULE(python2js);
  TRY_INIT_WITH_CORE_MODULE(jsproxy);
  TRY_INIT_WITH_CORE_MODULE(jsproxy_call);
  TRY_INIT_WITH_CORE_MODULE(pyproxy);
  TRY_INIT_WITH_CORE_MODULE(jsbind);

  if (init_pyodide_proxy() == -1) {
    FATAL_ERROR("Failed to create _pyodide proxy.");
  }

  success = true;
finally:
  Py_CLEAR(_pyodide);
  if (!success) {
    Py_CLEAR(core_module);
  }
  return core_module;
}
