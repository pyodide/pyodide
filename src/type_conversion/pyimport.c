#include "pyimport.h"

#include <Python.h>
#include <emscripten.h>

#include "python2js.h"

extern PyObject* globals;

JsRef
_pyimport(char* name)
{
  PyObject* pyname = PyUnicode_FromString(name);
  PyObject* pyval = PyDict_GetItem(globals, pyname);
  if (pyval == NULL) {
    Py_DECREF(pyname);
    pythonexc2js();
    return Js_ERROR;
  }

  Py_DECREF(pyname);
  JsRef idval = python2js(pyval);
  return idval;
}

EM_JS(int, pyimport_init, (), {
  Module.pyimport = function(name)
  {
    var pyname = allocate(intArrayFromString(name), 'i8', ALLOC_NORMAL);
    var idresult = Module.__pyimport(pyname);
    jsresult = Module.hiwire.get_value(idresult);
    Module.hiwire.decref(idresult);
    _free(pyname);
    return jsresult;
  };

  return 0;
});
