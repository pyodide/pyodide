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

// For the new JSPI API, use a regular function (not async) that returns a Promise.
// Using an async function creates JS frames that JSPI cannot suspend through.
function innerSync(x, y) {
  const promise = x ?? y;
  return Promise.resolve(promise).catch(e => {
    if (e && e.pyodide_fatal_error) {
      throw e;
    }
    Module.syncify_error = e;
    return Module.error;
  });
}

// For the old JSPI API, keep the async function as it works differently.
async function innerAsync(x, y) {
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
  syncifyHandler = new WebAssembly.Suspending(innerSync);
} else if (oldJspiSupported) {
  syncifyHandler = new WebAssembly.Function(
    { parameters: ["externref", "externref"], results: ["externref"] },
    innerAsync,
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
  console.log('[DEBUG] saveState: Starting');
  if (!validSuspender.value) {
    console.log('[DEBUG] saveState: ERROR - No valid suspender');
    return Module.error;
  }
  console.log('[DEBUG] saveState: Creating StackState');
  const stackState = new StackState();
  console.log('[DEBUG] saveState: Calling _captureThreadState');
  const threadState = _captureThreadState();
  console.log('[DEBUG] saveState: threadState:', threadState);
  const state = {
    threadState,
    stackState,
    suspender : suspenderGlobal.value,
  };
  console.log('[DEBUG] saveState: Returning state');
  return state;
});

/**
 * Restore the Python thread state and the wasm argument stack state. This is
 * called by the hiwire_syncify wasm module upon resuming the thread. The
 * argument is the return value from save_state.
 */
EM_JS(void, restoreState, (JsVal state), {
  console.log('[DEBUG] restoreState: Starting');
  console.log('[DEBUG] restoreState: Restoring stack state');
  state.stackState.restore();
  console.log('[DEBUG] restoreState: Calling _restoreThreadState');
  _restoreThreadState(state.threadState);
  console.log('[DEBUG] restoreState: Setting suspender and validSuspender');
  suspenderGlobal.value = state.suspender;
  validSuspender.value = true;
  console.log('[DEBUG] restoreState: Completed');
});

JsVal
JsvPromise_Syncify(JsVal promise)
{
  printf("[DEBUG] JsvPromise_Syncify: Starting\n");
  printf("[DEBUG] JsvPromise_Syncify: Calling saveState\n");
  JsVal state = saveState();
  if (JsvError_Check(state)) {
    printf("[DEBUG] JsvPromise_Syncify: ERROR - saveState failed\n");
    return JS_ERROR;
  }
  printf("[DEBUG] JsvPromise_Syncify: saveState succeeded\n");
  printf("[DEBUG] JsvPromise_Syncify: Getting suspender\n");
  JsVal suspender = get_suspender();
  printf("[DEBUG] JsvPromise_Syncify: Got suspender\n");
  printf("[DEBUG] JsvPromise_Syncify: Calling syncifyHandler\n");
  JsVal result = syncifyHandler(suspender, promise);
  printf("[DEBUG] JsvPromise_Syncify: syncifyHandler returned\n");
  printf("[DEBUG] JsvPromise_Syncify: Calling restoreState\n");
  restoreState(state);
  printf("[DEBUG] JsvPromise_Syncify: restoreState completed\n");
  if (JsvError_Check(result)) {
    printf("[DEBUG] JsvPromise_Syncify: ERROR - result is error, handling\n");
    JsvPromise_Syncify_handleError();
  }
  printf("[DEBUG] JsvPromise_Syncify: Returning result\n");
  return result;
}
