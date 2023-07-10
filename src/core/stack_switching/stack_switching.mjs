/**
 * Files exported from here are copied into the Emscripten namespace.
 * See esbuild.config.mjs.
 */

import {
  createInvoke,
  jsWrapperTag,
  wrapException,
  adjustWasmImports,
} from "./create_invokes.mjs";

export { createInvoke, jsWrapperTag };

if (jsWrapperTag) {
  Module.adjustWasmImports = adjustWasmImports;
  Module.wrapException = wrapException;
}
