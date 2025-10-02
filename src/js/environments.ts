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
  return calculateDerivedFlags({
    IN_BUN,
    IN_DENO,
    IN_NODE,
    IN_SAFARI,
    IN_SHELL,
  });
}

/** @private Internal runtime environment state */
export const RUNTIME_ENV: RuntimeEnv = getGlobalRuntimeEnv();

function calculateDerivedFlags(base: BaseRuntimeEnv): RuntimeEnv {
  const IN_NODE_COMMONJS =
    base.IN_NODE &&
    typeof module !== "undefined" &&
    module.exports &&
    typeof require === "function" &&
    typeof __dirname === "string";

  const IN_NODE_ESM = base.IN_NODE && !IN_NODE_COMMONJS;
  const IN_BROWSER = !base.IN_NODE && !base.IN_DENO && !base.IN_BUN;
  const IN_BROWSER_MAIN_THREAD =
    IN_BROWSER &&
    typeof window !== "undefined" &&
    typeof (window as any).document !== "undefined" &&
    typeof (document as any).createElement === "function" &&
    "sessionStorage" in (window as any) &&
    typeof (globalThis as any).importScripts !== "function";
  const IN_BROWSER_WEB_WORKER =
    IN_BROWSER &&
    typeof (globalThis as any).WorkerGlobalScope !== "undefined" &&
    typeof (globalThis as any).self !== "undefined" &&
    (globalThis as any).self instanceof (globalThis as any).WorkerGlobalScope;
  return {
    ...base,
    IN_BROWSER,
    IN_BROWSER_MAIN_THREAD,
    IN_BROWSER_WEB_WORKER,
    IN_NODE_COMMONJS,
    IN_NODE_ESM,
  };
}
