#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "keyboard_interrupt.h"
#include <emscripten.h>

int
pyodide_callback(void)
{
  int interrupt_buffer = EM_ASM_INT({
    let result = Module.interrupt_buffer[0];
    Module.interrupt_buffer[0] = 0;
    return result;
  });
  if (interrupt_buffer == 2) {
    PyErr_SetNone(PyExc_KeyboardInterrupt);
    return -1;
  }
  return 0;
}

void
set_pyodide_callback(int x)
{
  if (x) {
    PyPyodide_SetPyodideCallback(pyodide_callback);
  } else {
    PyPyodide_SetPyodideCallback(NULL);
  }
}
