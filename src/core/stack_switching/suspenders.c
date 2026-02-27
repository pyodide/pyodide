#include "Python.h"
#include "emscripten.h"
#include "jslib.h"

EM_JS(void, set_suspender, (JsVal suspender), {
  suspenderGlobal.value = suspender;
})

// clang-format off
EM_JS(JsVal, get_suspender, (), {
  return suspenderGlobal.value;
})

EM_JS(JsVal, syncifyHandler, (JsVal x, JsVal y), {
  return Module.error;
}

async function inner(x, y) {
  // In the old JSPI API, we get the promise as first argument.
  // In the new JSPI API we get it as the second argument.
  try {
    return await (x ?? y);
  } catch (e) {
    if (e && e.pyodide_fatal_error) {
      throw e;
    }
    Module.syncify_error = e;
    return Module.error;
  }
}
if (newJspiSupported) {
  syncifyHandler = new WebAssembly.Suspending(inner);
} else if (oldJspiSupported) {
  syncifyHandler = new WebAssembly.Function(
    { parameters: ["externref", "externref"], results: ["externref"] },
    inner,
    { suspending: "first" }
  );
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
 * Record the current Python thread state and the wasm call stack and argument
 * stack state. This is called by the hiwire_syncify wasm module just prior to
 * suspending the thread. `hiwire_syncify` uses `externref` for the return value
 * so we don't need to wrap this in a hiwire ID.
 */
EM_JS(JsVal, saveState, (void), {
  if (!validSuspender.value) {
    return Module.error;
  }
  const stackState = new StackState();
  const threadState = _captureThreadState();
  return {
    threadState,
    stackState,
    suspender : suspenderGlobal.value,
  };
});

/**
 * Restore the Python thread state and the wasm argument stack state. This is
 * called by the hiwire_syncify wasm module upon resuming the thread. The
 * argument is the return value from save_state.
 */
EM_JS(void, restoreState, (JsVal state), {
  state.stackState.restore();
  _restoreThreadState(state.threadState);
  suspenderGlobal.value = state.suspender;
  validSuspender.value = true;
});

JsVal
JsvPromise_Syncify(JsVal promise)
{
  JsVal state = saveState();
  if (JsvError_Check(state)) {
    return JS_ERROR;
  }
  JsVal suspender = get_suspender();
  JsVal result = syncifyHandler(suspender, promise);
  restoreState(state);
  if (JsvError_Check(result)) {
    JsvPromise_Syncify_handleError();
  }
  return result;
}

// clang-format off

/**
 * Convert a JsVal holding a JS number to a C int.
 * Used by syscall_syncify to extract the integer result from JsvPromise_Syncify.
 */
EM_JS(int, _JsvNum_toInt, (JsVal v), {
  return v | 0;
})

// clang-format on

/**
 * Syncify for C syscall context: suspend WASM, await a promise that resolves
 * to int, and resume.
 *
 * This is a thin wrapper around JsvPromise_Syncify for use in socket syscall
 * overrides. At the syscall level the GIL is not held: CPython's socketmodule.c
 * wraps connect()/recv() in Py_BEGIN_ALLOW_THREADS which releases the GIL and
 * sets PyThreadState to NULL. We reacquire the GIL via PyGILState_Ensure()
 * before calling JsvPromise_Syncify, which handles the full state save/restore
 * (Python thread state, asyncio task state, WASM stack state). After resuming,
 * PyGILState_Release re-releases the GIL to match what socketmodule.c expects.
 *
 * PyGILState_Ensure uses a separate thread-local storage (gilstate TSS) that is
 * NOT cleared by Py_BEGIN_ALLOW_THREADS, so it can find the valid tstate and
 * reacquire the GIL even from this context.
 */
int
syscall_syncify(__externref_t promise)
{
  PyGILState_STATE gilstate = PyGILState_Ensure();
  JsVal result = JsvPromise_Syncify(promise);
  int ret = JsvError_Check(result) ? -1 : _JsvNum_toInt(result);
  PyGILState_Release(gilstate);
  return ret;
}
