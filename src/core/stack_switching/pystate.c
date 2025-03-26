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

int pystate_keepalive;

typedef struct
{
  PyObject* loop;
  PyObject* task;
} AsyncioState;

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(_current_tasks);
_Py_IDENTIFIER(_leave_task);
_Py_IDENTIFIER(_enter_task);

AsyncioState
saveAsyncioState()
{
  AsyncioState as;
  PyObject* asyncio_module = NULL;
  PyObject* _asyncio_module = NULL;
  PyObject* loop = NULL;
  PyObject* _current_tasks = NULL;
  PyObject* task = NULL;
  PyObject* status = NULL;
  Py_hash_t hash;
  bool success = false;

  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);
  _asyncio_module = PyImport_ImportModule("_asyncio");
  FAIL_IF_NULL(_asyncio_module);
  loop = _PyObject_CallMethodIdNoArgs(asyncio_module, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);
  _current_tasks = _PyObject_GetAttrId(_asyncio_module, &PyId__current_tasks);
  FAIL_IF_NULL(_current_tasks);
  hash = PyObject_Hash(loop);
  FAIL_IF_MINUS_ONE(hash);
  task = _PyDict_GetItem_KnownHash(_current_tasks, loop, hash);
  Py_XINCREF(task);
  if (task == NULL) {
    FAIL_IF_ERR_OCCURRED();
    goto success;
  }
  status = _PyObject_CallMethodIdObjArgs(
    _asyncio_module, &PyId__leave_task, loop, task, NULL);
  FAIL_IF_NULL(status);

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
  Py_CLEAR(_current_tasks);
  Py_CLEAR(status);
  as.loop = loop;
  as.task = task;
  return as;
}

void
restoreAsyncioState(AsyncioState as)
{
  if (as.task == NULL) {
    // We weren't in a task when we switched, so nothing to restore.
    return;
  }
  PyObject* _asyncio_module = NULL;
  PyObject* status = NULL;
  bool success = false;

  _asyncio_module = PyImport_ImportModule("_asyncio");
  FAIL_IF_NULL(_asyncio_module);
  status = _PyObject_CallMethodIdObjArgs(
    _asyncio_module, &PyId__enter_task, as.loop, as.task, NULL);
  FAIL_IF_NULL(status);

  success = true;
finally:
  if (!success) {
    // Might want to make this a fatal...
    PySys_WriteStderr(
      "Pyodide: Internal error occurred while unswitching stacks:\n");
    PyErr_Print();
  }
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
