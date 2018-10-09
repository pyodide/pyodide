#include "runpython.h"

#include <Python.h>
#include <emscripten.h>
#include <node.h> // from Python

#include "hiwire.h"
#include "python2js.h"

extern PyObject* globals;

PyObject* eval_code;
PyObject* find_imports;

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

int
_findImports(char* code)
{
  PyObject* py_code;
  py_code = PyUnicode_FromString(code);
  if (py_code == NULL) {
    return pythonexc2js();
  }

  PyObject* ret = PyObject_CallFunctionObjArgs(find_imports, py_code, NULL);

  if (ret == NULL) {
    return pythonexc2js();
  }

  int id = python2js(ret);
  Py_DECREF(ret);
  return id;
}

EM_JS(int, runpython_init_js, (), {
  Module._runPythonInternal = function(pycode)
  {
    var idresult = Module.__runPython(pycode);
    var jsresult = Module.hiwire_get_value(idresult);
    Module.hiwire_decref(idresult);
    _free(pycode);
    return jsresult;
  };

  Module.runPython = function(code)
  {
    var pycode = allocate(intArrayFromString(code), 'i8', ALLOC_NORMAL);
    return Module._runPythonInternal(pycode);
  };

  Module.runPythonAsync = function(code, messageCallback)
  {
    var pycode = allocate(intArrayFromString(code), 'i8', ALLOC_NORMAL);

    var idimports = Module.__findImports(pycode);
    var jsimports = Module.hiwire_get_value(idimports);
    Module.hiwire_decref(idimports);

    var internal = function() { return Module._runPythonInternal(pycode); };

    if (jsimports.length) {
      var packages = window.pyodide._module.packages.dependencies;
      var packageFilter = function(name)
      {
        return Object.prototype.hasOwnProperty(packages, name);
      };
      jsimports = jsimports.filter(packageFilter);
      return Module.loadPackage(jsimports, messageCallback).then(internal);
    } else {
      var resolve = function(resolve) { return resolve(); };
      return new Promise(resolve).then(internal);
    }
  };
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

  find_imports = PyDict_GetItemString(d, "find_imports");
  if (find_imports == NULL) {
    return 1;
  }

  Py_DECREF(m);
  Py_DECREF(d);
  return 0;
}

EM_JS(int, runpython_finalize_js, (), {
  Module.version = function()
  {
    Module.runPython("import pyodide");
    return Module.runPython("pyodide.__version__");
  };
  return 0;
});
