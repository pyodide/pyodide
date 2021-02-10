#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include <assert.h>
#include <emscripten.h>
#include <stdalign.h>

#include "error_handling.h"
#include "hiwire.h"
#include "js2python.h"
#include "jsproxy.h"
#include "keyboard_interrupt.h"
#include "pyproxy.h"
#include "python2js.h"

#define FATAL_ERROR(args...)                                                   \
  do {                                                                         \
    printf("FATAL ERROR: ");                                                   \
    printf(args);                                                              \
    if (PyErr_Occurred()) {                                                    \
      printf("Error was triggered by Python exception:\n");                    \
      PyErr_Print();                                                           \
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
      FATAL_ERROR("Failed to initialize module %s.\n", #mod);                  \
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
      FATAL_ERROR("Failed to initialize module %s.\n", #mod);                  \
    }                                                                          \
  } while (0)

static struct PyModuleDef core_module_def = {
  PyModuleDef_HEAD_INIT,
  .m_name = "_pyodide_core",
  .m_doc = "Pyodide C builtins",
  .m_size = -1,
};

PyObject* init_dict;

void
run_python_simple_inner(char* code)
{
  PyObject* result = PyRun_String(code, Py_file_input, init_dict, init_dict);
  if (result == NULL) {
    pythonexc2js();
  } else {
    Py_DECREF(result);
  }
}

int
main(int argc, char** argv)
{
  // This exits and prints a message to stderr on failure,
  // no status code to check.
  initialize_python();

  if (alignof(JsRef) != alignof(int)) {
    FATAL_ERROR("JsRef doesn't have the same alignment as int.");
  }
  if (sizeof(JsRef) != sizeof(int)) {
    FATAL_ERROR("JsRef doesn't have the same size as int.");
  }

  PyObject* core_module = NULL;
  core_module = PyModule_Create(&core_module_def);
  if (core_module == NULL) {
    FATAL_ERROR("Failed to create core module.");
  }

  TRY_INIT(hiwire);
  TRY_INIT(error_handling);
  TRY_INIT(js2python);
  TRY_INIT_WITH_CORE_MODULE(JsProxy);
  TRY_INIT(pyproxy);
  TRY_INIT(python2js);
  TRY_INIT(keyboard_interrupt);

  PyObject* module_dict = PyImport_GetModuleDict(); // borrowed
  if (PyDict_SetItemString(module_dict, "_pyodide_core", core_module)) {
    FATAL_ERROR("Failed to add '_pyodide_core' module to modules dict.");
  }

  init_dict = PyDict_New();
  JsRef init_dict_proxy = python2js(init_dict);
  EM_ASM(
    {
      Module.init_dict = Module.hiwire.pop_value($0);
      Module.runPythonSimple = function(code)
      {
        let code_c_string = stringToNewUTF8(code);
        try {
          _run_python_simple_inner(code_c_string);
        } finally {
          _free(code_c_string);
        }
      };
    },
    init_dict_proxy);

  Py_CLEAR(core_module);
  printf("Python initialization complete\n");
  emscripten_exit_with_live_runtime();
  return 0;
}
