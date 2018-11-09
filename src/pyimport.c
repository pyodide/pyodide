#include "pyimport.h"

#include <Python.h>
#include <emscripten.h>

#include "python2js.h"

extern PyObject* globals;

int
_pyimport(char* name)
{
  PyObject* pyname = PyUnicode_FromString(name);
  PyObject* pyval = PyDict_GetItem(globals, pyname);
  if (pyval == NULL) {
    Py_DECREF(pyname);
    return pythonexc2js();
  }

  Py_DECREF(pyname);
  int idval = python2js(pyval);
  return idval;
}

EM_JS(int, pyimport_init, (), {
  Module.pyimport = function(name)
  {
    var pyname = allocate(intArrayFromString(name), 'i8', ALLOC_NORMAL);
    var idresult = Module.__pyimport(pyname);
    jsresult = Module.hiwire_get_value(idresult);
    Module.hiwire_decref(idresult);
    _free(pyname);
    return jsresult;
  };

  return 0;
});
