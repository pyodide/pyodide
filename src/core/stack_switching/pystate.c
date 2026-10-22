// Note: This file manages the Python thread state when stack switching. It
// needs to be audited on every Python update.
//
// captureTaskState / restoreTaskState are called from JS, in saveState and
// restoreState in suspenders.c. enter_promising_task / exit_promising_task are
// called from C, in _pyproxy_apply_promising and run_main_promising.
//
// There is exactly one PyThreadState and it is always the current thread state.
// Every in-flight "promising task" owns per-task state:
//  * the frame chain
//  * error flag
//  * contextvars context
//
// We swap these per-task fields whenever we change tasks. Everything else on
// the thread state is shared between tasks and is left alone.
//
// This is the approach greenlet takes, see
// https://github.com/python-greenlet/greenlet/blob/master/src/greenlet/TPythonState.cpp
//
// Keeping one thread state is important because some extensions store the
// thread state pointer in a TLS variable and assume it will remain valid since
// they reason there is only one thread state per thread. In our single threaded
// build, TLS is turned into normal global variables so to make these extensions
// work there can only be one thread state. See
// https://github.com/pyodide/pyodide/issues/6479.
//
// Whenever updating the Python version, look at the new fields added to
// PyThreadState and classify them as to whether they should be per-task or not.
// Generally we should be able to copy greenlet.
//
// See also https://github.com/python/cpython/pull/32303 which would move more
// of this logic into upstream CPython

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "Python.h"
#include "emscripten.h"
#include "error_handling.h"

int pystate_keepalive;

// Defined in pystate_pycore.c since they require internal headers.
PyObject*
pystate_swap_asyncio_running_task(PyThreadState* tstate, PyObject* task);

void
pystate_free_datastack(_PyStackChunk* chunk);

/**
 * The per-task part of the thread state.
 *
 * Audit this against PyThreadState and _PyThreadStateImpl on every Python
 * update.
 */
typedef struct
{
  // The contextvars context. Strong reference.
  PyObject* context;
  // Top of the frame chain. The frames live on the data stack below, except
  // for the _PyEntryFrame that _PyEval_EvalFrameDefault keeps as a C local,
  // which the suspender handles.
  struct _PyInterpreterFrame* current_frame;
  // The exception stack. exc_info is NULL if it pointed at tstate->exc_state,
  // since that address belongs to the thread state and not to the task.
  _PyErr_StackItem* exc_info;
  _PyErr_StackItem exc_state;
  // The exception being raised. Strong reference. Should be NULL when we
  // switch but we save it anyway so a stray exception can't leak between
  // tasks.
  PyObject* current_exception;
  int py_recursion_remaining;
  // Depth of the trace / profile callbacks currently running.
  int tracing;
  // The sys.monitoring event currently being dispatched, or -1. Set while a
  // monitoring callback runs, so it belongs to the frame chain that is
  // executing.
  int what_event;
  // Trashcan state, a chain of objects awaiting deallocation. Borrowed, the
  // objects have a refcount of 0 and are owned by the chain.
  PyObject* delete_later;
  // Memory for the frames. Each task starts with datastack_chunk == NULL so
  // the frame allocator gives it a root chunk of its own.
  _PyStackChunk* datastack_chunk;
  PyObject** datastack_top;
  PyObject** datastack_limit;
  // JIT executor. Borrowed, always NULL for us since we build without the JIT.
  PyObject* current_executor;
  // _PyThreadStateImpl.asyncio_running_task. Strong reference.
  PyObject* asyncio_running_task;
} TaskState;

/**
 * Whether a promising task is currently executing. When this is true, `outer`
 * holds the state of the code that the task took over from, which is restored
 * when the task suspends or exits.
 *
 * A task can only ever take control from the event loop and always returns
 * control to the event loop. It is a bug to start or resume a task when in_task
 * is true.
 */
static bool in_task = false;
static TaskState outer;

/**
 * Move the per-task fields out of the thread state into `dst`. The thread
 * state is left in an inconsistent state, the caller must follow this up with
 * load_task_state() or init_fresh_task().
 */
static void
save_task_state(PyThreadState* tstate, TaskState* dst)
{
  dst->context = tstate->context;
  dst->current_frame = tstate->current_frame;
  // exc_info is the head of a linked list of _PyErr_StackItems. Generators and
  // coroutines push their own item while they run, and the bottom of the list
  // is always tstate->exc_state. If exc_info points at tstate->exc_state we
  // record NULL instead, since tstate->exc_state is an address inside the
  // shared thread state and load_task_state() has to recompute it rather than
  // reuse the pointer.
  dst->exc_info =
    tstate->exc_info == &tstate->exc_state ? NULL : tstate->exc_info;
  dst->exc_state = tstate->exc_state;
  dst->current_exception = tstate->current_exception;
  dst->py_recursion_remaining = tstate->py_recursion_remaining;
  dst->tracing = tstate->tracing;
  dst->what_event = tstate->what_event;
  dst->delete_later = tstate->delete_later;
  dst->datastack_chunk = tstate->datastack_chunk;
  dst->datastack_top = tstate->datastack_top;
  dst->datastack_limit = tstate->datastack_limit;
  dst->current_executor = tstate->current_executor;
  dst->asyncio_running_task = pystate_swap_asyncio_running_task(tstate, NULL);
}

/**
 * Move the per-task fields from `src` into the thread state. `src` is zeroed.
 */
