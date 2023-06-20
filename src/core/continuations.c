#include <Python.h>

#include "internal/pycore_frame.h"

// This file deals with Python stack / thread state.
// continuations.js deals with the C stack state

// This is taken from
// https://github.com/python-greenlet/greenlet/blob/master/src/greenlet/greenlet_greenlet.hpp
//
// When updating the major Python version it will be necessary to look at that
// file.
//
// See also
// https://github.com/python/cpython/pull/32303
// which would move more of this logic into upstream CPython

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

// Defines continuations_init_js
#include "continuations.gen.js"

int
continuations_init(void)
{
  return continuations_init_js();
}

bool has_suspender = false;

EM_JS(
  PyObject*,
  normal_trampoline,
  (PyCFunctionWithKeywords func, PyObject* self, PyObject* args, PyObject* kw),
  { return wasmTable.get(func)(self, args, kw); });

typedef PyObject*
Trampoline(PyCFunctionWithKeywords func,
           PyObject* self,
           PyObject* args,
           PyObject* kw);

Trampoline* async_trampoline = NULL;

PyObject*
_PyCFunctionWithKeywords_TrampolineCall(PyCFunctionWithKeywords func,
                                        PyObject* self,
                                        PyObject* args,
                                        PyObject* kw)
{
  if (has_suspender) {
    return async_trampoline(func, self, args, kw);
  } else {
    return normal_trampoline(func, self, args, kw);
  }
}

int
descr_set_trampoline_call(setter set,
                          PyObject* obj,
                          PyObject* value,
                          void* closure)
{
  if (has_suspender) {
    return (int)async_trampoline(
      (PyCFunctionWithKeywords)set, obj, value, (PyObject*)closure);
  } else {
    return (int)normal_trampoline(
      (PyCFunctionWithKeywords)set, obj, value, (PyObject*)closure);
  }
}

PyObject*
descr_get_trampoline_call(getter get, PyObject* obj, void* closure)
{
  if (has_suspender) {
    return async_trampoline(
      (PyCFunctionWithKeywords)get, obj, (PyObject*)closure, NULL);
  } else {
    return normal_trampoline(
      (PyCFunctionWithKeywords)get, obj, (PyObject*)closure, NULL);
  }
}
