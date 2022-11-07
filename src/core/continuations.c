#include <Python.h>

typedef struct
{
  CFrame* cframe;
  int use_tracing;
  int recursion_depth;
  PyFrameObject* _top_frame;
  int trash_delete_nesting;
} P;

P*
captureThreadState()
{
  PyThreadState* tstate = PyThreadState_Get();
  P* state = (P*)malloc(sizeof(P));
  state->cframe = tstate->cframe;
  state->recursion_depth = tstate->recursion_depth;
  state->use_tracing = tstate->cframe->use_tracing;
  state->_top_frame = tstate->frame;
  Py_XINCREF(state->_top_frame);
  // All versions of Python.
  state->trash_delete_nesting = tstate->trash_delete_nesting;
  return state;
}

void
restoreThreadState(P* state)
{
  PyThreadState* tstate = PyThreadState_Get();
  tstate->cframe = state->cframe;
  tstate->recursion_depth = state->recursion_depth;
  tstate->cframe->use_tracing = state->use_tracing;
  tstate->frame = state->_top_frame;
  tstate->trash_delete_nesting = state->trash_delete_nesting;
  free(state);
}
