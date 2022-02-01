#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "keyboard_interrupt.h"
#include <emscripten.h>

static int callback_clock = 50;
_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(set_interrupt);

/**
 * Calls WebLoop.handle_interrupt.
 * WebLoop.handle_interrupt raises KeyboardInterrupt into all Tasks that are marked as interruptable.
 */
void
webloop_set_interrupt(void)
{
  bool success = false;
  PyObject* asyncio = NULL;
  PyObject* loop = NULL;
  PyObject* result = NULL;

  asyncio = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio);
  loop = _PyObject_CallMethodIdNoArgs(asyncio, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);
  result = _PyObject_CallMethodIdNoArgs(loop, &PyId_set_interrupt);
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

/**
 * Check if interrupt_buffer[0] is set to 2 and reset it. If it's set, schedule
 * interrupts on the current thread and also on all tasks that are marked as
 * interruptable.
 */
void pyodide_check_interrupt(){
  int interrupt_buffer = EM_ASM_INT({
    if(API.interrupt_check_disabled){
      return 0;
    }
    let result = API.interrupt_buffer[0];
    API.interrupt_buffer[0] = 0;
    return result;
  });
  if (unlikely(interrupt_buffer == 2)) {
    webloop_set_interrupt();
    PyErr_SetInterrupt();
  }
}

/**
 * Run pyodide_check_interrupt on a delay
 *
 * This runs a *lot* so the delay is important for performance
 */
int
pyodide_callback(void)
{
  callback_clock--;
  if (unlikely(callback_clock == 0)) {
    callback_clock = 50;
    pyodide_check_interrupt();
  }
  return 0;
}

/**
 * Called from setInterruptBuffer. Hooks into our patch for ceval.c to run our
 * interrupt checker.
 */
void
set_pyodide_callback(int x)
{
  if (x) {
    PyPyodide_SetPyodideCallback(pyodide_callback);
  } else {
    PyPyodide_SetPyodideCallback(NULL);
  }
}
