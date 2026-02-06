#include "Python.h"
#include "emscripten.h"
#include "error_handling.h"
#include "python_unexposed.h"
#include <stdio.h>

// This file manages the Python stack / thread state when stack switching.
//
// The functions exported here are used in suspenders.mjs, in save_state,
// restore_state, and promisingApply.
//
// The logic here is inspired by:
// https://github.com/python-greenlet/greenlet/blob/master/src/greenlet/greenlet_greenlet.hpp
//
// When updating the major Python version it will be necessary to look at that
// file.
//
// See also https://github.com/python/cpython/pull/32303 which would move more
// of this logic into upstream CPython
//
// Python 3.14 IMPORTANT CHANGE:
// In Python 3.14, asyncio state (running loop and task) is now stored directly
// in _PyThreadStateImpl fields (asyncio_running_loop, asyncio_running_task)
// instead of in a global dictionary. This means that when we create a new
// PyThreadState for stack switching, we must explicitly set both the loop AND
// the task on the new thread state.
//
// We no longer use _enter_task/_leave_task because:
// 1. _leave_task clears asyncio_running_task on the ORIGINAL thread state
// 2. When we swap back to ORIGINAL, it would have task=NULL
// 3. Instead, we preserve ORIGINAL's state and just copy loop+task to NEW

int pystate_keepalive;

typedef struct
{
  PyObject* loop;
  PyObject* task;
} AsyncioState;

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(current_task);

// saveAsyncioState: Get the current loop and task without modifying the
// current thread state. In Python 3.14+, we must NOT call _leave_task here
// because that would clear asyncio_running_task on the original thread state,
// and when we swap back, the original would incorrectly have task=NULL.
AsyncioState
saveAsyncioState()
{
  printf("[DEBUG] saveAsyncioState: Starting\n");
  AsyncioState as;
  PyObject* asyncio_module = NULL;
  PyObject* _asyncio_module = NULL;
  PyObject* loop = NULL;
  PyObject* task = NULL;
  bool success = false;

  printf("[DEBUG] saveAsyncioState: Importing asyncio module\n");
  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);
  printf("[DEBUG] saveAsyncioState: asyncio module imported successfully\n");
  printf("[DEBUG] saveAsyncioState: Importing _asyncio module\n");
  _asyncio_module = PyImport_ImportModule("_asyncio");
  FAIL_IF_NULL(_asyncio_module);
  printf("[DEBUG] saveAsyncioState: _asyncio module imported successfully\n");
  printf("[DEBUG] saveAsyncioState: Getting event loop\n");
  loop = _PyObject_CallMethodIdNoArgs(asyncio_module, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);
  printf("[DEBUG] saveAsyncioState: Event loop obtained: %p\n", (void*)loop);
  printf("[DEBUG] saveAsyncioState: Getting current task\n");
  task = _PyObject_CallMethodIdOneArg(_asyncio_module, &PyId_current_task, loop);
  Py_XINCREF(task);
  if (task == NULL) {
    printf("[DEBUG] saveAsyncioState: No current task (task is NULL)\n");
    FAIL_IF_ERR_OCCURRED();
    printf("[DEBUG] saveAsyncioState: No error occurred, not in a task context\n");
    goto success;
  }
  printf("[DEBUG] saveAsyncioState: Current task found: %p\n", (void*)task);
  // Python 3.14+: Do NOT call _leave_task here. We just save references.
  // The original thread state keeps its asyncio state intact.
  printf("[DEBUG] saveAsyncioState: Saved task reference (no _leave_task call)\n");

success:
  printf("[DEBUG] saveAsyncioState: Success path reached\n");
  success = true;
finally:
  if (!success) {
    printf("[DEBUG] saveAsyncioState: ERROR - Failed to save asyncio state\n");
    // Might want to make this a fatal...
    PySys_WriteStderr(
      "Pyodide: Internal error occurred while switching stacks:\n");
    PyErr_Print();
  }
  Py_CLEAR(asyncio_module);
  Py_CLEAR(_asyncio_module);
  as.loop = loop;
  as.task = task;
  printf("[DEBUG] saveAsyncioState: Returning - loop: %p, task: %p\n", (void*)loop, (void*)task);
  return as;
}

