#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include <emscripten.h>
#include <stdbool.h>

#define FAIL_IF_STATUS_EXCEPTION(status)                                       \
  if (PyStatus_Exception(status)) {                                            \
    goto finally;                                                              \
  }

// Initialize python. exit() and print message to stderr on failure.
static void
initialize_python(int argc, char** argv)
{
  bool success = false;
  PyStatus status;

  PyPreConfig preconfig;
  PyPreConfig_InitPythonConfig(&preconfig);

  status = Py_PreInitializeFromBytesArgs(&preconfig, argc, argv);
  FAIL_IF_STATUS_EXCEPTION(status);

  PyConfig config;
  PyConfig_InitPythonConfig(&config);

  status = PyConfig_SetBytesArgv(&config, argc, argv);
  FAIL_IF_STATUS_EXCEPTION(status);

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

PyObject*
PyInit__pyodide_core(void);

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
  // This exits and prints a message to stderr on failure,
  // no status code to check.
  PyImport_AppendInittab("_pyodide_core", PyInit__pyodide_core);
  initialize_python(argc, argv);
  emscripten_exit_with_live_runtime();
  return 0;
}

void
pymain_run_python(int* exitcode);

EMSCRIPTEN_KEEPALIVE int
run_main()
{
  int exitcode;
  pymain_run_python(&exitcode);
  return exitcode;
}
