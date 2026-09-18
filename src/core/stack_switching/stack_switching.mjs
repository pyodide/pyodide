/**
 * Files exported from here are copied into the Emscripten namespace.
 * See esbuild.config.mjs.
 */

export {
  promisingApply,
  promisingRunMain,
  createPromising,
  validSuspender,
} from "./suspenders.mjs";
export { StackState, enterTask } from "./stack_state.mjs";

export const jspiSupported = "Suspending" in WebAssembly;
Module.jspiSupported = jspiSupported;
