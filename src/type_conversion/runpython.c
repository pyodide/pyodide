#include "runpython.h"
#include "pyproxy.h"
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
  if (py_pyodide == NULL) {
    return 1;
  }

  int py_pyodide_id = python2js(py_pyodide);
  Py_CLEAR(py_pyodide);
  // Currently by default, python2js copies dicts into objects.
  // We want to feed Module.globals back to `eval_code` in `pyodide.runPython`
  // (see definition in pyodide.js) but because the round trip conversion
  // py => js => py for a dict object is a JsProxy, that causes trouble.
  // Instead we explicitly call pyproxy_new.
  // We also had to add ad-hoc modifications to _pyproxy_get, etc to support
  // this. I (HC) will fix this with the rest of the type conversions
  // modifications.
  int py_globals_id = pyproxy_new(globals);
  EM_ASM(
    {
      Module.py_pyodide = Module.hiwire.get_value($0);
      Module.globals = Module.hiwire.get_value($1);
    },
    py_pyodide_id,
    py_globals_id);
  return 0;
}