static void
load_task_state(PyThreadState* tstate, TaskState* src)
{
  tstate->context = src->context;
  // Incrementing this to invalidate the contextvars cache which would otherwise
  // remain valid across the switch.
  tstate->context_ver++;
  tstate->current_frame = src->current_frame;
  tstate->exc_state = src->exc_state;
  tstate->exc_info = src->exc_info ? src->exc_info : &tstate->exc_state;
  tstate->current_exception = src->current_exception;
  tstate->py_recursion_remaining = src->py_recursion_remaining;
  tstate->tracing = src->tracing;
  tstate->what_event = src->what_event;
  tstate->delete_later = src->delete_later;
  tstate->datastack_chunk = src->datastack_chunk;
  tstate->datastack_top = src->datastack_top;
  tstate->datastack_limit = src->datastack_limit;
  tstate->current_executor = src->current_executor;
  PyObject* old =
    pystate_swap_asyncio_running_task(tstate, src->asyncio_running_task);
  assert(old == NULL);
  memset(src, 0, sizeof(*src));
}

/**
 * Set up the thread state for a brand new task. Called right after
 * save_task_state() in enter_promising_task(): the fields we inherit from the
 * caller are still on the thread state and everything else is replaced with a
 * blank slate. Steals a reference to `context`.
 */
static void
init_fresh_task(PyThreadState* tstate, PyObject* context)
{
  tstate->context = context;
  tstate->context_ver++;
  tstate->current_frame = NULL;
  memset(&tstate->exc_state, 0, sizeof(tstate->exc_state));
  tstate->exc_info = &tstate->exc_state;
  tstate->current_exception = NULL;
  // py_recursion_remaining, tracing, what_event: inherited from the caller.
  tstate->delete_later = NULL;
  tstate->datastack_chunk = NULL;
  tstate->datastack_top = NULL;
  tstate->datastack_limit = NULL;
  tstate->current_executor = NULL;
  // asyncio_running_task was set to NULL by save_task_state().
}

/**
 * Release everything owned by the task that is currently installed on the
 * thread state. Must be followed by load_task_state().
 */
static void
cleanup_task(PyThreadState* tstate)
{
  // The task's Python code has returned so the frame chain is back to where it
  // started.
  assert(tstate->current_frame == NULL);
  assert(tstate->exc_info == &tstate->exc_state);
  Py_CLEAR(tstate->context);
  Py_CLEAR(tstate->exc_state.exc_value);
  // _pyproxy_apply_promising moves the exception out before calling us, so
  // this should be NULL already.
  Py_CLEAR(tstate->current_exception);
  pystate_free_datastack(tstate->datastack_chunk);
  tstate->datastack_chunk = NULL;
  tstate->datastack_top = NULL;
  tstate->datastack_limit = NULL;
  Py_XDECREF(pystate_swap_asyncio_running_task(tstate, NULL));
}

/**
 * Start a new task. The task runs on the same thread state as its caller but
 * with a frame chain, exception stack, and contextvars context of its own. The
 * caller's state is stashed in `outer` and restored when the task suspends or
 * exits.
 *
 * The task's context is a copy of the caller's context, so contextvar changes
 * made by the task stay local to it.
 */
int
enter_promising_task(void)
{
  if (in_task) {
    // Entering a promising call yields to the event loop first so this should
    // not be reachable.
    PyErr_SetString(PyExc_SystemError,
                    "Cannot enter a promising task from inside another running "
                    "promising task. This is a bug in Pyodide.");
    return -1;
  }
  PyObject* context = PyContext_CopyCurrent();
  if (context == NULL) {
    return -1;
  }
  PyThreadState* tstate = PyThreadState_Get();
  save_task_state(tstate, &outer);
  init_fresh_task(tstate, context);
  in_task = true;
  return 0;
}

/**
 * Finish the current task and put back the caller's state.
 *
 * Any pending exception must have been moved out of the thread state before
 * calling this, see _pyproxy_apply_promising.
 */
void
exit_promising_task(void)
{
  assert(in_task);
  PyThreadState* tstate = PyThreadState_Get();
  cleanup_task(tstate);
  load_task_state(tstate, &outer);
  in_task = false;
}

/**
 * Suspend the current task: move its state off the thread state into a heap
 * allocated TaskState and restore the caller's state. saveState stores the
 * returned pointer in the JS state object and passes it back to
 * restoreTaskState when the task resumes.
 *
 * With the task's frames off the thread state, a suspended task looks like
 * Python code that isn't running, which is what the GC and other things that
 * walk current_frame expect. The task's objects are kept alive by their
 * reference counts.
 */
EMSCRIPTEN_KEEPALIVE TaskState*
captureTaskState(void)
{
  if (!in_task) {
    // validSuspender is supposed to prevent this. If it happens anyway, refuse
    // rather than corrupting the thread state.
    PyErr_SetString(PyExc_SystemError,
                    "Cannot stack switch: not inside a promising task. This is "
                    "a bug in Pyodide.");
    return NULL;
  }
  TaskState* saved = malloc(sizeof(TaskState));
  if (saved == NULL) {
    PyErr_NoMemory();
    return NULL;
  }
  PyThreadState* tstate = PyThreadState_Get();
  save_task_state(tstate, saved);
  load_task_state(tstate, &outer);
  in_task = false;
  return saved;
}

/**
 * Resume a suspended task: stash the current state in `outer` and install the
 * task's state. Frees `saved`.
 */
EMSCRIPTEN_KEEPALIVE void
restoreTaskState(TaskState* saved)
{
  assert(!in_task);
  PyThreadState* tstate = PyThreadState_Get();
  save_task_state(tstate, &outer);
  load_task_state(tstate, saved);
  free(saved);
  in_task = true;
}
