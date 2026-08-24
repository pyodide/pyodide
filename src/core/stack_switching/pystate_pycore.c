// Note: This file manages the Python stack / thread state when stack switching.
// It needs to be audited on every Python update.
//
// Separated into its own file because it touches internal headers.
//
// This file exposes two functions: pystate_threadstate_new(), which builds the
// thread state for a new task, and pystate_threadstate_swap(), which fixes up
// the runtime when one thread state takes over from another.
//
// Some things to check on Python version update:
// - The eval_breaker bit list in pycore_ceval.h. Each new bit needs to be
//   classified as interpreter-wide or per thread state.
// - That take_gil() still recomputes _PY_CALLS_TO_DO_BIT and refreshes the
//   instrumentation version on attach.

// All internal headers require Py_BUILD_CORE_MODULE to be defined.
#define Py_BUILD_CORE_MODULE 1

#include "Python.h"
#include "internal/pycore_ceval.h"
#include "internal/pycore_runtime.h"
#include "internal/pycore_tstate.h"

/**
 * asyncio records the loop it is running and the task whose step is currently
 * executing on the thread state, so a task with a thread state of its own has
 * to inherit both from its caller.
 *
 * The running task is NULL because callPromising() yields to the event loop
 * before it enters Python.
 */
static void
inherit_asyncio_state(PyThreadState* from, PyThreadState* to)
{
  _PyThreadStateImpl* from_impl = (_PyThreadStateImpl*)from;
  _PyThreadStateImpl* to_impl = (_PyThreadStateImpl*)to;
  assert(to_impl->asyncio_running_loop == NULL);
  assert(to_impl->asyncio_running_task == NULL);
  // Double check that running_task is NULL.
  assert(from_impl->asyncio_running_task == NULL);
  to_impl->asyncio_running_loop = Py_XNewRef(from_impl->asyncio_running_loop);
}

/**
 * Build the thread state for a new task, inheriting from `from` the per-thread
 * state that can only be reached through internal headers. The rest of what a
 * task inherits is handled by enter_promising_task().
 */
PyThreadState*
pystate_threadstate_new(PyThreadState* from)
{
  PyThreadState* tstate = PyThreadState_New(from->interp);
  if (tstate == NULL) {
    return NULL;
  }
  inherit_asyncio_state(from, tstate);
  return tstate;
}

#define TRANSFERABLE_EVAL_BREAKER_BITS                                         \
  ((uintptr_t)(_PY_SIGNALS_PENDING_BIT | _PY_GC_SCHEDULED_BIT))

/**
 * Move the eval_breaker bits that mean "the interpreter has work to do" as
 * opposed to "this particular thread state has work to do".
 */
static void
transfer_eval_breaker(PyThreadState* from, PyThreadState* to)
{
  uintptr_t bits = from->eval_breaker & TRANSFERABLE_EVAL_BREAKER_BITS;
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

  if (orig_tstate != NULL) {
    transfer_eval_breaker(orig_tstate, new_tstate);
  }
  return orig_tstate;
}
