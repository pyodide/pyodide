#include "runpython.h"

#include <Python.h>
#include <emscripten.h>
#include <node.h> // from Python

#include "hiwire.h"
#include "python2js.h"

extern PyObject* globals;

PyObject* eval_code;

int
_runPython(char* code)
{
  PyObject* py_code;
  py_code = PyUnicode_FromString(code);
  if (py_code == NULL) {
    return pythonexc2js();
  }

  PyObject* ret =
    PyObject_CallFunctionObjArgs(eval_code, py_code, globals, NULL);

  if (ret == NULL) {
    return pythonexc2js();
  }

  int id = python2js(ret);
  Py_DECREF(ret);
  return id;
}

EM_JS(int, runpython_init_js, (), {
  Module.runPython = function(code)
  {
    var pycode = allocate(intArrayFromString(code), 'i8', ALLOC_NORMAL);
    var idresult = Module.__runPython(pycode);
    jsresult = Module.hiwire_get_value(idresult);
    Module.hiwire_decref(idresult);
    _free(pycode);
    return jsresult;
  };

  return 0;
});

int
runpython_init_py()
{
  PyObject* m = PyImport_ImportModule("pyodide");
  if (m == NULL) {
    return 1;
  }

  PyObject* d = PyModule_GetDict(m);
  if (d == NULL) {
    return 1;
  }

  eval_code = PyDict_GetItemString(d, "eval_code");
  if (eval_code == NULL) {
    return 1;
  }

  Py_DECREF(m);
  Py_DECREF(d);
  return 0;
}
