/**
 * This file handles stack switching for the C in-memory stack and for the
 * inaccessible wasm stack.
 */

import {
  createInvoke,
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
