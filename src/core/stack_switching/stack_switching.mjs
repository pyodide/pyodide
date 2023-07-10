/**
 * Files exported from here are copied into the Emscripten namespace.
 * See esbuild.config.mjs.
 */

import {
  jsWrapperTag,
  wrapException,
  adjustWasmImports,
} from "./create_invokes.mjs";

export { jsWrapperTag };

if (jsWrapperTag) {
  Module.adjustWasmImports = adjustWasmImports;
  Module.wrapException = wrapException;
}
