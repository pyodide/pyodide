// @ts-nocheck

/**
 * Internal runtime environment interface for type safety
 * @hidden
 */
export interface RuntimeEnv {
  IN_NODE: boolean;
  IN_NODE_COMMONJS: boolean;
  IN_NODE_ESM: boolean;
  IN_BUN: boolean;
  IN_DENO: boolean;
  IN_BROWSER: boolean;
  IN_BROWSER_MAIN_THREAD: boolean;
  IN_BROWSER_WEB_WORKER: boolean;
  IN_SAFARI: boolean;
  IN_SHELL: boolean;
}

/**
 * Internal runtime environment state
 */
function getGlobalRuntimeEnv(): RuntimeEnv {
  if (typeof API !== "undefined" && API !== globalThis.API) {
    // We're in pyodide.asm.js, get runtimeEnv off of API.
    // Hopefully this API !== globalThis.API prevents us from accidentally
    // picking up a global.
    return API.runtimeEnv;
  }
  // We're in pyodide.mjs, do the feature detection.
  // Derived flags are computed during initialization
  const env: RuntimeEnv = {
    IN_NODE:
      typeof process === "object" &&
      typeof process.versions === "object" &&
      typeof process.versions.node === "string" &&
      !(process as any).browser,

    IN_NODE_COMMONJS: false, // Derived from IN_NODE
    IN_NODE_ESM: false, // Derived from IN_NODE

    IN_BUN: typeof (globalThis as any).Bun !== "undefined",
    IN_DENO: typeof (globalThis as any).Deno !== "undefined",
    IN_BROWSER: true, // Default true, will be updated in derived flags
    IN_BROWSER_MAIN_THREAD: false, // Derived from IN_BROWSER
    IN_BROWSER_WEB_WORKER: false, // Derived from IN_BROWSER,

    IN_SAFARI:
      typeof navigator === "object" &&
      typeof (navigator as any).userAgent === "string" &&
      (navigator as any).userAgent.indexOf("Chrome") == -1 &&
      (navigator as any).userAgent.indexOf("Safari") > -1,

    IN_SHELL:
      typeof (globalThis as any).read == "function" &&
      typeof (globalThis as any).load === "function",
  };
  // Update derived flags using the shared function
  updateDerivedFlags(env);
  return env;
}

/** @private Internal runtime environment state */
export const RUNTIME_ENV: RuntimeEnv = getGlobalRuntimeEnv();

/**
 * Update derived flags based on current runtime environment
 * @private
 */
function updateDerivedFlags(runtimeEnv: RuntimeEnv) {
  // Calculate IN_NODE_COMMONJS
  runtimeEnv.IN_NODE_COMMONJS =
    runtimeEnv.IN_NODE &&
    typeof module !== "undefined" &&
    module.exports &&
    typeof require === "function" &&
    typeof __dirname === "string";

  // Update derived flags
  runtimeEnv.IN_NODE_ESM = runtimeEnv.IN_NODE && !runtimeEnv.IN_NODE_COMMONJS;
  runtimeEnv.IN_BROWSER =
    !runtimeEnv.IN_NODE && !runtimeEnv.IN_DENO && !runtimeEnv.IN_BUN;
  runtimeEnv.IN_BROWSER_MAIN_THREAD =
    runtimeEnv.IN_BROWSER &&
    typeof window !== "undefined" &&
    typeof (window as any).document !== "undefined" &&
    typeof (document as any).createElement === "function" &&
    "sessionStorage" in (window as any) &&
    typeof (globalThis as any).importScripts !== "function";
  runtimeEnv.IN_BROWSER_WEB_WORKER =
    runtimeEnv.IN_BROWSER &&
    typeof (globalThis as any).WorkerGlobalScope !== "undefined" &&
    typeof (globalThis as any).self !== "undefined" &&
    (globalThis as any).self instanceof (globalThis as any).WorkerGlobalScope;
}
