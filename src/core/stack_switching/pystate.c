#include "Python.h"
#include "emscripten.h"
#include "error_handling.h"
#include "internal/pycore_frame.h"

// This file manages the Python stack / thread state when stack switching.
//
// The functions exported here are used in suspenders.mjs, in save_state,
// restore_state, and promisingApply.
//
// The logic here is inspired by:
// https://github.com/python-greenlet/greenlet/blob/master/src/greenlet/greenlet_greenlet.hpp
//
// The CFrame stuff is particularly subtle.
//
// When updating the major Python version it will be necessary to look at that
// file.
//
// See also https://github.com/python/cpython/pull/32303 which would move more
// of this logic into upstream CPython

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
  if (task == NULL) {
    Py_CLEAR(loop);
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
  _PyErr_StackItem* exc_info;
  _PyErr_StackItem exc_state;
} ExceptionState;

ExceptionState
saveExceptionState(PyThreadState* tstate)
{
  ExceptionState es;
  es.exc_info = tstate->exc_info;
  es.exc_state = tstate->exc_state;
  // Clear exc_state without decrementing any refcounts (we moved ownership to
  // es) See test_switch_from_except_block for a test case for this.
  tstate->exc_state.exc_value = NULL;
  tstate->exc_state.previous_item = NULL;
  tstate->exc_info = &tstate->exc_state;
  return es;
}

void
restoreExceptionState(PyThreadState* tstate, ExceptionState es)
{
  tstate->exc_state = es.exc_state;
  tstate->exc_info = es.exc_info ? es.exc_info : &es.exc_state;

  es.exc_info = NULL;
  es.exc_state.exc_value = NULL;
  es.exc_state.previous_item = NULL;
}

typedef struct
{
  PyFrameObject* _top_frame;
  _PyCFrame* cframe;
  int py_recursion_depth;
  int c_recursion_depth;
  int trash_delete_nesting;
  _PyInterpreterFrame* current_frame;
  _PyStackChunk* datastack_chunk;
  PyObject** datastack_top;
  PyObject** datastack_limit;
  PyObject* context;
} PythonState;

PythonState
savePythonState(PyThreadState* tstate)
{
  PythonState ps;

  ps.cframe = tstate->cframe;
  ps.current_frame = tstate->cframe->current_frame;
  ps.datastack_chunk = tstate->datastack_chunk;
  ps.datastack_top = tstate->datastack_top;
  ps.datastack_limit = tstate->datastack_limit;
  tstate->datastack_chunk = NULL;
  tstate->datastack_top = NULL;
  tstate->datastack_limit = NULL;

  ps.py_recursion_depth =
    tstate->py_recursion_limit - tstate->py_recursion_remaining;
  ps.c_recursion_depth = C_RECURSION_LIMIT - tstate->c_recursion_remaining;

  ps._top_frame = PyThreadState_GetFrame((PyThreadState*)tstate);
  Py_XDECREF(ps._top_frame);

  ps.trash_delete_nesting = tstate->trash.delete_nesting;

  ps.context = tstate->context;
  Py_XINCREF(ps.context);
  return ps;
}

void
restorePythonState(PyThreadState* tstate, PythonState ps)
{
  tstate->cframe = ps.cframe;
  tstate->cframe->current_frame = ps.current_frame;
  tstate->datastack_chunk = ps.datastack_chunk;
  tstate->datastack_top = ps.datastack_top;
  tstate->datastack_limit = ps.datastack_limit;

  tstate->py_recursion_remaining =
    tstate->py_recursion_limit - ps.py_recursion_depth;
  tstate->c_recursion_remaining = C_RECURSION_LIMIT - ps.c_recursion_depth;

  tstate->trash.delete_nesting = ps.trash_delete_nesting;

  tstate->context = ps.context;
  Py_XDECREF(ps.context);
}

typedef struct
{
  AsyncioState as;
  PythonState ps;
  ExceptionState es;
} ThreadState;

EMSCRIPTEN_KEEPALIVE ThreadState*
captureThreadState()
{
  PyThreadState* tstate = PyThreadState_Get();
  ThreadState* state = (ThreadState*)malloc(sizeof(ThreadState));
  state->as = saveAsyncioState();
  state->es = saveExceptionState(tstate);
  state->ps = savePythonState(tstate);
  return state;
}

EMSCRIPTEN_KEEPALIVE void
restoreThreadState(ThreadState* state)
{
  PyThreadState* tstate = PyThreadState_Get();
  restoreExceptionState(tstate, state->es);
  restorePythonState(tstate, state->ps);
  restoreAsyncioState(state->as);
  free(state);
}

EMSCRIPTEN_KEEPALIVE int size_of_cframe = sizeof(_PyCFrame);

EMSCRIPTEN_KEEPALIVE _PyCFrame*
get_cframe()
{
  PyThreadState* tstate = PyThreadState_Get();
  return tstate->cframe;
}

EMSCRIPTEN_KEEPALIVE void
restore_cframe(_PyCFrame* frame)
{
  PyThreadState* tstate = PyThreadState_Get();
  tstate->cframe = frame;
}

EMSCRIPTEN_KEEPALIVE void
set_new_cframe(_PyCFrame* frame)
{
  PyThreadState* tstate = PyThreadState_Get();
  *frame = *tstate->cframe;
  tstate->cframe = frame;
  tstate->cframe->previous = &PyThreadState_GET()->root_cframe;
  tstate->cframe->current_frame = NULL;
  tstate->trash.delete_nesting = 0;
  tstate->py_recursion_remaining = tstate->py_recursion_limit;
  tstate->c_recursion_remaining = C_RECURSION_LIMIT;
}

EMSCRIPTEN_KEEPALIVE void
exit_cframe(_PyCFrame* frame)
{
  PyThreadState* tstate = PyThreadState_Get();
  _PyStackChunk* chunk = tstate->datastack_chunk;

  PyObjectArenaAllocator alloc;
  PyObject_GetArenaAllocator(&alloc);

  tstate->cframe = frame;
  tstate->datastack_chunk = NULL;
  tstate->datastack_top = NULL;
  tstate->datastack_limit = NULL;

  if (!alloc.free) {
    return;
  }

  while (chunk) {
    _PyStackChunk* prev = chunk->previous;
    chunk->previous = NULL;
    alloc.free(alloc.ctx, chunk, chunk->size);
    chunk = prev;
  }
}
