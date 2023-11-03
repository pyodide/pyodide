#include "Python.h"
#include "emscripten.h"
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
  _PyErr_StackItem* exc_info;
  _PyErr_StackItem exc_state;
} ExceptionState;

ExceptionState
saveExceptionState(PyThreadState* tstate)
{
  ExceptionState es;
  es.exc_info = tstate->exc_info;
  es.exc_state = tstate->exc_state;
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
  int use_tracing;
  int recursion_depth;
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

  ps.use_tracing = tstate->cframe->use_tracing;
  ps.recursion_depth = tstate->recursion_limit - tstate->recursion_remaining;

  ps._top_frame = PyThreadState_GetFrame((PyThreadState*)tstate);
  Py_XDECREF(ps._top_frame);

  ps.trash_delete_nesting = tstate->trash_delete_nesting;

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

  tstate->cframe->use_tracing = ps.use_tracing;
  tstate->recursion_remaining = tstate->recursion_limit - ps.recursion_depth;

  tstate->trash_delete_nesting = ps.trash_delete_nesting;

  tstate->context = ps.context;
  Py_XDECREF(ps.context);
}

typedef struct
{
  PythonState ps;
  ExceptionState es;
} ThreadState;

EMSCRIPTEN_KEEPALIVE ThreadState*
captureThreadState()
{
  PyThreadState* tstate = PyThreadState_Get();
  ThreadState* state = (ThreadState*)malloc(sizeof(ThreadState));
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
  tstate->trash_delete_nesting = 0;
  tstate->cframe->current_frame = NULL;
  tstate->datastack_chunk = NULL;
  tstate->datastack_top = NULL;
  tstate->datastack_limit = NULL;
}
