#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include <emscripten.h>
#include <emscripten/eventloop.h>
#include <jslib.h>
#include <stdbool.h>

// Initialize python. exit() and print message to stderr on failure.
static void
initialize_python(int argc, char** argv)
{
  PyPreConfig preconfig;
  PyPreConfig_InitPythonConfig(&preconfig);

  PyStatus status = Py_PreInitializeFromBytesArgs(&preconfig, argc, argv);
  if (PyStatus_Exception(status)) {
    // This will exit().
    Py_ExitStatusException(status);
  }

  PyConfig config;
  PyConfig_InitPythonConfig(&config);
  _Defer
  {
    PyConfig_Clear(&config);
  };

  status = PyConfig_SetBytesArgv(&config, argc, argv);
  if (PyStatus_Exception(status)) {
    Py_ExitStatusException(status);
  }

  status = PyConfig_SetBytesString(&config, &config.home, "/");
  if (PyStatus_Exception(status)) {
    Py_ExitStatusException(status);
  }

  config.write_bytecode = false;
  status = Py_InitializeFromConfig(&config);
  if (PyStatus_Exception(status)) {
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
  // Normally the runtime would exit when main() returns, don't let that
  // happen.
  emscripten_runtime_keepalive_push();
  return 0;
}

void
pymain_run_python(int* exitcode);

EMSCRIPTEN_KEEPALIVE int
run_main()
{
  // run_python may call exit() if `-h` or `-V` have been passed. If we stop it
  // from exiting, we'll segfault. So pop the keep alive, so that exit() will
  // call onExit and shut down the runtime. We notice this in pyodide.ts and
  // throw a ExitStatus error.
  emscripten_runtime_keepalive_pop();
  int exitcode;
  pymain_run_python(&exitcode);
  emscripten_runtime_keepalive_push();
  return exitcode;
}

void
set_suspender(JsVal suspender);

/**
 * call _pyproxy_apply but save the error flag into the argument so it can't be
 * observed by unrelated Python callframes. callPyObjectKwargsSuspending will
 * restore the error flag before calling pythonexc2js(). See
 * test_stack_switching.test_throw_from_switcher for a detailed explanation.
 */
EMSCRIPTEN_KEEPALIVE int
run_main_promising(JsVal suspender)
{
  set_suspender(suspender);
  return run_main();
}
