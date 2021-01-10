#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "hiwire.h"
#include "pyproxy.h"
#include "python2js.h"
#include "runpython.h"

#include <emscripten.h>

static PyObject* pyodide_py;
static PyObject* globals;
_Py_IDENTIFIER(eval_code);

JsRef
_runPythonDebug(char* code)
{
  PyObject* py_code;
  py_code = PyUnicode_FromString(code);
  if (py_code == NULL) {
    fprintf(stderr, "runPythonDebug -- error occurred converting argument:\n");
    PyErr_Print();
    return Js_UNDEFINED;
  }

  PyObject* result = _PyObject_CallMethodIdObjArgs(
    pyodide_py, &PyId_eval_code, py_code, globals, NULL);

  if (result == NULL) {
    fprintf(stderr, "runPythonDebug -- error occurred\n");
    PyErr_Print();
    return Js_UNDEFINED;
  }

  printf("runPythonDebug -- eval_code succeeded, it returned:\n");
  PyObject_Print(result, stdout, 0);

  printf("runPythonDebug -- doing python2js(result):\n");
  JsRef id = python2js(result);
  Py_DECREF(result);
  return id;
}

EM_JS_NUM(int,
          runpython_init_js,
          (JsRef pyodide_py_proxy, JsRef globals_proxy),
          {
            Module.pyodide_py = Module.hiwire.get_value(pyodide_py_proxy);
            Module.globals = Module.hiwire.get_value(globals_proxy);

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
            return 0;
          });

int
runpython_init()
{
  bool success = false;
  JsRef pyodide_py_proxy = NULL;
  JsRef globals_proxy = NULL;

  // I'm a bit confused about this deal with globals and builtins:
  // 1. Why are we using __main__.__dict__ as globals? Shouldn't we make a fresh
  // dictionary?
  // 2. Why do we dump "builtins" directly into the dict? Normally we would
  // leave the builtins where they belong as globals().__builtins__.

  // borrowed
  PyObject* builtins = PyImport_AddModule("builtins");
  FAIL_IF_NULL(builtins);

  // borrowed
  PyObject* builtins_dict = PyModule_GetDict(builtins);
  FAIL_IF_NULL(builtins_dict);

  // borrowed
  PyObject* __main__ = PyImport_AddModule("__main__");
  FAIL_IF_NULL(__main__);

  // globals is static variable, borrowed
  globals = PyModule_GetDict(__main__);
  FAIL_IF_NULL(globals);
  Py_INCREF(globals); // to owned

  FAIL_IF_MINUS_ONE(PyDict_Update(globals, builtins_dict));

  // pyodide_py is static variable, new
  pyodide_py = PyImport_ImportModule("pyodide");
  FAIL_IF_NULL(pyodide_py);

  pyodide_py_proxy = python2js(pyodide_py);
  FAIL_IF_NULL(pyodide_py_proxy);
  // Currently by default, python2js copies dicts into objects.
  // We want to feed Module.globals back to `eval_code` in `pyodide.runPython`
  // (see definition in pyodide.js) but because the round trip conversion
  // py => js => py for a dict object is a JsProxy, that causes trouble.
  // Instead we explicitly call pyproxy_new.
  // We also had to add ad-hoc modifications to _pyproxy_get, etc to support
  // this. I (HC) will fix this with the rest of the type conversions
  // modifications.
  Py_INCREF(globals); // pyproxy_new steals argument
  globals_proxy = pyproxy_new(globals);
  FAIL_IF_NULL(globals_proxy);
  FAIL_IF_MINUS_ONE(runpython_init_js(pyodide_py_proxy, globals_proxy));

  success = true;
finally:
  hiwire_decref(pyodide_py_proxy);
  hiwire_decref(globals_proxy);
  if (success) {
    return 0;
  }
  if (PyErr_Occurred()) {
    PyErr_Print();
  }
  Py_CLEAR(pyodide_py);
  Py_CLEAR(globals);
  return -1;
}
