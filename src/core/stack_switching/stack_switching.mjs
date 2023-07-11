/**
 * Files exported from here are copied into the Emscripten namespace.
 * See esbuild.config.mjs.
 */

import {
  jsWrapperTag,
  wrapException,
  adjustWasmImports,
} from "./create_invokes.mjs";
export {
  initSuspenders,
  promisingApply,
  createPromising,
} from "./suspenders.mjs";

export { jsWrapperTag };

if (jsWrapperTag) {
  Module.adjustWasmImports = adjustWasmImports;
  Module.wrapException = wrapException;
}
