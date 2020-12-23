#include "runpython.h"
#include "python2js.h"

#include <Python.h>
#include <emscripten.h>

int
runpython_init()
{
  PyObject* builtins = PyImport_AddModule("builtins");
  if (builtins == NULL) {
    return 1;
  }

  PyObject* builtins_dict = PyModule_GetDict(builtins);
  if (builtins_dict == NULL) {
    return 1;
  }

  PyObject* __main__ = PyImport_AddModule("__main__");
  if (__main__ == NULL) {
    return 1;
  }

  PyObject* globals = PyModule_GetDict(__main__);
  if (globals == NULL) {
    return 1;
  }

  if (PyDict_Update(globals, builtins_dict)) {
    return 1;
  }

  PyObject* py_pyodide = PyImport_ImportModule("pyodide");
  int py_pyodide_id = python2js(py_pyodide);
  Py_CLEAR(py_pyodide);
  int py_globals_id = python2js(globals);
  EM_ASM(
    {
      Module.py_pyodide = Module.hiwire.get_value($0);
      Module.globals = Module.hiwire.get_value($1);
    },
    py_pyodide_id,
    py_globals_id);
  return 0;
}