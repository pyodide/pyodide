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
    const env: RuntimeEnv = {
      IN_NODE:
        typeof process === "object" &&
        typeof process.versions === "object" &&
        typeof process.versions.node === "string" &&
        !(process as any).browser,

      IN_NODE_COMMONJS: false,  // Derived from IN_NODE
      IN_NODE_ESM: false,      // Derived from IN_NODE

      IN_BUN: typeof (globalThis as any).Bun !== "undefined",
      IN_DENO: typeof (globalThis as any).Deno !== "undefined",
      IN_BROWSER: true,        // Default true, will be updated in derived flags
      IN_BROWSER_MAIN_THREAD: false,  // Derived from IN_BROWSER
      IN_BROWSER_WEB_WORKER: false,   // Derived from IN_BROWSER,

      IN_SAFARI:
        typeof navigator === "object" &&
        typeof (navigator as any).userAgent === "string" &&
        (navigator as any).userAgent.indexOf("Chrome") == -1 &&
        (navigator as any).userAgent.indexOf("Safari") > -1,

      IN_SHELL:
        typeof (globalThis as any).read == "function" &&
        typeof (globalThis as any).load === "function",
    };
    // compute derived
    env.IN_NODE_ESM = env.IN_NODE && !env.IN_NODE_COMMONJS;
    env.IN_BROWSER = !env.IN_NODE && !env.IN_DENO && !env.IN_BUN;
    env.IN_BROWSER_MAIN_THREAD =
      env.IN_BROWSER &&
      typeof window !== "undefined" &&
      typeof (window as any).document !== "undefined" &&
      typeof (document as any).createElement === "function" &&
      "sessionStorage" in (window as any) &&
      typeof (globalThis as any).importScripts !== "function";
    env.IN_BROWSER_WEB_WORKER =
      env.IN_BROWSER &&
      typeof (globalThis as any).WorkerGlobalScope !== "undefined" &&
      typeof (globalThis as any).self !== "undefined" &&
      (globalThis as any).self instanceof (globalThis as any).WorkerGlobalScope;

    globalThis.__PYODIDE_RUNTIME_ENV__ = env;
  }
  return globalThis.__PYODIDE_RUNTIME_ENV__;
}

/**
 * Singleton runtime environment object
 * This serves as the single source of truth for runtime detection
 * @private
 */
export const RUNTIME_ENV: RuntimeEnv = getGlobalRuntimeEnv();

// Derived flags are computed during initialization in getGlobalRuntimeEnv

/**
 * Update derived flags based on current runtime environment
 * This ensures consistency when runtime is overridden
 * @private
 */
function updateDerivedFlags() {
  const runtimeEnv = getGlobalRuntimeEnv();

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

/**
 * Override runtime environment flags
 * This allows forcing specific runtime detection for testing purposes
 * @param runtime - The runtime to force ('browser', 'node', 'deno', 'bun')
 * @private
 */
export function overrideRuntime(runtime: "browser" | "node" | "deno" | "bun") {
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

  switch (runtime) {
    case "node":
      runtimeEnv.IN_NODE = true;
      break;
    case "browser":
      runtimeEnv.IN_BROWSER = true;
      break;
    case "deno":
      runtimeEnv.IN_NODE = true;
      runtimeEnv.IN_DENO = true;
      break;
    case "bun":
      runtimeEnv.IN_NODE = true;
      runtimeEnv.IN_BUN = true;
      break;
  }

  // Update derived flags (including IN_NODE_*, IN_BROWSER_*)
  updateDerivedFlags();
}

// No individual flag exports; use RUNTIME_ENV directly

/**
 * Detects the current environment and returns a record with the results.
 * This function is useful for debugging and testing purposes.
 * @private
 */
export function detectEnvironment(): RuntimeEnv {
  return getGlobalRuntimeEnv();
}
