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
#include "keyboard_interrupt.h"
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
  config.install_signal_handlers = false;
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
#define TRY_INIT_WITH_CORE_MODULE(mod)                                         \
  do {                                                                         \
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

PyObject* init_dict;

/**
 * The C code for runPythonSimple. The definition of runPythonSimple is in
 * `pyodide.js` for greater visibility.
 */
int
run_python_simple_inner(char* code)
{
  PyObject* result = PyRun_String(code, Py_file_input, init_dict, init_dict);
  Py_XDECREF(result);
  return result ? 0 : -1;
}

// from numpy_patch.c (no need for a header just for this)
int
numpy_patch_init();

int
get_python_stack_depth()
{
  PyThreadState* tstate = PyThreadState_GET();
  return tstate->recursion_depth;
}

/**
 * Bootstrap steps here:
 *  1. Initialize init_dict so that runPythonSimple will work.
 *  2. Initialize the different ffi components and create the _pyodide_core
 *     module
 *  3. Create a PyProxy wrapper around init_dict so that JavaScript can retreive
 *     PyProxies from the runPythonSimple namespace.
 */
int
main(int argc, char** argv)
{
  // This exits and prints a message to stderr on failure,
  // no status code to check.
  initialize_python();

  // Once we initialize init_dict, runPythonSimple can work. This gives us a way
  // to run Python code that works even if the rest of the initialization fails
  // pretty badly.
  init_dict = PyDict_New();
  if (init_dict == NULL) {
    FATAL_ERROR("Failed to create init_dict.");
  }

  if (alignof(JsRef) != alignof(int)) {
    FATAL_ERROR("JsRef doesn't have the same alignment as int.");
  }
  if (sizeof(JsRef) != sizeof(int)) {
    FATAL_ERROR("JsRef doesn't have the same size as int.");
  }

  PyObject* _pyodide = NULL;
  PyObject* core_module = NULL;
  JsRef init_dict_proxy = NULL;

  _pyodide = PyImport_ImportModule("_pyodide");
  if (_pyodide == NULL) {
    FATAL_ERROR("Failed to import _pyodide module");
  }

  core_module = PyModule_Create(&core_module_def);
  if (core_module == NULL) {
    FATAL_ERROR("Failed to create core module.");
  }

  EM_ASM({
    // For some reason emscripten doesn't make UTF8ToString available on Module
    // by default...
    Module.UTF8ToString = UTF8ToString;
    Module.wasmTable = wasmTable;
  });

  TRY_INIT_WITH_CORE_MODULE(error_handling);
  TRY_INIT(hiwire);
  TRY_INIT(docstring);
  TRY_INIT(numpy_patch);
  TRY_INIT(js2python);
  TRY_INIT_WITH_CORE_MODULE(python2js);
  TRY_INIT(python2js_buffer);
  TRY_INIT_WITH_CORE_MODULE(JsProxy);
  TRY_INIT_WITH_CORE_MODULE(pyproxy);

  PyObject* module_dict = PyImport_GetModuleDict(); /* borrowed */
  if (PyDict_SetItemString(module_dict, "_pyodide_core", core_module)) {
    FATAL_ERROR("Failed to add '_pyodide_core' module to modules dict.");
  }

  // Enable JavaScript access to the globals from runPythonSimple.
  init_dict_proxy = python2js(init_dict);
  if (init_dict_proxy == NULL) {
    FATAL_ERROR("Failed to create init_dict proxy.");
  }
  EM_ASM({ Module.init_dict = Module.hiwire.pop_value($0); }, init_dict_proxy);

  Py_CLEAR(_pyodide);
  Py_CLEAR(core_module);
  hiwire_CLEAR(init_dict_proxy);
  emscripten_exit_with_live_runtime();
  return 0;
}
