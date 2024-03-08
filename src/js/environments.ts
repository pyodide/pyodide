// @ts-nocheck

/** @private */
export const IN_NODE =
  typeof process === "object" &&
  typeof process.versions === "object" &&
  typeof process.versions.node === "string" &&
  typeof process.browser ===
    "undefined"; /* This last condition checks if we run the browser shim of process */

/** @private */
export const IN_NODE_COMMONJS =
  IN_NODE &&
  typeof module !== "undefined" &&
  typeof module.exports !== "undefined" &&
  typeof require !== "undefined" &&
  typeof __dirname !== "undefined";

/** @private */
export const IN_NODE_ESM = IN_NODE && !IN_NODE_COMMONJS;

/** @private */
export const IN_DENO = typeof Deno !== "undefined"; // just in case...

/** @private */
export const IN_BROWSER = !IN_NODE && !IN_DENO;

/** @private */
export const IN_BROWSER_MAIN_THREAD =
  IN_BROWSER &&
  typeof window !== "undefined" &&
  typeof document !== "undefined" &&
  typeof document.createElement !== "undefined" &&
  typeof sessionStorage !== "undefined" &&
  typeof importScripts === "undefined";

/** @private */
export const IN_BROWSER_WEB_WORKER =
  IN_BROWSER &&
  typeof importScripts !== "undefined" &&
  typeof self !== "undefined";

/** @private */
export const IN_SAFARI =
  typeof navigator !== "undefined" &&
  typeof navigator.userAgent !== "undefined" &&
  navigator.userAgent.indexOf("Chrome") == -1 &&
  navigator.userAgent.indexOf("Safari") > -1;

/**
 * Detects the current environment and returns a record with the results.
 * This function is useful for debugging and testing purposes.
 */
export function detectEnvironment(): Record<string, boolean> {
  return {
    IN_NODE: IN_NODE,
    IN_NODE_COMMONJS: IN_NODE_COMMONJS,
    IN_NODE_ESM: IN_NODE_ESM,
    IN_DENO: IN_DENO,
    IN_BROWSER: IN_BROWSER,
    IN_BROWSER_MAIN_THREAD: IN_BROWSER_MAIN_THREAD,
    IN_BROWSER_WEB_WORKER: IN_BROWSER_WEB_WORKER,
    IN_SAFARI: IN_SAFARI,
  };
}
