#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "keyboard_interrupt.h"
#include <emscripten.h>

static int callback_clock = 50;

int
pyodide_callback(void)
{
  callback_clock--;
  if (callback_clock == 0) {
    callback_clock = 50;
    int interrupt_buffer = EM_ASM_INT({
      let result = Module.interrupt_buffer[0];
      Module.interrupt_buffer[0] = 0;
      return result;
    });
    if (interrupt_buffer == 2) {
      PyErr_SetInterrupt();
    }
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
