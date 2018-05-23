#include "pyimport.h"

#include <Python.h>
#include <emscripten.h>

#include "python2js.h"

extern PyObject *globals;

int pyimport(char *name) {
  PyObject *pyname = PyUnicode_FromString(name);
  PyObject *pyval = PyDict_GetItem(globals, pyname);
  if (pyval == NULL) {
    Py_DECREF(pyname);
    return pythonExcToJs();
  }

  Py_DECREF(pyname);
  return pythonToJs(pyval);
}

EM_JS(int, pyimport_Ready, (), {
  Module.__pyimport = Module.cwrap('pyimport', 'number', ['string']);

  Module.pyimport = function(name) {
    var id = Module.__pyimport(name);
    result = Module.hiwire_get_value(id);
    Module.hiwire_decref(id);
    return result;
  };

  return 0;
});
