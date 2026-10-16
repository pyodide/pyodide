// Note: This file manages the Python stack / thread state when stack switching.
// It needs to be audited on every Python update.
//
// Separated into its own file because it touches internal headers. The task
// switching logic itself lives in pystate.c, this file only exposes the handful
// of operations that need internal headers.

// All internal headers require Py_BUILD_CORE_MODULE to be defined.
#define Py_BUILD_CORE_MODULE 1

#include <stdbool.h>

#include "Python.h"
#include "internal/pycore_obmalloc.h"
#include "internal/pycore_tstate.h"

/**
 * asyncio records the task whose step is currently executing on the thread
 * state. This is part of the per-task state so we swap it in and out when we
 * switch tasks. Returns the old value (a strong reference or NULL) and steals a
 * reference to `task`.
 */
PyObject*
pystate_swap_asyncio_running_task(PyThreadState* tstate, PyObject* task)
{
  _PyThreadStateImpl* impl = (_PyThreadStateImpl*)tstate;
  PyObject* old = impl->asyncio_running_task;
  impl->asyncio_running_task = task;
  return old;
}

/**
 * Free a chain of data stack chunks. This mirrors clear_datastack() in
 * CPython's pystate.c. Each task starts with datastack_chunk == NULL so the
 * frame allocator makes it a root chunk of its own, which never gets popped
 * and which we have to free when the task finishes.
 */
void
pystate_free_datastack(_PyStackChunk* chunk)
{
  while (chunk != NULL) {
    _PyStackChunk* prev = chunk->previous;
    _PyObject_VirtualFree(chunk, chunk->size);
    chunk = prev;
  }
}
