#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include <emscripten.h>

EMSCRIPTEN_KEEPALIVE int
py_version_major()
{
  return PY_MAJOR_VERSION;
}

EMSCRIPTEN_KEEPALIVE int
py_version_minor()
{
  return PY_MINOR_VERSION;
}

EMSCRIPTEN_KEEPALIVE int
py_version_micro()
{
  return PY_MICRO_VERSION;
}
