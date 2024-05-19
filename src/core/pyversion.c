#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include <emscripten.h>

#ifndef PYODIDE_ABI
#error "oops"
#define PYODIDE_ABI make_ides_happy
#endif

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

#include <sys/utsname.h>

#define STRINGIFY(s) #s
#define STR(s) STRINGIFY(s)

int
__syscall_uname(intptr_t buf)
{
  if (!buf) {
    return -EFAULT;
  }
  const char* full_version = STR(PYODIDE_ABI);

  struct utsname* utsname = (struct utsname*)buf;

  strcpy(utsname->sysname, "Pyodide");
  strcpy(utsname->nodename, "pyodide");
  strcpy(utsname->release, full_version);
  strcpy(utsname->version, "#1");
#ifdef __wasm64__
  strcpy(utsname->machine, "wasm64");
#else
  strcpy(utsname->machine, "wasm32");
#endif
  return 0;
}
