#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "keyboard_interrupt.h"
#include <emscripten.h>

static int callback_clock = 1000;

int
pyodide_callback(void)
{
  callback_clock--;
  if (callback_clock == 0) {
    callback_clock = 1000;
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
