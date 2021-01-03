#include <Python.h>
#include <assert.h>
#include <emscripten.h>
#include <stdalign.h>

#include "hiwire.h"
#include "js2python.h"
#include "jsimport.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include "python2js.h"
#include "runpython.h"

#define FATAL_ERROR(args...)                                                   \
  do {                                                                         \
    printf("FATAL ERROR: ");                                                   \
    printf(args);                                                              \
    if (PyErr_Occurred()) {                                                    \
      printf("Error was triggered by Python exception:\n");                    \
      PyErr_Print();                                                           \
      return 1;                                                                \
    }                                                                          \
  } while (0)

#define TRY_INIT(mod)                                                          \
  do {                                                                         \
    if (mod##_init()) {                                                        \
      FATAL_ERROR("Failed to initialize module %s.\n", #mod);                  \
    }                                                                          \
  } while (0)

int
main(int argc, char** argv)
{
  if (alignof(JsRef) != alignof(int)) {
    FATAL_ERROR("JsRef doesn't have the same alignment as int.");
  }
  if (sizeof(JsRef) != sizeof(int)) {
    FATAL_ERROR("JsRef doesn't have the same size as int.");
  }
  TRY_INIT(hiwire);

  setenv("PYTHONHOME", "/", 0);

  Py_InitializeEx(0);

  // This doesn't seem to work anymore, but I'm keeping it for good measure
  // anyway The effective way to turn this off is below: setting
  // sys.dont_write_bytecode = True
  setenv("PYTHONDONTWRITEBYTECODE", "1", 0);

  PyObject* sys = PyImport_ImportModule("sys");
  if (sys == NULL) {
    FATAL_ERROR("Failed to import sys module.");
  }

  if (PyObject_SetAttrString(sys, "dont_write_bytecode", Py_True)) {
    FATAL_ERROR("Failed to set attribute on sys module.");
  }
  Py_DECREF(sys);

  TRY_INIT(js2python);
  TRY_INIT(JsImport);
  TRY_INIT(JsProxy);
  TRY_INIT(pyproxy);
  TRY_INIT(python2js);
  TRY_INIT(runpython);
  printf("Python initialization complete\n");

  emscripten_exit_with_live_runtime();
  return 0;
}
