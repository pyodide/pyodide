#define Py_BUILD_CORE_MODULE 1 // pycore_gil.h requires this to be defined
#include "Python.h"
#include "internal/pycore_ceval.h"
#include "internal/pycore_runtime.h"

static void
transfer_eval_breaker(PyThreadState* from, PyThreadState* to)
{
  uintptr_t bits = from->eval_breaker & _PY_SIGNALS_PENDING_BIT;
  if (bits == 0) {
    return;
  }
  _Py_unset_eval_breaker_bit(from, bits);
  _Py_set_eval_breaker_bit(to, bits);
}


PyThreadState*
pystate_threadstate_swap(PyThreadState* new_tstate)
{
  PyThreadState* orig_tstate = PyThreadState_Swap(new_tstate);

  // _PyEval_SignalReceived and Py_AddPendingCall and related only ever add work
  // to execute on the main tstate, with the assumption that the main tstate
  // will make consistent progress. Our stack switching is cooperative and can
  // delay execution of code on the main tstate for arbitrarily long, so we
  // always set the current tstate as the main tstate and copy the eval_breaker
  // flags.
  _PyRuntime.main_tstate = new_tstate;
  transfer_eval_breaker(orig_tstate, new_tstate)
  return orig_tstate;
}
