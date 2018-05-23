#include <emscripten.h>
#include <Python.h>

#include "hiwire.h"
#include "js2python.h"
#include "jsimport.h"
#include "jsproxy.h"
#include "pyimport.h"
#include "pyproxy.h"
#include "python2js.h"
#include "runpython.h"

// TODO: Use static functions where appropriate


////////////////////////////////////////////////////////////
// Forward declarations

////////////////////////////////////////////////////////////
// Conversions


/*
  TODO: This is a workaround for a weird emscripten compiler bug. The
  matplotlib/_qhull.so extension makes function pointer calls with these
  signatures, but since nothing with that signature exists in the MAIN_MODULE,
  it can't link the SIDE_MODULE. Creating these dummy functions here seems to
  work around the problem.
*/

void __foo(double x) {

}

void __foo2(double x, double y) {

}

void __foo3(double x, double y, double z) {

}

void __foo4(int a, double b, int c, int d, int e) {

}

/* END WORKAROUND */

int main(int argc, char** argv) {
  hiwire_setup();

  setenv("PYTHONHOME", "/", 0);

  Py_InitializeEx(0);

  // cleanup naming of these functions

  if (JsProxy_Ready() ||
      jsToPython_Ready() ||
      pythonToJs_Ready() ||
      JsImport_Ready() ||
      runPython_Ready() ||
      pyimport_Ready() ||
      PyProxy_Ready()) {
    return 1;
  }

  printf("Python initialization complete\n");

  emscripten_exit_with_live_runtime();
  return 0;
}
