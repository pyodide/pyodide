// @ts-nocheck

/**
 * Internal runtime environment interface for type safety
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
 * @private
 */
function getGlobalRuntimeEnv(): RuntimeEnv {
  if (!globalThis.__PYODIDE_RUNTIME_ENV__) {
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
    globalThis.__PYODIDE_RUNTIME_ENV__ = env;
    // Update derived flags using the shared function
    updateDerivedFlags(env);
  }
  return globalThis.__PYODIDE_RUNTIME_ENV__;
}

/**
 * Singleton runtime environment object
 * This serves as the single source of truth for runtime detection
 */
export const RUNTIME_ENV: RuntimeEnv = getGlobalRuntimeEnv();

/**
 * Update derived flags based on current runtime environment
 * This ensures consistency when runtime is overridden
 * @private
 */
function updateDerivedFlags(runtimeEnv: RuntimeEnv) {
  // Calculate IN_NODE_COMMONJS
  if (runtimeEnv.IN_NODE) {
    runtimeEnv.IN_NODE_COMMONJS =
      typeof module !== "undefined" &&
      module.exports &&
      typeof require === "function" &&
      typeof __dirname === "string";
  }

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

  // Reset all flags to false to prevent human error
  Object.keys(runtimeEnv).forEach(
    (key) => (runtimeEnv[key as keyof RuntimeEnv] = false),
  );

  switch (runtime) {
    case "node":
      runtimeEnv.IN_NODE = true;
      // IN_NODE_COMMONJS and IN_NODE_ESM will be derived in updateDerivedFlags()
      break;
    case "browser":
      runtimeEnv.IN_BROWSER = true;
      break;
    case "deno":
      runtimeEnv.IN_DENO = true;
      runtimeEnv.IN_NODE = true; // Deno is Node-compatible
      break;
    case "bun":
      runtimeEnv.IN_BUN = true;
      runtimeEnv.IN_NODE = true; // Bun is Node-compatible
      break;
  }

  // Update derived flags (including IN_NODE_*, IN_BROWSER_*)
  updateDerivedFlags(runtimeEnv);
}

// No individual flag exports; use RUNTIME_ENV directly

/**
 * Detects the current environment and returns a record of boolean flags.
 * The flags indicate what kind of environment pyodide is running in.
 * @deprecated Use RUNTIME_ENV directly instead of this function
 */
export function detectEnvironment(): Record<string, boolean> {
  return getGlobalRuntimeEnv();
}

// Register functions with API if available
if (typeof API !== "undefined") {
  API.detectEnvironment = detectEnvironment;
  API.overrideRuntime = overrideRuntime;
}