// In Python 3.14+, we don't modify asyncio state during stack switching.
// ORIGINAL thread state keeps its loop/task intact, NEW has loop set but task=NULL.
// This function just cleans up the saved references.
void
restoreAsyncioState(AsyncioState as)
{
  printf("[DEBUG] restoreAsyncioState: Starting - loop: %p, task: %p\n", (void*)as.loop, (void*)as.task);
  printf("[DEBUG] restoreAsyncioState: Cleaning up saved references\n");
  Py_CLEAR(as.loop);
  Py_CLEAR(as.task);
  printf("[DEBUG] restoreAsyncioState: Completed\n");
}

typedef struct
{
  AsyncioState as;
  PyThreadState* ts;
} ThreadState;

#define THREADSTATE_MAX_FREELIST 10

PyThreadState* threadstate_freelist[THREADSTATE_MAX_FREELIST] = {};
int threadstate_freelist_len = 0;

EMSCRIPTEN_KEEPALIVE ThreadState*
captureThreadState()
{
  printf("[DEBUG] captureThreadState: Starting\n");
  ThreadState* res = malloc(sizeof(ThreadState));
  printf("[DEBUG] captureThreadState: Allocated ThreadState: %p\n", (void*)res);
  printf("[DEBUG] captureThreadState: Calling saveAsyncioState\n");
  res->as = saveAsyncioState();
  printf("[DEBUG] captureThreadState: saveAsyncioState completed\n");
  PyThreadState* tstate;
  if (threadstate_freelist_len > 0) {
    printf("[DEBUG] captureThreadState: Reusing thread state from freelist (len=%d)\n", threadstate_freelist_len);
    tstate = threadstate_freelist[threadstate_freelist_len - 1];
    threadstate_freelist_len--;
  } else {
    printf("[DEBUG] captureThreadState: Creating new thread state\n");
    tstate = PyThreadState_New(PyInterpreterState_Get());
  }
  printf("[DEBUG] captureThreadState: New thread state: %p\n", (void*)tstate);
  printf("[DEBUG] captureThreadState: Swapping thread state\n");
  res->ts = PyThreadState_Swap(tstate);
  printf("[DEBUG] captureThreadState: Previous thread state: %p\n", (void*)res->ts);

  PyObject* _asyncio_module = NULL;
  PyObject* t = NULL;
  printf("[DEBUG] captureThreadState: Importing _asyncio module\n");
  _asyncio_module = PyImport_ImportModule("_asyncio");
  _Py_IDENTIFIER(_set_running_loop);
  printf("[DEBUG] captureThreadState: Setting running loop: %p\n", (void*)res->as.loop);
  t = _PyObject_CallMethodIdOneArg(
    _asyncio_module, &PyId__set_running_loop, res->as.loop);
  printf("[DEBUG] captureThreadState: _set_running_loop completed\n");
  // NOTE: We intentionally do NOT set the task on the NEW thread state.
  // The NEW thread state should have asyncio_running_task = NULL so that
  // the event loop can properly enter other tasks while we're suspended.
  // The ORIGINAL thread state still has the correct task set, and when we
  // restore (swap back to ORIGINAL), the task context will be correct.

  Py_CLEAR(_asyncio_module);
  Py_CLEAR(t);
  printf("[DEBUG] captureThreadState: Returning ThreadState: %p\n", (void*)res);
  return res;
}

EMSCRIPTEN_KEEPALIVE void
restoreThreadState(ThreadState* state)
{
  printf("[DEBUG] restoreThreadState: Starting with ThreadState: %p\n", (void*)state);
  printf("[DEBUG] restoreThreadState: Calling restoreAsyncioState\n");
  restoreAsyncioState(state->as);
  printf("[DEBUG] restoreThreadState: restoreAsyncioState completed\n");
  printf("[DEBUG] restoreThreadState: Swapping back to thread state: %p\n", (void*)state->ts);
  PyThreadState* res = PyThreadState_Swap(state->ts);
  printf("[DEBUG] restoreThreadState: Swapped thread state: %p\n", (void*)res);
  if (threadstate_freelist_len == THREADSTATE_MAX_FREELIST) {
    printf("[DEBUG] restoreThreadState: Freelist full, deleting thread state\n");
    PyThreadState_Delete(res);
  } else {
    printf("[DEBUG] restoreThreadState: Adding thread state to freelist (len=%d)\n", threadstate_freelist_len);
    threadstate_freelist[threadstate_freelist_len] = res;
    threadstate_freelist_len++;
  }
  printf("[DEBUG] restoreThreadState: Completed\n");
}
