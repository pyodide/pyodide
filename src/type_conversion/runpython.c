#include "runpython.h"
#include "hiwire.h"
#include "pyproxy.h"
#include "python2js.h"

#include <Python.h>
#include <emscripten.h>

static PyObject* py_pyodide;
static PyObject* globals;
_Py_IDENTIFIER(eval_code);

int
_runPythonDebug(char* code)
{
  PyObject* py_code;
  py_code = PyUnicode_FromString(code);
  if (py_code == NULL) {
    fprintf(stderr, "runPythonDebug -- error occurred converting argument:\n");
    PyErr_Print();
  }

  PyObject* result = _PyObject_CallMethodIdObjArgs(
    pyodide, &PyId_eval_code, py_code, globals, NULL);

  if (result == NULL) {
    fprintf(stderr, "runPythonDebug -- error occurred\n");
    PyErr_Print();
    return HW_UNDEFINED;
  }

  printf("runPythonDebug -- eval_code succeeded, it returned:\n");
  PyObject_Print(result, stdout, 0);

  printf("runPythonDebug -- doing python2js(result):\n");
  int id = python2js(result);
  Py_DECREF(result);
  return id;
}

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

  globals = PyModule_GetDict(__main__);
  if (globals == NULL) {
    return 1;
  }

  if (PyDict_Update(globals, builtins_dict)) {
    return 1;
  }

  py_pyodide = PyImport_ImportModule("pyodide");
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

      // Use this to test python code separate from pyproxy.apply.
      Module.runPythonDebug = function(code)
      {
        let pycode = stringToNewUTF8(code);
        let idresult = Module.__runPythonDebug(pycode);
        let jsresult = Module.hiwire.get_value(idresult);
        Module.hiwire.decref(idresult);
        _free(pycode);
        return jsresult;
      };
    },
    py_pyodide_id,
    py_globals_id);
  return 0;
}
