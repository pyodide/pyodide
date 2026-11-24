#include "Python.h"
#include "emscripten.h"
#include "jslib.h"

// The actual function that suspends.
//
// Promise rejections are caught by the JS try/catch in inner() below. However,
// a SuspendError (thrown when there is no suspender on the stack) is raised by
// the wasm-to-js wrapper itself before any JS frame runs, so no JS try/catch
// can see it. Thus, we additionally catch errors from wasm in
// syncify_catch_trampoline, where we do approximately:
//
// try {
//    return suspendForPromise(x);
// } catch(e) {
//    return set_syncify_error(e);
// }

// clang-format off
EM_JS(JsVal, suspendForPromise, (JsVal x), {
  return Module.error;
}

async function inner(x) {
  try {
    return await x;
  } catch (e) {
    if (e && e.pyodide_fatal_error) {
      throw e;
    }
    Module.syncify_error = e;
    return Module.error;
  }
}
if (jspiSupported) {
  suspendForPromise = new WebAssembly.Suspending(inner);
}
)
// clang-format on

// syncify_catch_trampoline calls suspendForPromise
__externref_t syncify_catch_trampoline(__externref_t);

// Called by syncify_catch_trampoline when it catches a SuspendError.
EM_JS(__externref_t, set_syncify_error, (__externref_t e), {
  // No fatal guard needed because the error must be a SuspendError.
  Module.syncify_error = e;
  return Module.error;
})

EM_JS(void, JsvPromise_Syncify_handleError, (void), {
  if (!Module.syncify_error) {
    // In this case we tried to syncify in a context where there is no
    // suspender. JsProxy.c checks for this case and sets the error flag
    // appropriately.
    return;
  }
  Module.handle_js_error(Module.syncify_error);
  delete Module.syncify_error;
})

/**
 * Record the per-task part of the Python thread state and the wasm argument
 * stack state. This is called by the JsvPromise_syncify just prior to
 * suspending the thread.
 *
 * _captureTaskState() moves the task's state off the thread state and puts the
 * caller's state back, see pystate.c.
 */
EM_JS(JsVal, saveState, (void), {
  if (!validSuspender.value) {
    return Module.error;
  }
  const taskState = _captureTaskState();
  // clang-format off
  if (taskState === 0) {
    return Module.error;
  }
  // clang-format on
  const stackState = new StackState();
  return {
    taskState,
    stackState,
  };
});

/**
 * Restore the per-task Python state and the wasm argument stack state. This is
 * called by JsvPromise_syncify upon resuming the thread. The argument is the
 * return value from save_state.
 */
EM_JS(void, restoreState, (JsVal state), {
  state.stackState.restore();
  _restoreTaskState(state.taskState);
  validSuspender.value = true;
});

JsVal
JsvPromise_Syncify(JsVal promise)
{
  JsVal state = saveState();
  if (JsvError_Check(state)) {
    return JS_ERROR;
  }
  JsVal result = syncify_catch_trampoline(promise);
  restoreState(state);
  if (JsvError_Check(result)) {
    JsvPromise_Syncify_handleError();
  }
  return result;
}

/**
 * Syncify for C syscall context: suspend WASM, await a promise that resolves
 * to int, and resume.
 *
 * This is a thin wrapper around JsvPromise_Syncify for use in socket syscall
 * overrides. At the syscall level the GIL is not held.
 * We reacquire the GIL via PyGILState_Ensure() before calling
 * JsvPromise_Syncify. After resuming, PyGILState_Release re-releases the GIL.
 */
int
syscall_syncify(__externref_t promise)
{
  PyGILState_STATE gilstate = PyGILState_Ensure();
  JsVal result = JsvPromise_Syncify(promise);
  int ret = JsvError_Check(result) ? -1 : JsvNum_toInt(result);
  PyGILState_Release(gilstate);
  return ret;
}
