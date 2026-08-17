#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include <emscripten.h>
#include <emscripten/eventloop.h>
#include <jslib.h>
#include <stdbool.h>

// The standard library is shipped as a zip file mounted at
// /lib/python<major><minor>.zip
#define STDLIB_ZIP_HELPER(major, minor) "/lib/python" #major #minor ".zip"
#define STDLIB_ZIP_(major, minor) STDLIB_ZIP_HELPER(major, minor)
#define STDLIB_ZIP STDLIB_ZIP_(PY_MAJOR_VERSION, PY_MINOR_VERSION)

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

  // Point the standard library directory at the stdlib zip
  status = PyConfig_SetBytesString(&config, &config.stdlib_dir, STDLIB_ZIP);
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

int
enter_promising_task(void);

void
exit_promising_task(void);

/**
 * Run main with stack switching enabled.
 *
 * Like _pyproxy_apply_promising, main gets a thread state of its own for its
 * whole lifetime. See the ownership model at the top of pystate.c.
 */
EMSCRIPTEN_KEEPALIVE int
run_main_promising(JsVal suspender)
{
  set_suspender(suspender);
  if (enter_promising_task() != 0) {
    PyErr_Print();
    return 1;
  }
  // Note: run_main() may call exit(), in which case control never returns here
  // and exit_promising_task() is never called. That's okay because the runtime
  // shuts down.
  int exitcode = run_main();
  exit_promising_task();
  return exitcode;
}
