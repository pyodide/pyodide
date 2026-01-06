export let suspenderGlobal = { value: null };
export let validSuspender = { value: false };

let promisingApplyHandler;
export function promisingApply(...args) {
  // validSuspender is a flag so that we can ask for permission before trying to
  // suspend.
  validSuspender.value = true;
  // Record the current stack position. Used in stack_state.mjs
  Module.stackStop = stackSave();
  return promisingApplyHandler(...args);
}

let promisingRunMainHandler;
export function promisingRunMain(...args) {
  // validSuspender is a flag so that we can ask for permission before trying to
  // suspend.
  validSuspender.value = true;
  // Record the current stack position. Used in stack_state.mjs
  Module.stackStop = stackSave();
  return promisingRunMainHandler(...args);
}

/**
 * This creates a wrapper around wasm_func that receives an extra suspender
 * argument and returns a promise. The suspender is stored into suspenderGlobal
 * so it can be used by syncify
 */
export function createPromising(wasm_func) {
  if (Module.newJspiSupported) {
    const promisingFunc = WebAssembly.promising(wasm_func);
    async function wrapper(...args) {
      const orig = validSuspender.value;
      validSuspender.value = true;
      try {
        return await promisingFunc(null, ...args);
      } finally {
        validSuspender.value = orig;
      }
    }
    return wrapper;
  }
  const { parameters } = wasmFunctionType(wasm_func);
  parameters.shift();
  return new WebAssembly.Function(
    { parameters, results: ["externref"] },
    wasm_func,
    { promising: "first" },
  );
}

/**
 * This sets up syncify to work.
 *
 * We need to make:
 *
 * - promisingApplyHandler which calls a Python function with stack switching
 *   enabled (used in callPyObjectKwargsSuspending in pyproxy.ts)
 */
export function initSuspenders() {
  promisingApplyHandler = createPromising(wasmExports._pyproxy_apply_promising);
  if (wasmExports.run_main_promising) {
    promisingRunMainHandler = createPromising(wasmExports.run_main_promising);
  }
}

/**
 * Synchronously wait for a JavaScript promise to resolve.
 *
 * This wraps the C function JsvPromise_Syncify which handles all the
 * state saving/restoring and JSPI suspension.
 *
 * IMPORTANT: This can only be called when:
 * 1. JSPI is supported (jspiSupported === true)
 * 2. We're in a valid suspender context (validSuspender.value === true)
 *
 * @param {Promise} promise - The promise to wait for
 * @returns {any} The resolved value of the promise
 * @throws {Error} If called outside a valid suspender context or on error
 */
export function syncify(promise) {
  // _JsvPromise_Syncify is the C function exposed via wasmExports
  // It handles all the state management and calls syncifyHandler
  const result = Module._JsvPromise_Syncify(promise);
  
  // Check for error (Module.error is returned on failure)
  if (result === Module.error) {
    if (Module.syncify_error) {
      const err = Module.syncify_error;
      delete Module.syncify_error;
      throw err;
    }
    throw new Error("syncify failed - not in a valid suspender context");
  }
  
  return result;
}

/**
 * A lightweight version of syncify that only saves/restores WebAssembly stack
 * state, without touching Python thread state.
 *
 * This is designed for use in low-level contexts like syscall implementations
 * (e.g., nodesockfs) where:
 * - The GIL may or may not be held
 * - Python thread state may be in an inconsistent state
 * - We only need to suspend the WebAssembly execution, not switch Python contexts
 *
 * IMPORTANT: This can only be called when:
 * 1. JSPI is supported (jspiSupported === true)
 * 2. We're in a valid suspender context (validSuspender.value === true)
 *
 * @param {Promise} promise - The promise to wait for
 * @returns {any} The resolved value of the promise
 * @throws {Error} If called outside a valid suspender context or on error
 */
export function syncifySimple(promise) {
  // _JsvPromise_SyncifySimple is the C function that only saves/restores
  // WebAssembly stack state (not Python thread state)
  const result = Module._JsvPromise_SyncifySimple(promise);
  
  // Check for error (Module.error is returned on failure)
  if (result === Module.error) {
    if (Module.syncify_error) {
      const err = Module.syncify_error;
      delete Module.syncify_error;
      throw err;
    }
    throw new Error("syncifySimple failed - not in a valid suspender context");
  }
  
  return result;
}
