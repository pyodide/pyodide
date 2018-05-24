#include "js2python.hpp"
#include "jsimport.hpp"
#include "pyimport.hpp"
#include "python2js.hpp"

using emscripten::val;

val pyimport(val name) {
  PyObject *pyname = jsToPython(name);
  PyObject *pyval = PyDict_GetItem(globals, pyname);
  if (pyval == NULL) {
    return pythonExcToJs();
  }

  return pythonToJs(pyval);
}
