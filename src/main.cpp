#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>
#include <Python.h>
#include <node.h>  // from CPython

#include "jsimport.hpp"
#include "jsproxy.hpp"
#include "js2python.hpp"
#include "pyimport.hpp"
#include "pyproxy.hpp"
#include "python2js.hpp"
#include "runpython.hpp"

using emscripten::val;

////////////////////////////////////////////////////////////
// Forward declarations

////////////////////////////////////////////////////////////
// Conversions


EMSCRIPTEN_BINDINGS(python) {
  emscripten::function("runPython", &runPython);
  emscripten::function("pyimport", &pyimport);
  emscripten::class_<Py>("Py")
    .function<val>("call", &Py::call)
    .function<val>("getattr", &Py::getattr)
    .function<void>("setattr", &Py::setattr)
    .function<val>("getitem", &Py::getitem)
    .function<void>("setitem", &Py::setitem);
}

extern "C" {
  int main(int argc, char** argv) {
    setenv("PYTHONHOME", "/", 0);

    Py_InitializeEx(0);

    if (JsProxy_Ready() ||
        jsToPython_Ready() ||
        pythonToJs_Ready() ||
        JsImport_Ready()) {
      return 1;
    }

    emscripten_exit_with_live_runtime();
    return 0;
  }
}
