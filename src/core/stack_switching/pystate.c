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

_Py_IDENTIFIER(get_event_loop);
_Py_IDENTIFIER(_set_running_loop);

#define THREADSTATE_MAX_FREELIST 10

static PyThreadState* threadstate_freelist[THREADSTATE_MAX_FREELIST] = {};
static int threadstate_freelist_len = 0;

static PyThreadState*
new_tstate(void)
{
  if (threadstate_freelist_len > 0) {
    threadstate_freelist_len--;
    return threadstate_freelist[threadstate_freelist_len];
  } else {
    return PyThreadState_New(PyInterpreterState_Get());
  }
}

static void
delete_tstate(PyThreadState* tstate)
{
  if (threadstate_freelist_len == THREADSTATE_MAX_FREELIST) {
    PyThreadState_Delete(tstate);
  } else {
    threadstate_freelist[threadstate_freelist_len] = tstate;
    threadstate_freelist_len++;
  }
}

EMSCRIPTEN_KEEPALIVE void
restoreThreadState(PyThreadState* state)
{
  delete_tstate(PyThreadState_Swap(state));
}

EMSCRIPTEN_KEEPALIVE PyThreadState*
captureThreadState()
{
  PyObject* asyncio_module = NULL;
  PyObject* loop = NULL;
  PyObject* tmp = NULL;
  PyThreadState* result = NULL;

  // We need to set the event loop in the new thread state to be the same as the
  // event loop in the old thread state.

  // 1. get the event loop from the old thread state
  asyncio_module = PyImport_ImportModule("asyncio");
  FAIL_IF_NULL(asyncio_module);
  loop = _PyObject_CallMethodIdNoArgs(asyncio_module, &PyId_get_event_loop);
  FAIL_IF_NULL(loop);

  // 2. swap thread state
  result = PyThreadState_Swap(new_tstate());

  // 3. set the running event loop in the new thread state
  tmp =
    _PyObject_CallMethodIdOneArg(asyncio_module, &PyId__set_running_loop, loop);
  if (tmp == NULL) {
    PyErr_Clear();
    restoreThreadState(result);
    result = NULL;
    PyErr_SetString(PyExc_SystemError, "Unexpected error when stack switching");
    FAIL();
  }

finally:
  Py_CLEAR(asyncio_module);
  Py_CLEAR(loop);
  Py_CLEAR(tmp);

  return result;
}
