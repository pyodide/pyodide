// @ts-nocheck

/**
 * Runtime environment interface
 * @private
 */
interface RuntimeEnv {
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
 * Get or create the global runtime environment object
 * This ensures consistency across pyodide.mjs and pyodide.asm.wasm bundles
 * @private
 */
function getGlobalRuntimeEnv(): RuntimeEnv {
  if (!globalThis.__PYODIDE_RUNTIME_ENV__) {
    globalThis.__PYODIDE_RUNTIME_ENV__ = {
      IN_NODE:
        typeof process === "object" &&
        typeof process.versions === "object" &&
        typeof process.versions.node === "string" &&
        !process.browser /* This last condition checks if we run the browser shim of process */,

      IN_NODE_COMMONJS:
        typeof process === "object" &&
        typeof process.versions === "object" &&
        typeof process.versions.node === "string" &&
        !process.browser &&
        typeof module !== "undefined" &&
        typeof module.exports !== "undefined" &&
        typeof require !== "undefined" &&
        typeof __dirname !== "undefined",

      IN_NODE_ESM: false, // Will be computed based on IN_NODE and IN_NODE_COMMONJS

      IN_BUN: typeof globalThis.Bun !== "undefined",

      IN_DENO: typeof Deno !== "undefined", // just in case...

      IN_BROWSER: true, // Will be computed based on other flags

      IN_BROWSER_MAIN_THREAD: false, // Will be computed

      IN_BROWSER_WEB_WORKER: false, // Will be computed

      IN_SAFARI:
        typeof navigator === "object" &&
        typeof navigator.userAgent === "string" &&
        navigator.userAgent.indexOf("Chrome") == -1 &&
        navigator.userAgent.indexOf("Safari") > -1,

      IN_SHELL: typeof read == "function" && typeof load === "function",
    };
  }
  return globalThis.__PYODIDE_RUNTIME_ENV__;
}

/**
 * Singleton runtime environment object
 * This serves as the single source of truth for runtime detection
 * @private
 */
export const RUNTIME_ENV: RuntimeEnv = getGlobalRuntimeEnv();

// Compute derived flags
function updateDerivedFlags() {
  RUNTIME_ENV.IN_NODE_ESM =
    RUNTIME_ENV.IN_NODE && !RUNTIME_ENV.IN_NODE_COMMONJS;
  RUNTIME_ENV.IN_BROWSER =
    !RUNTIME_ENV.IN_NODE && !RUNTIME_ENV.IN_DENO && !RUNTIME_ENV.IN_BUN;
  RUNTIME_ENV.IN_BROWSER_MAIN_THREAD =
    RUNTIME_ENV.IN_BROWSER &&
    typeof window === "object" &&
    typeof document === "object" &&
    typeof document.createElement === "function" &&
    "sessionStorage" in window &&
    typeof importScripts !== "function";
  RUNTIME_ENV.IN_BROWSER_WEB_WORKER =
    RUNTIME_ENV.IN_BROWSER &&
    typeof importScripts === "function" &&
    typeof self === "object";
}

// Initialize derived flags
updateDerivedFlags();

/**
 * Override runtime environment flags
 * This allows forcing specific runtime detection for testing purposes
 * @param runtime - The runtime to force ('browser', 'node', 'deno', 'bun')
 * @private
 */
export function setRuntimeOverride(
  runtime: "browser" | "node" | "deno" | "bun",
) {
  // Get the global runtime environment object
  const runtimeEnv = getGlobalRuntimeEnv();

  // Reset all flags to false
  runtimeEnv.IN_NODE = false;
  runtimeEnv.IN_NODE_COMMONJS = false;
  runtimeEnv.IN_NODE_ESM = false;
  runtimeEnv.IN_BUN = false;
  runtimeEnv.IN_DENO = false;
  runtimeEnv.IN_BROWSER = false;
  runtimeEnv.IN_BROWSER_MAIN_THREAD = false;
  runtimeEnv.IN_BROWSER_WEB_WORKER = false;

  // Set the requested runtime
  switch (runtime) {
    case "node":
      runtimeEnv.IN_NODE = true;
      // Default to CommonJS mode, but can be overridden later
      runtimeEnv.IN_NODE_COMMONJS = true;
      runtimeEnv.IN_NODE_ESM = false;
      break;
    case "browser":
      runtimeEnv.IN_BROWSER = true;
      // Default to main thread, but can be overridden later
      runtimeEnv.IN_BROWSER_MAIN_THREAD = true;
      runtimeEnv.IN_BROWSER_WEB_WORKER = false;
      break;
    case "deno":
      runtimeEnv.IN_DENO = true;
      break;
    case "bun":
      runtimeEnv.IN_BUN = true;
      break;
  }
}

// Export individual flags for backward compatibility
/** @private */
export const IN_NODE = RUNTIME_ENV.IN_NODE;
/** @private */
export const IN_NODE_COMMONJS = RUNTIME_ENV.IN_NODE_COMMONJS;
/** @private */
export const IN_NODE_ESM = RUNTIME_ENV.IN_NODE_ESM;
/** @private */
export const IN_BUN = RUNTIME_ENV.IN_BUN;
/** @private */
export const IN_DENO = RUNTIME_ENV.IN_DENO;
/** @private */
export const IN_BROWSER = RUNTIME_ENV.IN_BROWSER;
/** @private */
export const IN_BROWSER_MAIN_THREAD = RUNTIME_ENV.IN_BROWSER_MAIN_THREAD;
/** @private */
export const IN_BROWSER_WEB_WORKER = RUNTIME_ENV.IN_BROWSER_WEB_WORKER;
/** @private */
export const IN_SAFARI = RUNTIME_ENV.IN_SAFARI;
/** @private */
export const IN_SHELL = RUNTIME_ENV.IN_SHELL;

/**
 * Detects the current environment and returns a record with the results.
 * This function is useful for debugging and testing purposes.
 * @private
 */
export function detectEnvironment(): Record<string, boolean> {
  const runtimeEnv = getGlobalRuntimeEnv();
  return {
    IN_NODE: runtimeEnv.IN_NODE,
    IN_NODE_COMMONJS: runtimeEnv.IN_NODE_COMMONJS,
    IN_NODE_ESM: runtimeEnv.IN_NODE_ESM,
    IN_BUN: runtimeEnv.IN_BUN,
    IN_DENO: runtimeEnv.IN_DENO,
    IN_BROWSER: runtimeEnv.IN_BROWSER,
    IN_BROWSER_MAIN_THREAD: runtimeEnv.IN_BROWSER_MAIN_THREAD,
    IN_BROWSER_WEB_WORKER: runtimeEnv.IN_BROWSER_WEB_WORKER,
    IN_SAFARI: runtimeEnv.IN_SAFARI,
    IN_SHELL: runtimeEnv.IN_SHELL,
  };
}
