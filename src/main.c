#include <Python.h>
#include <emscripten.h>
#include "testmacros.h"


#include "hiwire.h"
#include "js2python.h"
#include "jsimport.h"
#include "jsproxy.h"
#include "pyimport.h"
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
    }                                                                          \
  } while (0)

#define TRY_INIT(mod)                                                          \
  do {                                                                         \
    if (mod##_init()) {                                                        \
      FATAL_ERROR("Failed to initialize module %s.\n", #mod);                  \
      return 1;                                                                \
    }                                                                          \
  } while (0)

#ifdef TEST
  int
  init_test_entrypoints();
#endif

int
main(int argc, char** argv)
{
#ifdef TEST
  init_test_entrypoints();
#endif
  hiwire_setup();
  setenv("PYTHONHOME", "/", 0);

  Py_InitializeEx(0);

  // This doesn't seem to work anymore, but I'm keeping it for good measure
  // anyway The effective way to turn this off is below: setting
  // sys.dont_write_bytecode = True
  setenv("PYTHONDONTWRITEBYTECODE", "1", 0);

  PyObject* sys = PyImport_ImportModule("sys");
  if (sys == NULL) {
    FATAL_ERROR("Failed to import sys module.");
    return 1;
  }
  if (PyObject_SetAttrString(sys, "dont_write_bytecode", Py_True)) {
    FATAL_ERROR("Failed to set attribute on sys module.");
    return 1;
  }
  Py_DECREF(sys);

  TRY_INIT(js2python);
  TRY_INIT(JsImport);
  TRY_INIT(JsProxy);
  TRY_INIT(pyimport);
  TRY_INIT(pyproxy);
  TRY_INIT(python2js);
  TRY_INIT(runpython);
  printf("Python initialization complete\n");

  emscripten_exit_with_live_runtime();
  return 0;
}

#ifdef TEST
EM_JS(int, init_test_entrypoints, (), {
  Module.Tests = {};
  Module.Tests.test_entrypoints = function() { return "It works!"; };
  Module.Tests.raise_on_fail = function(result){
    if (result) {
      let msg = UTF8ToString(result);
      _free(result);
      throw new Error(msg);
    }
  };
  Module.Tests.test_c_tests_success =  _test_c_tests_success;
  Module.Tests.test_c_tests_fail =  _test_c_tests_fail;
});

DEFINE_TEST(
  c_tests_success, {
    ASSERT(1);
    ASSERT(1 > -7);
  }
)

DEFINE_TEST(
  c_tests_fail, {
    char* failure_msg = NULL;
    ASSERT(0 * (1 + 1 - 88));
    return failure_msg;
  }
)
#endif
