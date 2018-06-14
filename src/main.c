#include <Python.h>
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "jsimport.h"
#include "jsproxy.h"
#include "pyimport.h"
#include "pyproxy.h"
#include "python2js.h"
#include "runpython.h"

/*
  TODO: This is a workaround for a weird emscripten compiler bug. The
  matplotlib/_qhull.so extension makes function pointer calls with these
  signatures, but since nothing with that signature exists in the MAIN_MODULE,
  it can't link the SIDE_MODULE. Creating these dummy functions here seems to
  work around the problem.
*/

void
__foo(double x)
{}

void
__foo2(double x, double y)
{}

void
__foo3(double x, double y, double z)
{}

void
__foo4(int a, double b, int c, int d, int e)
{}

/* END WORKAROUND */

int
main(int argc, char** argv)
{
  hiwire_setup();

  setenv("PYTHONDONTWRITEBYTECODE", "1", 0);
  setenv("PYTHONHOME", "/", 0);

  Py_InitializeEx(0);

  // TODO cleanup naming of these functions

  if (js2python_init() || JsImport_init() || JsProxy_init() ||
      pyimport_init() || pyproxy_init() || python2js_init() ||
      runpython_init()) {
    return 1;
  }

  printf("Python initialization complete\n");

  emscripten_exit_with_live_runtime();
  return 0;
}
