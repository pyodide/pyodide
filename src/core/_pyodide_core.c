#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "hiwire.h"
#include "python2js.h"
#include <emscripten.h>
#include <stdbool.h>

#define FATAL_ERROR(args...)                                                   \
  do {                                                                         \
    PyErr_Format(PyExc_ImportError, args);                                     \
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

PyObject*
PyInit__pyodide_core(void)
{
  EM_ASM({
    // Emscripten doesn't make UTF8ToString or wasmTable available on Module by
    // default...
    Module.UTF8ToString = UTF8ToString;
    Module.wasmTable = wasmTable;
    // Emscripten has a bug where it accidentally exposes an empty object as
    // Module.ERRNO_CODES
    Module.ERRNO_CODES = ERRNO_CODES;
  });

  bool success = false;
  PyObject* _pyodide = NULL;
  PyObject* core_module = NULL;
  JsRef _pyodide_proxy = NULL;

  _pyodide = PyImport_ImportModule("_pyodide");
  if (_pyodide == NULL) {
    FATAL_ERROR("Failed to import _pyodide module.");
  }

  core_module = PyModule_Create(&core_module_def);
  if (core_module == NULL) {
    FATAL_ERROR("Failed to create core module.");
  }

  TRY_INIT_WITH_CORE_MODULE(error_handling);
  TRY_INIT(hiwire);
  TRY_INIT(docstring);
  TRY_INIT(js2python);
  TRY_INIT_WITH_CORE_MODULE(python2js);
  TRY_INIT(python2js_buffer);
  TRY_INIT_WITH_CORE_MODULE(JsProxy);
  TRY_INIT_WITH_CORE_MODULE(pyproxy);

  PyObject* module_dict = PyImport_GetModuleDict(); /* borrowed */
  if (PyDict_SetItemString(module_dict, "_pyodide_core", core_module)) {
    FATAL_ERROR("Failed to add '_pyodide_core' module to modules dict.");
    FAIL();
  }

  // Enable JavaScript access to the _pyodide module.
  _pyodide_proxy = python2js(_pyodide);
  if (_pyodide_proxy == NULL) {
    FATAL_ERROR("Failed to create _pyodide proxy.");
  }
  EM_ASM({ API._pyodide = Hiwire.pop_value($0); }, _pyodide_proxy);

  success = true;
finally:
  Py_CLEAR(_pyodide);
  if (!success) {
    Py_CLEAR(core_module);
  }
  return core_module;
}
