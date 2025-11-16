/**
 * @hidden
 */
export interface RuntimeEnv extends BaseRuntimeEnv {
  IN_NODE_COMMONJS: boolean;
  IN_NODE_ESM: boolean;
  IN_BROWSER: boolean;
  IN_BROWSER_MAIN_THREAD: boolean;
  IN_BROWSER_WEB_WORKER: boolean;
}

interface BaseRuntimeEnv {
  IN_NODE: boolean;
  IN_BUN: boolean;
  IN_DENO: boolean;
  IN_SAFARI: boolean;
  IN_SHELL: boolean;
}

/**
 * Runtime override option type.
 * @private
 */
export type RuntimeOption = "browser" | "node" | "deno" | "bun" | "webworker";

declare var read: any;
declare var load: any;
declare var Deno: any;
declare var Bun: any;

function getGlobalRuntimeEnv(): RuntimeEnv {
  if (typeof API !== "undefined" && API !== globalThis.API) {
    // We're in pyodide.asm.js, get runtimeEnv off of API.
    // Hopefully this API !== globalThis.API prevents us from accidentally
    // picking up a global.
    return API.runtimeEnv;
  }
  // We're in pyodide.mjs, do the feature detection.
  const IN_BUN = typeof Bun !== "undefined";
  const IN_DENO = typeof Deno !== "undefined";
  const IN_NODE =
    typeof process === "object" &&
    typeof process.versions === "object" &&
    typeof process.versions.node === "string" &&
    !(process as any).browser;
  const IN_SAFARI =
    typeof navigator === "object" &&
    typeof navigator.userAgent === "string" &&
    navigator.userAgent.indexOf("Chrome") === -1 &&
    navigator.userAgent.indexOf("Safari") > -1;
  const IN_SHELL = typeof read === "function" && typeof load === "function";
  return calculateDerivedFlags(
    {
      IN_BUN,
      IN_DENO,
      IN_NODE,
      IN_SAFARI,
      IN_SHELL,
    },
    undefined, // No override, use automatic detection
  );
}

/** @private Internal runtime environment state */
export const RUNTIME_ENV: RuntimeEnv = getGlobalRuntimeEnv();

/**
 * Create a BaseRuntimeEnv from a runtime override option.
 * @private
 */
function createBaseFromOverride(
  runtimeOverride: RuntimeOption,
): BaseRuntimeEnv {
  return {
    IN_NODE: runtimeOverride === "node",
    IN_BUN: runtimeOverride === "bun",
    IN_DENO: runtimeOverride === "deno",
    IN_SAFARI: false, // Safari detection doesn't make sense with override
    IN_SHELL: false, // Shell detection doesn't make sense with override
  };
}

/**
 * Get runtime environment with optional override.
 * If override is provided, it takes precedence over automatic detection.
 * @param runtimeOverride Optional runtime override
 * @returns Runtime environment configuration
 * @private
 */
export function getRuntimeEnvWithOverride(
  runtimeOverride?: RuntimeOption,
): RuntimeEnv {
  if (!runtimeOverride) {
    // No override, use the pre-computed RUNTIME_ENV for performance
    return RUNTIME_ENV;
  }

  // Override is provided, calculate from override
  const base = createBaseFromOverride(runtimeOverride);
  return calculateDerivedFlags(base, runtimeOverride);
}

function calculateDerivedFlags(
  base: BaseRuntimeEnv,
  runtimeOverride?: RuntimeOption,
): RuntimeEnv {
  const IN_NODE_COMMONJS =
    base.IN_NODE &&
    typeof module !== "undefined" &&
    module.exports &&
    typeof require === "function" &&
    typeof __dirname === "string";

  const IN_NODE_ESM = base.IN_NODE && !IN_NODE_COMMONJS;
  const IN_BROWSER = !base.IN_NODE && !base.IN_DENO && !base.IN_BUN;

  // Handle webworker override explicitly
  let IN_BROWSER_MAIN_THREAD: boolean;
  let IN_BROWSER_WEB_WORKER: boolean;

  if (runtimeOverride === "webworker") {
    // Explicit webworker override
    IN_BROWSER_WEB_WORKER = true;
    IN_BROWSER_MAIN_THREAD = false;
  } else if (runtimeOverride === "browser") {
    // Explicit browser override (main thread)
    IN_BROWSER_WEB_WORKER = false;
    IN_BROWSER_MAIN_THREAD = true;
  } else {
    // Automatic detection (existing logic)
    IN_BROWSER_MAIN_THREAD =
      IN_BROWSER &&
      typeof window !== "undefined" &&
      typeof (window as any).document !== "undefined" &&
      typeof (document as any).createElement === "function" &&
      "sessionStorage" in (window as any) &&
      typeof (globalThis as any).importScripts !== "function";
    IN_BROWSER_WEB_WORKER =
      IN_BROWSER &&
      typeof (globalThis as any).WorkerGlobalScope !== "undefined" &&
      typeof (globalThis as any).self !== "undefined" &&
      (globalThis as any).self instanceof (globalThis as any).WorkerGlobalScope;
  }
  return {
    ...base,
    IN_BROWSER,
    IN_BROWSER_MAIN_THREAD,
    IN_BROWSER_WEB_WORKER,
    IN_NODE_COMMONJS,
    IN_NODE_ESM,
  };
}
