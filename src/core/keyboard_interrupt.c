#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "keyboard_interrupt.h"
#include <emscripten.h>

static int callback_clock = 50;
_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(handle_interrupt);

void
webloop_handle_interrupts(void)
{
  bool success = false;
  PyObject* asyncio = NULL;
  PyObject* loop = NULL;
  PyObject* result = NULL;

  asyncio = PyImport_ImportModule("pyodide.webloop");
  FAIL_IF_NULL(asyncio);
  loop = _PyObject_CallMethodIdNoArgs(asyncio, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);
  result = _PyObject_CallMethodIdNoArgs(loop, &PyId_handle_interrupt);
  FAIL_IF_NULL(result);

  success = true;
finally:
  Py_CLEAR(asyncio);
  Py_CLEAR(loop);
  Py_CLEAR(result);
  if (!success) {
    fatal_python_exception();
  }
}

int
pyodide_callback(void)
{
  callback_clock--;
  if (unlikely(callback_clock == 0)) {
    callback_clock = 50;
    int interrupt_buffer = EM_ASM_INT({
      let result = API.interrupt_buffer[0];
      API.interrupt_buffer[0] = 0;
      return result;
    });
    if (unlikely(interrupt_buffer == 2)) {
      webloop_handle_interrupts();
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
