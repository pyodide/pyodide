// Note: This file manages the Python stack / thread state when stack switching.
// It needs to be audited on every Python update.
//
// captureThreadState / restoreThreadState are called from JS, in saveState and
// restoreState in suspenders.c. enter_promising_task / exit_promising_task are
// called from C, in _pyproxy_apply_promising and run_main_promising.
//
// Every in-flight "promising task" owns a PyThreadState for its whole lifetime.
// We store the main thread state when we swap it out to enter a promising task
// and we restore it when the promising task suspends or exits.
//
// Because each task has a thread state of its own, parts of the threadstate
// that should be shared between tasks have to be copied by hand.
//
// The logic is inspired by greenlet, but greenlet makes the opposite choice: it
// keeps one thread state per thread and saves and restores the fields that
// should be private to the task. See
// https://github.com/python-greenlet/greenlet/blob/master/src/greenlet/TPythonState.cpp
//
// TODO: Perhaps aligning with greenlet could reduce the amount of effort to
// maintain this?
//
// Whenever updating the Python version, look at the new fields added to
// PyThreadState and classify them as to whether they should be per-task or
// per-thread (i.e., global since we have only one thread). Whenever possible,
// we can see what Greenlet does and copy that.
//
// See also https://github.com/python/cpython/pull/32303 which would move more
// of this logic into upstream CPython

#include "Python.h"
#include "emscripten.h"
#include "error_handling.h"

int pystate_keepalive;

// Defined in pystate_pycore.c since they require internal headers.
PyThreadState*
pystate_tstate_new(PyThreadState* from);

PyThreadState*
pystate_tstate_swap(PyThreadState* new_tstate);

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
 * - the trace and profile functions
 *
 * All of these live on the thread state but are shared between all tasks. This
 * list has to be rechecked against the PyThreadState struct every time we
 * update Python.
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

  // 1. Collect everything the task inherits, while we are still running on the
  //    caller's thread state.
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
  // sys.settrace() and sys.setprofile() also record their state on the thread
  // state. We read these last since everything above can run Python, which
  // could in theory call sys.settrace().
  Py_tracefunc tracefunc = caller_tstate->c_tracefunc;
  DECLARE_PY_OBJECT(traceobj);
  traceobj = Py_XNewRef(caller_tstate->c_traceobj);
  Py_tracefunc profilefunc = caller_tstate->c_profilefunc;
  DECLARE_PY_OBJECT(profileobj);
  profileobj = Py_XNewRef(caller_tstate->c_profileobj);
  // pystate_tstate_new copies the event loop over because doing so requires
  // internal headers.
  PyThreadState* tstate = pystate_tstate_new(caller_tstate);
  FAIL_IF_NULL(tstate);

  // 2. Swap in task thread state
  handback_tstate = pystate_tstate_swap(tstate);
  ON_FAIL({
    // Restore thread state on failure
    PyErr_Clear();
    delete_tstate(pystate_tstate_swap(handback_tstate));
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
  // These have to be installed with the task's thread state current, so they
  // come last. They return void and report failures through
  // PyErr_FormatUnraisable().
  if (profilefunc != NULL) {
    PyEval_SetProfile(profilefunc, profileobj);
  }
  if (tracefunc != NULL) {
    PyEval_SetTrace(tracefunc, traceobj);
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
  PyThreadState* mine = pystate_tstate_swap(handback_tstate);
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
  PyThreadState* mine = pystate_tstate_swap(handback_tstate);
  handback_tstate = NULL;
  return mine;
}

EMSCRIPTEN_KEEPALIVE void
restoreThreadState(PyThreadState* state)
{
  assert(handback_tstate == NULL);
  handback_tstate = pystate_tstate_swap(state);
}
