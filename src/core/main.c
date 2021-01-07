#include <Python.h>
#include <assert.h>
#include <emscripten.h>
#include <stdalign.h>

#include "error_handling.h"
#include "hiwire.h"
#include "js2python.h"
#include "jsimport.h"
#include "jsproxy.h"
#include "pyproxy.h"
#include "python2js.h"
#include "runpython.h"

_Py_IDENTIFIER(__version__);
_Py_IDENTIFIER(version);

#define FATAL_ERROR(args...)                                                   \
  do {                                                                         \
    printf("FATAL ERROR: ");                                                   \
    printf(args);                                                              \
    if (PyErr_Occurred()) {                                                    \
      printf("Error was triggered by Python exception:\n");                    \
      PyErr_Print();                                                           \
      return -1;                                                               \
    }                                                                          \
  } while (0)

#define TRY_INIT(mod)                                                          \
  do {                                                                         \
    if (mod##_init()) {                                                        \
      FATAL_ERROR("Failed to initialize module %s.\n", #mod);                  \
    }                                                                          \
  } while (0)

static int
PythonInterpreter_init()
{
  bool success = false;
  setenv("PYTHONHOME", "/", 0);

  Py_InitializeEx(0);

  // This doesn't seem to work anymore, but I'm keeping it for good measure
  // anyway The effective way to turn this off is below: setting
  // sys.dont_write_bytecode = True
  setenv("PYTHONDONTWRITEBYTECODE", "1", 0);

  PyObject* sys = PyImport_ImportModule("sys");
  if (sys == NULL) {
    printf("Failed to import sys module.\n");
    goto finally;
  }

  if (PyObject_SetAttrString(sys, "dont_write_bytecode", Py_True)) {
    printf("Failed to set attribute on sys module.\n");
    goto finally;
  }
  success = true;
finally:
  Py_CLEAR(sys);
  return success ? 0 : -1;
}

int
version_info_init()
{
  PyObject* pyodide = PyImport_ImportModule("pyodide");
  PyObject* pyodide_version = _PyAttr_GetId(pyodide, &PyId___version__);
  char* pyodide_version_utf8 = PyUnicode_AsUTF8(version);
  PyObject* sys = PyImport_ImportModule("sys");
  PyObject* python_version = _PyAttr_GetId(sys, &PyId___version__);
  char* python_version_utf8 = PyUnicode_AsUTF8(version);

  EM_ASM(
    {
      Module.version = UTF8ToString($0);
      Module.pythonVersion = UTF8ToString($1);
    },
    pyodide_version_utf8,
    python_version_utf8);

  Py_CLEAR(pyodide);
  Py_CLEAR(pyodide_version);
  Py_CLEAR(sys);
  Py_CLEAR(python_version);
  return 0;
}

int
main(int argc, char** argv) TRY_INIT(hiwire);
TRY_INIT(PythonInterpreter);

TRY_INIT(error_handling);
TRY_INIT(js2python);
TRY_INIT(JsImport);
TRY_INIT(JsProxy);
TRY_INIT(pyproxy);
TRY_INIT(python2js);
TRY_INIT(runpython);

version_info_init();

printf("Python initialization complete\n");

emscripten_exit_with_live_runtime();
return 0;
}
