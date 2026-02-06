#include "Python.h"
#include "emscripten.h"
#include "error_handling.h"
#include "python_unexposed.h"

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
// Changelog:
// - Python 3.14:
//   asyncio state (running loop and task) is now stored directly
//   in _PyThreadStateImpl fields (asyncio_running_loop, asyncio_running_task)
//   instead of in a global dictionary. This means that when we create a new
//   PyThreadState for stack switching, we must explicitly set both the loop AND
//   the task on the new thread state.

int pystate_keepalive;

typedef struct
{
  PyObject* loop;
  PyObject* task;
} AsyncioState;

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(current_task);

AsyncioState
saveAsyncioState()
{
  AsyncioState as;
  PyObject* asyncio_module = NULL;
  PyObject* _asyncio_module = NULL;
  PyObject* loop = NULL;
  PyObject* task = NULL;
  bool success = false;

  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);
  _asyncio_module = PyImport_ImportModule("_asyncio");
  FAIL_IF_NULL(_asyncio_module);
  loop = _PyObject_CallMethodIdNoArgs(asyncio_module, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);
  task = _PyObject_CallMethodIdOneArg(_asyncio_module, &PyId_current_task, loop);
  Py_XINCREF(task);
  if (task == NULL) {
    FAIL_IF_ERR_OCCURRED();
    goto success;
  }

success:
  success = true;
finally:
  if (!success) {
    // Might want to make this a fatal...
    PySys_WriteStderr(
      "Pyodide: Internal error occurred while switching stacks:\n");
    PyErr_Print();
  }
  Py_CLEAR(asyncio_module);
  Py_CLEAR(_asyncio_module);
  as.loop = loop;
  as.task = task;
  return as;
}

void
restoreAsyncioState(AsyncioState as)
{
  Py_CLEAR(as.loop);
  Py_CLEAR(as.task);
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
  ThreadState* res = malloc(sizeof(ThreadState));
  res->as = saveAsyncioState();
  PyThreadState* tstate;
  if (threadstate_freelist_len > 0) {
    tstate = threadstate_freelist[threadstate_freelist_len - 1];
    threadstate_freelist_len--;
  } else {
    tstate = PyThreadState_New(PyInterpreterState_Get());
  }
  res->ts = PyThreadState_Swap(tstate);

  PyObject* _asyncio_module = NULL;
  PyObject* t = NULL;
  _asyncio_module = PyImport_ImportModule("_asyncio");
  _Py_IDENTIFIER(_set_running_loop);
  t = _PyObject_CallMethodIdOneArg(
    _asyncio_module, &PyId__set_running_loop, res->as.loop);

  Py_CLEAR(_asyncio_module);
  Py_CLEAR(t);

  return res;
}

EMSCRIPTEN_KEEPALIVE void
restoreThreadState(ThreadState* state)
{
  restoreAsyncioState(state->as);
  PyThreadState* res = PyThreadState_Swap(state->ts);
  if (threadstate_freelist_len == THREADSTATE_MAX_FREELIST) {
    PyThreadState_Delete(res);
  } else {
    threadstate_freelist[threadstate_freelist_len] = res;
    threadstate_freelist_len++;
  }
}
