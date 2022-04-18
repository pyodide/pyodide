#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include <assert.h>
#include <emscripten.h>
#include <stdalign.h>

#include "docstring.h"
#include "error_handling.h"
#include "hiwire.h"
#include "js2python.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include "python2js.h"
#include "python2js_buffer.h"

#define FATAL_ERROR(args...)                                                   \
  do {                                                                         \
    printf("FATAL ERROR: ");                                                   \
    printf(args);                                                              \
    printf("\n");                                                              \
    if (PyErr_Occurred()) {                                                    \
      printf("Error was triggered by Python exception:\n");                    \
      PyErr_Print();                                                           \
      EM_ASM(throw new Error("Fatal pyodide error"));                          \
    }                                                                          \
    return -1;                                                                 \
  } while (0)

#define FAIL_IF_STATUS_EXCEPTION(status)                                       \
  if (PyStatus_Exception(status)) {                                            \
    goto finally;                                                              \
  }

#define TRY_INIT(mod)                                                          \
  do {                                                                         \
    if (mod##_init()) {                                                        \
      FATAL_ERROR("Failed to initialize module %s.", #mod);                    \
    }                                                                          \
  } while (0)

#define TRY_INIT_WITH_CORE_MODULE(mod)                                         \
  do {                                                                         \
    if (mod##_init(core_module)) {                                             \
      FATAL_ERROR("Failed to initialize module %s.", #mod);                    \
    }                                                                          \
  } while (0)

// Initialize python. exit() and print message to stderr on failure.
static void
initialize_python()
{
  bool success = false;
  PyStatus status;
  PyConfig config;
  PyConfig_InitPythonConfig(&config);
  status = PyConfig_SetBytesString(&config, &config.home, "/");
  FAIL_IF_STATUS_EXCEPTION(status);
  config.write_bytecode = false;
  status = Py_InitializeFromConfig(&config);
  FAIL_IF_STATUS_EXCEPTION(status);

  success = true;
finally:
  PyConfig_Clear(&config);
  if (!success) {
    // This will exit().
    Py_ExitStatusException(status);
  }
}

static struct PyModuleDef core_module_def = {
  PyModuleDef_HEAD_INIT,
  .m_name = "_pyodide_core",
  .m_doc = "Pyodide C builtins",
  .m_size = -1,
};

/**
 * Bootstrap steps here:
 *  1. Import _pyodide package (we depend on this in _pyodide_core)
 *  2. Initialize the different ffi components and create the _pyodide_core
 *     module
 *  3. Create a PyProxy wrapper around _pyodide package so that JavaScript can
 *     call into _pyodide._base.eval_code and
 *     _pyodide._import_hook.register_js_finder (this happens in loadPyodide in
 *     pyodide.js)
 */
int
main(int argc, char** argv)
{
  EM_ASM({
    // For some reason emscripten doesn't make UTF8ToString available on Module
    // by default...
    Module.UTF8ToString = UTF8ToString;
    Module.wasmTable = wasmTable;
  });

  // This exits and prints a message to stderr on failure,
  // no status code to check.
  initialize_python();
  emscripten_exit_with_live_runtime();
  return 0;
}

int
pyodide_init(void)
{
  PyObject* _pyodide = NULL;
  PyObject* core_module = NULL;
  JsRef _pyodide_proxy = NULL;

  _pyodide = PyImport_ImportModule("_pyodide");
  if (_pyodide == NULL) {
    FATAL_ERROR("Failed to import _pyodide module");
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
  }

  // Enable JavaScript access to the _pyodide module.
  _pyodide_proxy = python2js(_pyodide);
  if (_pyodide_proxy == NULL) {
    FATAL_ERROR("Failed to create _pyodide proxy.");
  }
  EM_ASM({ API._pyodide = Hiwire.pop_value($0); }, _pyodide_proxy);

  Py_CLEAR(_pyodide);
  Py_CLEAR(core_module);
  return 0;
}
