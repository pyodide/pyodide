#define Py_BUILD_CORE_MODULE 1
#include "Python.h"
#include "internal/pycore_ceval.h"
#include "internal/pycore_runtime.h"

PyThreadState*
pystate_get_main_tstate(void)
{
  return _PyRuntime.main_tstate;
}

void
pystate_set_main_tstate(PyThreadState* tstate)
{
  // Promising tasks all execute on the main OS thread. Revisit this if Pyodide
  // gains pthread support.
  _PyRuntime.main_tstate = tstate;
}

void
pystate_carry_signal_bit(PyThreadState* from, PyThreadState* to)
{
  if (_Py_eval_breaker_bit_is_set(from, _PY_SIGNALS_PENDING_BIT)) {
    _Py_set_eval_breaker_bit(to, _PY_SIGNALS_PENDING_BIT);
  }
}
