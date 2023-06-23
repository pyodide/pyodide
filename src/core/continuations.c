#include <Python.h>

#include "emscripten.h"
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

// clang-format off
EM_JS(int, continuations_init_js, (), {
  initSuspenders();
})
// clang-format on

static bool type_reflection_available;

int
continuations_init(void)
{
  type_reflection_available = EM_ASM_INT({ return "Function" in WebAssembly; });
  return continuations_init_js();
}

// clang-format off
EM_JS(
PyObject*,
bootstrap_trampoline_js,
(PyCFunctionWithKeywords func, PyObject* self, PyObject* args, PyObject* kw),
{
    return wasmTableMirror[func](self, args, kw);
});
// clang-format on

static PyObject*
bootstrap_trampoline(PyCFunctionWithKeywords func,
                     PyObject* self,
                     PyObject* args,
                     PyObject* kw)
{
  return bootstrap_trampoline_js(func, self, args, kw);
}

EM_JS(int, count_params, (PyCFunctionWithKeywords func), {
  return WebAssembly.Function.type(wasmTableMirror[func]).parameters.length;
})

typedef PyObject* (*zero_arg)(void);
typedef PyObject* (*one_arg)(PyObject*);
typedef PyObject* (*two_arg)(PyObject*, PyObject*);
typedef PyObject* (*three_arg)(PyObject*, PyObject*, PyObject*);

// These are the Emscripten call trampolines that we patched out of CPython.
PyObject*
py_trampoline(PyCFunctionWithKeywords func,
              PyObject* self,
              PyObject* args,
              PyObject* kw)
{
  if (!type_reflection_available) {
    return bootstrap_trampoline(func, self, args, kw);
  } else {
    switch (count_params(func)) {
      case 0:
        return ((zero_arg)func)();
      case 1:
        return ((one_arg)func)(self);
      case 2:
        return ((two_arg)func)(self, args);
      case 3:
        return ((three_arg)func)(self, args, kw);
    }
  }
}

PyObject*
_PyCFunctionWithKeywords_TrampolineCall(PyCFunctionWithKeywords func,
                                        PyObject* self,
                                        PyObject* args,
                                        PyObject* kw)
{
  return py_trampoline(func, self, args, kw);
}

int
descr_set_trampoline_call(setter set,
                          PyObject* obj,
                          PyObject* value,
                          void* closure)
{
  return (int)py_trampoline(
    (PyCFunctionWithKeywords)set, obj, value, (PyObject*)closure);
}

PyObject*
descr_get_trampoline_call(getter get, PyObject* obj, void* closure)
{
  return py_trampoline(
    (PyCFunctionWithKeywords)get, obj, (PyObject*)closure, NULL);
}
