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

export { promisingApply, createPromising } from "./suspenders.mjs";

export { jsWrapperTag };

Module.jspiSupported = false;
Module.validSuspender = { value: 0 };

// wasm-feature-detect uses `"Suspender" in WebAssembly` feature detect JSPI. It
// is not 100% clear based on the text of the JSPI proposal that this will
// actually work in the future, but if it breaks we can replace it with
// something else that does work.
if ("Suspender" in WebAssembly) {
  try {
    // Check that WebAssembly.Module constructor works -- if dynamic eval is
    // disabled it might raise.
    // This is the smallest valid wasm module -- only the magic number and wasm
    // version.
    new WebAssembly.Module(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0]));
    Module.jspiSupported = true;
  } catch (e) {}
}

if (Module.jspiSupported) {
  Module.preRun.push(initSuspenders);
  Module.adjustWasmImports = adjustWasmImports;
  Module.wrapException = wrapException;
  Module.createInvoke = createInvoke;
}
