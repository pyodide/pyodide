#include "Python.h"
#include "emscripten.h"
#include "jslib.h"

// clang-format off
EM_JS(JsVal, syncifyHandler, (JsVal x), {
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
  syncifyHandler = new WebAssembly.Suspending(inner);
}
)
// clang-format on

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
 * Record the task thread state and the wasm call stack and argument stack
 * state. This is called by the JsvPromise_syncify just prior to suspending the
 * thread.
 *
 * _captureThreadState() also restores control to the main thread state, see
 * pystate.c.
 *
 * tstate->current_frame points into the stack, so detachCurrentFrame() nulls it
 * out to prevent crashes from code that walks the stack.
 */
EM_JS(JsVal, saveState, (void), {
  if (!validSuspender.value) {
    return Module.error;
  }
  const threadState = _captureThreadState();
  // clang-format off
  if (threadState === 0) {
    return Module.error;
  }
  // clang-format on
  const currentFrame = _detachCurrentFrame(threadState);
  const stackState = new StackState();
  return {
    threadState,
    currentFrame,
    stackState,
  };
});

/**
 * Restore the Python thread state and the wasm argument stack state. This is
 * called by JsvPromise_syncify upon resuming the thread. The argument is the
 * return value from save_state.
 */
EM_JS(void, restoreState, (JsVal state), {
  state.stackState.restore();
  _restoreThreadState(state.threadState, state.currentFrame);
  validSuspender.value = true;
});

JsVal
JsvPromise_Syncify(JsVal promise)
{
  JsVal state = saveState();
  if (JsvError_Check(state)) {
    return JS_ERROR;
  }
  JsVal result = syncifyHandler(promise);
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
