#include "internal/pycore_frame.h"
#include <Python.h>

typedef struct
{
  _PyCFrame* cframe;
  int use_tracing;
  int recursion_depth;
  PyFrameObject* _top_frame;
  int trash_delete_nesting;
  _PyErr_StackItem exc_info;
  _PyInterpreterFrame* current_frame;
  _PyStackChunk* datastack_chunk;
  PyObject** datastack_top;
  PyObject** datastack_limit;
} P;

P*
captureThreadState()
{
  PyThreadState* tstate = PyThreadState_Get();
  P* state = (P*)malloc(sizeof(P));
  state->cframe = tstate->cframe;
  state->use_tracing = tstate->cframe->use_tracing;

  state->recursion_depth =
    tstate->recursion_limit - tstate->recursion_remaining;
  state->current_frame = tstate->cframe->current_frame;
  state->datastack_chunk = tstate->datastack_chunk;
  state->datastack_top = tstate->datastack_top;
  state->datastack_limit = tstate->datastack_limit;

  state->_top_frame = PyThreadState_GetFrame((PyThreadState*)tstate);
  // All versions of Python.
  state->trash_delete_nesting = tstate->trash_delete_nesting;
  state->exc_info = *tstate->exc_info;
  tstate->exc_info->exc_value = NULL;
  tstate->exc_info->previous_item = NULL;
  return state;
}

void
restoreThreadState(P* state)
{
  PyThreadState* tstate = PyThreadState_Get();

  tstate->recursion_remaining =
    tstate->recursion_limit - state->recursion_depth;

  tstate->cframe = state->cframe;
  tstate->cframe->use_tracing = state->use_tracing;

  tstate->cframe->current_frame = state->current_frame;
  tstate->datastack_chunk = state->datastack_chunk;
  tstate->datastack_top = state->datastack_top;
  tstate->datastack_limit = state->datastack_limit;

  Py_XDECREF(state->_top_frame);
  *tstate->exc_info = state->exc_info;
  tstate->trash_delete_nesting = state->trash_delete_nesting;
  free(state);
}
