#include "Python.h"
#include "emscripten.h"
#include "error_handling.h"
#include "python_unexposed.h"

// This file manages the Python stack / thread state when stack switching.
//
// captureThreadState / restoreThreadState are called from JS, in saveState and
// restoreState in suspenders.c. enter_promising_task / exit_promising_task are
// called from C, in _pyproxy_apply_promising and run_main_promising.
//
// Every in-flight "promising task" owns a PyThreadState for its whole lifetime.
// We store the main thread state when we swap it out to enter a promising task
// and we restore it when the promising task suspends or exits.
//
// The logic here is inspired by:
// https://github.com/python-greenlet/greenlet/blob/master/src/greenlet/greenlet_greenlet.hpp
//
// When updating the major Python version it will be necessary to look at that
// file.
//
// See also https://github.com/python/cpython/pull/32303 which would move more
// of this logic into upstream CPython

int pystate_keepalive;

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(_set_running_loop);

/**
 * The main thread state that the promising task took over from. We'll reinstall
 * this thread state when the promising task gives up control by suspending or
 * by returning. It is NULL when the JS event loop is turning or when Python is
 * executing with no suspender.
 *
 * This has to be ambient state rather than a parameter, because a task gives up
 * control from JsvPromise_Syncify(), which sits arbitrarily deep below
 * enter_promising_task() with unknown Python frames in between.
 *
 * A task can only ever take control from the event loop and always returns
 * control to the event loop. So this is always the event loop tstate or NULL.
 * It is a bug to enter or resume a task when this is not NULL.
 */
static PyThreadState* handback_tstate = NULL;

/**
 * Dispose of a task's thread state.
 *
 * Note that we deliberately don't pool thread states for reuse. A lot of state
 * is keyed on thread state identity: threading.local() storage hangs off
 * tstate->threading_local_key, the ContextVar cache is keyed on
 * (tstate->id, tstate->context_ver), and the running event loop lives in
 * tstate->asyncio_running_loop. Handing the same thread state to an unrelated
 * task later means invalidating all of it by hand, which we got wrong before
 * and which would need re-auditing on every CPython update. A fresh thread
 * state gets a fresh unique id and PyThreadState_Clear deals with the rest.
 *
 * This must be called with a different thread state installed: PyThreadState_
 * Clear can run Python code (the threading.local() sentinel weakref callback)
 * and requires that the caller isn't running on `tstate`.
 */
static void
delete_tstate(PyThreadState* tstate)
{
  PyThreadState_Clear(tstate);
  PyThreadState_Delete(tstate);
}

/**
 * Install a thread state for the new task and record the main thread state so
 * we can swap it back in when we suspend or exit.
 *
 * The task inherits from its caller:
 *
 * - a copy of the contextvars context
 * - the thread local dict
 * - the running event loop
 * - the async generator hooks
 */
int
enter_promising_task(void)
{
  FAIL_RETURN_VALUE(-1);
  DECLARE_PY_OBJECT(asyncio_module);
  DECLARE_PY_OBJECT(loop);
  DECLARE_PY_OBJECT(context);
  DECLARE_PY_OBJECT(thread_dict);
  DECLARE_PY_OBJECT(agen_firstiter);
  DECLARE_PY_OBJECT(agen_finalizer);
  DECLARE_PY_OBJECT(tmp);

  if (handback_tstate != NULL) {
    // Entering a promising call yields to the event loop first so this should
    // not be reachable.
    PyErr_SetString(PyExc_SystemError,
                    "Cannot enter a promising task from inside another running "
                    "promising task. This is a bug in Pyodide.");
    FAIL();
  }

  // 1. Collect everything the task inherits, while we are still running on the
  //    caller's thread state.
  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);
  loop = _PyObject_CallMethodIdNoArgs(asyncio_module, &PyId_get_event_loop);
  if (loop == NULL) {
    // There is no event loop to propagate.
    PyErr_Clear();
  }
  context = PyContext_CopyCurrent();
  FAIL_IF_NULL(context);
  // PyThreadState_GetDict() creates the thread dict if it doesn't exist yet, so
  // the caller and the task share one.
  thread_dict = Py_XNewRef(PyThreadState_GetDict());
  // sys.set_asyncgen_hooks() records the hooks on the thread state, so a task
  // would otherwise run with no hooks installed and async generators it creates
  // would never be registered with the event loop that is going to have to shut
  // them down.
  PyThreadState* caller_tstate = PyThreadState_Get();
  agen_firstiter = Py_XNewRef(caller_tstate->async_gen_firstiter);
  agen_finalizer = Py_XNewRef(caller_tstate->async_gen_finalizer);
  PyThreadState* tstate = PyThreadState_New(PyInterpreterState_Get());
  FAIL_IF_NULL(tstate);

  // 2. Swap in task thread state
  handback_tstate = PyThreadState_Swap(tstate);

  // 3. Populate the new thread state
  assert(tstate->context == NULL);
  assert(tstate->dict == NULL);
  Py_XSETREF(tstate->context, context);
  context = NULL;
  Py_XSETREF(tstate->dict, thread_dict);
  thread_dict = NULL;
  Py_XSETREF(tstate->async_gen_firstiter, agen_firstiter);
  agen_firstiter = NULL;
  Py_XSETREF(tstate->async_gen_finalizer, agen_finalizer);
  agen_finalizer = NULL;
  if (loop != NULL) {
    tmp = _PyObject_CallMethodIdOneArg(
      asyncio_module, &PyId__set_running_loop, loop);
    if (tmp == NULL) {
      // Put back main thread state and fail
      PyErr_Clear();
      delete_tstate(PyThreadState_Swap(handback_tstate));
      handback_tstate = NULL;
      PyErr_SetString(PyExc_SystemError,
                      "Unexpected error when entering a promising task");
      FAIL();
    }
  }
  return 0;
}

/**
 * Put back the main thread state and dispose of the current thread state.
 *
 * Any pending exception must have been moved out of our thread state before
 * calling this, see _pyproxy_apply_promising.
 */
void
exit_promising_task(void)
{
  PyThreadState* mine = PyThreadState_Swap(handback_tstate);
  handback_tstate = NULL;
  delete_tstate(mine);
}

/**
 * Return task tstate so that saveState can store it in the JS state object.
 */
EMSCRIPTEN_KEEPALIVE PyThreadState*
captureThreadState(void)
{
  if (handback_tstate == NULL) {
    // validSuspender is supposed to prevent this. If it happens anyway, refuse
    // rather than detaching the thread state entirely.
    PyErr_SetString(PyExc_SystemError,
                    "Cannot stack switch: no thread state to hand control back "
                    "to. This is a bug in Pyodide.");
    return NULL;
  }
  PyThreadState* mine = PyThreadState_Swap(handback_tstate);
  handback_tstate = NULL;
  return mine;
}

EMSCRIPTEN_KEEPALIVE void
restoreThreadState(PyThreadState* state)
{
  handback_tstate = PyThreadState_Swap(state);
}
