export let validSuspender = { value: false };

let promisingApplyHandler;
export function promisingApply(...args) {
  promisingApplyHandler ??= createPromising(
    wasmExports._pyproxy_apply_promising,
  );
  return promisingApplyHandler(...args);
}

let promisingRunMainHandler;
export function promisingRunMain(...args) {
  promisingRunMainHandler ??= createPromising(wasmExports.run_main_promising);
  return promisingRunMainHandler(...args);
}

export function createPromising(wasm_func) {
  const promisingFunc = WebAssembly.promising(wasm_func);
  async function wrapper(...args) {
    const orig = validSuspender.value;
    validSuspender.value = true;
    // Record the current stack position. Used by stack_state.mjs
    Module.stackStop = stackSave();
    try {
      return await promisingFunc(...args);
    } finally {
      validSuspender.value = orig;
    }
  }
  return wrapper;
}
