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
} AsyncioState;

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(_set_running_loop);

AsyncioState
saveAsyncioState()
{
  AsyncioState as;
  PyObject* asyncio_module = NULL;
  PyObject* loop = NULL;

  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);
  loop = _PyObject_CallMethodIdNoArgs(asyncio_module, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);

finally:
  Py_CLEAR(asyncio_module);
  as.loop = loop;
  return as;
}

void
cleanAsyncioState(AsyncioState as)
{
  Py_CLEAR(as.loop);
}

#define THREADSTATE_MAX_FREELIST 10

static PyThreadState* threadstate_freelist[THREADSTATE_MAX_FREELIST] = {};
static int threadstate_freelist_len = 0;

static PyThreadState*
new_tstate(void) {
  if (threadstate_freelist_len > 0) {
    threadstate_freelist_len--;
    return threadstate_freelist[threadstate_freelist_len];
  } else {
    return PyThreadState_New(PyInterpreterState_Get());
  }
}

static void
delete_tstate(PyThreadState* tstate) {
  if (threadstate_freelist_len == THREADSTATE_MAX_FREELIST) {
    PyThreadState_Delete(tstate);
  } else {
    threadstate_freelist[threadstate_freelist_len] = tstate;
    threadstate_freelist_len++;
  }
}

typedef struct
{
  AsyncioState as;
  PyThreadState* ts;
} ThreadState;

EMSCRIPTEN_KEEPALIVE ThreadState*
captureThreadState()
{
  ThreadState* res = malloc(sizeof(ThreadState));
  res->as = saveAsyncioState();
  res->ts = PyThreadState_Swap(new_tstate());

  PyObject* _asyncio_module = NULL;
  PyObject* t = NULL;
  _asyncio_module = PyImport_ImportModule("_asyncio");
  t = _PyObject_CallMethodIdOneArg(
    _asyncio_module, &PyId__set_running_loop, res->as.loop);

  Py_CLEAR(_asyncio_module);
  Py_CLEAR(t);

  return res;
}

EMSCRIPTEN_KEEPALIVE void
restoreThreadState(ThreadState* state)
{
  cleanAsyncioState(state->as);
  delete_tstate(PyThreadState_Swap(state->ts));
}
