#include "runpython.h"

#include <Python.h>
#include <emscripten.h>
#include <node.h> // from Python

#include "hiwire.h"
#include "python2js.h"

PyObject* globals;

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
_findImports(char* code, char* prefix)
{
  PyObject* py_code;
  PyObject* py_prefix = NULL;

  if ( !(py_code = PyUnicode_FromString(code)) ) {
    return pythonexc2js();
  }

  if( prefix && !(py_prefix = PyUnicode_FromString(prefix)) ) {
    return pythonexc2js();
  }

  PyObject* ret = PyObject_CallFunctionObjArgs(find_imports, py_code, py_prefix, NULL);

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

  Module.parsePythonImports = function(code, prefix)
  {
    if( typeof code === "string" )
      code = allocate(intArrayFromString(code), 'i8', ALLOC_NORMAL);

    if( typeof prefix === "string" )
      prefix = allocate(intArrayFromString(prefix), 'i8', ALLOC_NORMAL);
    else
      prefix = null;

    var idimports = Module.__findImports(code, prefix);
    var jsimports = Module.hiwire_get_value(idimports);
    Module.hiwire_decref(idimports);

    return jsimports;
  };

  Module.runPythonAsync = function(code, messageCallback)
  {
    var pycode = allocate(intArrayFromString(code), 'i8', ALLOC_NORMAL);
    let jsimports = Module.parsePythonImports(pycode);

    let internal = function(resolve, reject)
    {
      try {
        resolve(Module._runPythonInternal(pycode));
      } catch (e) {
        reject(e);
      }
    };

    if (jsimports.length) {
      return Module.loadPackage(jsimports, messageCallback)
        .then(() => new Promise(internal) );
    }

    return new Promise(internal);
  };

});

int
runpython_init_py()
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
