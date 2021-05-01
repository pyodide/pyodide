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

int
keyboard_interrupt_init()
{
  EM_ASM(
    {
      Module.setInterruptBuffer = function(buffer)
      {
        Module.interrupt_buffer = buffer;
        if (buffer) {
          _PyPyodide_SetPyodideCallback($0);
        } else {
          _PyPyodide_SetPyodideCallback(0);
        }
      };
    },
    pyodide_callback);
  return 0;
}
