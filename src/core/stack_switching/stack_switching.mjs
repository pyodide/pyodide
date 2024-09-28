/**
 * Files exported from here are copied into the Emscripten namespace.
 * See esbuild.config.mjs.
 */

import {
  jsWrapperTag,
  wrapException,
  adjustWasmImports,
  createInvoke,
} from "./create_invokes.mjs";
import { initSuspenders } from "./suspenders.mjs";

export {
  promisingApply,
  createPromising,
  validSuspender,
  suspenderGlobal,
} from "./suspenders.mjs";
export { StackState } from "./stack_state.mjs";
export { jsWrapperTag };

let canConstructWasm = true;
try {
  // Check that WebAssembly.Module constructor works -- if dynamic eval is
  // disabled it might raise.
  // This is the smallest valid wasm module -- only the magic number and wasm
  // version.
  new WebAssembly.Module(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0]));
} catch (e) {
  canConstructWasm = false;
}

// wasm-feature-detect uses `"Suspender" in WebAssembly` feature detect JSPI. It
// is not 100% clear based on the text of the JSPI proposal that this will
// actually work in the future, but if it breaks we can replace it with
// something else that does work.
export const newJspiSupported = canConstructWasm && "Suspending" in WebAssembly;
export const oldJspiSupported = canConstructWasm && "Suspender" in WebAssembly;
export const jspiSupported = newJspiSupported || oldJspiSupported;
Module.newJspiSupported = newJspiSupported;
Module.oldJspiSupported = oldJspiSupported;
Module.jspiSupported = jspiSupported;

if (jspiSupported) {
  Module.preRun.push(initSuspenders);
  Module.adjustWasmImports = adjustWasmImports;
  Module.wrapException = wrapException;
  Module.createInvoke = createInvoke;
}
