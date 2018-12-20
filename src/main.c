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

int
main(int argc, char** argv)
{
  hiwire_setup();

  setenv("PYTHONHOME", "/", 0);

  Py_InitializeEx(0);

  // This doesn't seem to work anymore, but I'm keeping it for good measure
  // anyway The effective way to turn this off is below: setting
  // sys.done_write_bytecode = True
  setenv("PYTHONDONTWRITEBYTECODE", "1", 0);

  PyObject* sys = PyImport_ImportModule("sys");
  if (sys == NULL) {
    return 1;
  }
  if (PyObject_SetAttrString(sys, "dont_write_bytecode", Py_True)) {
    return 1;
  }
  Py_DECREF(sys);

  if (js2python_init() || JsImport_init() || JsProxy_init() ||
      pyimport_init() || pyproxy_init() || python2js_init() ||
      runpython_init_js() || runpython_init_py() || runpython_finalize_js()) {
    return 1;
  }

  printf("Python initialization complete\n");

  emscripten_exit_with_live_runtime();
  return 0;
}
