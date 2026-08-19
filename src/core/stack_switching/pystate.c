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

PyThreadState*
pystate_get_main_tstate(void);
void
pystate_set_main_tstate(PyThreadState* tstate);
void
pystate_carry_signal_bit(PyThreadState* from, PyThreadState* to);

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(_set_running_loop);

/**
 * The main thread state that the promising task took over from. We'll reinstall
 * this thread state when the promising task gives up control by suspending or
 * by returning. It is NULL when the JS event loop is turning or when Python is
 * executing with no suspender.
 *
 * A task can only ever take control from the event loop and always returns
 * control to the event loop. So this is always the event loop tstate or NULL.
 * It is a bug to enter or resume a task when this is not NULL.
 */
static PyThreadState* handback_tstate = NULL;

// CPython targets signals and main-thread pending calls at
// _PyRuntime.main_tstate. Keep it pointed at the state currently executing on
// the main OS thread. This is always either this original state or a live task
// state.
static PyThreadState* original_main_tstate = NULL;

/**
 * Dispose of a task's thread state.
 *
 * We used to keep a freelist of thread states but it seems like there is no way
 * to reuse thread states correctly. It doesn't take very much time to make a
 * thread state anyways.
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
  if (handback_tstate != NULL) {
    // Entering a promising call yields to the event loop first so this should
    // not be reachable.
    PyErr_SetString(PyExc_SystemError,
                    "Cannot enter a promising task from inside another running "
                    "promising task. This is a bug in Pyodide.");
    FAIL();
  }
  if (original_main_tstate == NULL) {
    original_main_tstate = pystate_get_main_tstate();
  }

  // 1. Collect everything the task inherits, while we are still running on the
  //    caller's thread state.
  DECLARE_PY_OBJECT(asyncio_module);
  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);
  DECLARE_PY_OBJECT(loop);
  loop = _PyObject_CallMethodIdNoArgs(asyncio_module, &PyId_get_event_loop);
  if (loop == NULL) {
    // There is no event loop to propagate.
    PyErr_Clear();
  }
  DECLARE_PY_OBJECT(context);
  context = PyContext_CopyCurrent();
  FAIL_IF_NULL(context);
  // PyThreadState_GetDict() creates the thread dict if it doesn't exist yet, so
  // the caller and the task share one.
  DECLARE_PY_OBJECT(thread_dict);
  thread_dict = Py_XNewRef(PyThreadState_GetDict());
  // sys.set_asyncgen_hooks() records the hooks on the thread state so we need
  // to copy them over with the event loop.
  PyThreadState* caller_tstate = PyThreadState_Get();
  DECLARE_PY_OBJECT(agen_firstiter);
  agen_firstiter = Py_XNewRef(caller_tstate->async_gen_firstiter);
  DECLARE_PY_OBJECT(agen_finalizer);
  agen_finalizer = Py_XNewRef(caller_tstate->async_gen_finalizer);
  // All tasks should see the same thread locals since there is only one thread.
  // Thread locals are created lazily on first use, so force them to exist on
  // the caller.
  if (caller_tstate->threading_local_key == NULL) {
    DECLARE_PY_OBJECT(threading_module);
    threading_module = PyImport_ImportModule("threading");
    FAIL_IF_NULL(threading_module);
    DECLARE_PY_OBJECT(threading_local);
    threading_local = PyObject_CallMethod(threading_module, "local", NULL);
    FAIL_IF_NULL(threading_local);
    // Reading an attribute is what triggers the lazy creation.
    DECLARE_PY_OBJECT(res);
    res = PyObject_GetAttrString(threading_local, "__dict__");
    FAIL_IF_NULL(res);
  }
  DECLARE_PY_OBJECT(tlocal_key);
  tlocal_key = Py_XNewRef(caller_tstate->threading_local_key);
  DECLARE_PY_OBJECT(tlocal_sentinel);
  tlocal_sentinel = Py_XNewRef(caller_tstate->threading_local_sentinel);
  PyThreadState* tstate = PyThreadState_New(PyInterpreterState_Get());
  FAIL_IF_NULL(tstate);

  // 2. Swap in task thread state
  handback_tstate = PyThreadState_Swap(tstate);
  assert(handback_tstate == original_main_tstate);
  pystate_set_main_tstate(tstate);
  ON_FAIL({
    // Restore thread state on failure
    PyErr_Clear();
    pystate_set_main_tstate(original_main_tstate);
    delete_tstate(PyThreadState_Swap(handback_tstate));
    handback_tstate = NULL;
    PyErr_SetString(PyExc_SystemError,
                    "Unexpected error when entering a promising task");
  });

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
  Py_XSETREF(tstate->threading_local_key, tlocal_key);
  tlocal_key = NULL;
  Py_XSETREF(tstate->threading_local_sentinel, tlocal_sentinel);
  tlocal_sentinel = NULL;
  if (loop != NULL) {
    DECLARE_PY_OBJECT(res);
    res = _PyObject_CallMethodIdOneArg(
      asyncio_module, &PyId__set_running_loop, loop);
    FAIL_IF_NULL(res);
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
  pystate_carry_signal_bit(mine, handback_tstate);
  pystate_set_main_tstate(original_main_tstate);
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
  pystate_carry_signal_bit(mine, handback_tstate);
  pystate_set_main_tstate(original_main_tstate);
  handback_tstate = NULL;
  return mine;
}

EMSCRIPTEN_KEEPALIVE void
restoreThreadState(PyThreadState* state)
{
  handback_tstate = PyThreadState_Swap(state);
  assert(handback_tstate == original_main_tstate);
  pystate_set_main_tstate(state);
}
