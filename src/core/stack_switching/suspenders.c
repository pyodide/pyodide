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

/**
 * Save only the WebAssembly stack state (not Python thread state).
 * This is for use in low-level contexts like syscalls where the GIL
 * may not be held.
 */
EM_JS(JsVal, saveStateSimple, (void), {
  if (!validSuspender.value) {
    return Module.error;
  }
  const stackState = new StackState();
  return {
    stackState,
    suspender : suspenderGlobal.value,
  };
});

/**
 * Restore only the WebAssembly stack state (not Python thread state).
 */
EM_JS(void, restoreStateSimple, (JsVal state), {
  state.stackState.restore();
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

/**
 * A lightweight version of JsvPromise_Syncify that only saves/restores
 * WebAssembly stack state, without touching Python thread state.
 *
 * This is designed for use in low-level contexts like syscall implementations
 * where the GIL may not be held and Python thread state may be inconsistent.
 */
JsVal
JsvPromise_SyncifySimple(JsVal promise)
{
  JsVal state = saveStateSimple();
  if (JsvError_Check(state)) {
    return JS_ERROR;
  }
  JsVal suspender = get_suspender();
  JsVal result = syncifyHandler(suspender, promise);
  restoreStateSimple(state);
  if (JsvError_Check(result)) {
    JsvPromise_Syncify_handleError();
  }
  return result;
}

