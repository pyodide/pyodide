/**
 * Files exported from here are copied into the Emscripten namespace.
 * See esbuild.config.mjs.
 */

import {
  jsWrapperTag,
  wrapException,
  adjustWasmImports,
} from "./create_invokes.mjs";
import { initSuspenders } from "./suspenders.mjs";

export { promisingApply, createPromising } from "./suspenders.mjs";

export { jsWrapperTag };

Module.preRun.push(initSuspenders);

if (jsWrapperTag) {
  Module.adjustWasmImports = adjustWasmImports;
  Module.wrapException = wrapException;
}
