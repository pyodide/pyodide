// @ts-nocheck

export const IN_NODE =
  typeof process === "object" &&
  typeof process.versions === "object" &&
  typeof process.versions.node === "string" &&
  typeof process.browser ===
    "undefined"; /* This last condition checks if we run the browser shim of process */

export const IN_NODE_COMMONJS =
  IN_NODE &&
  typeof module !== "undefined" &&
  typeof module.exports !== "undefined" &&
  typeof require !== "undefined" &&
  typeof __dirname !== "undefined";

export const IN_NODE_ESM = IN_NODE && !IN_NODE_COMMONJS;

export const IN_DENO = typeof Deno !== "undefined"; // just in case...

export const IN_BROWSER = !IN_NODE && !IN_DENO;

export const IN_BROWSER_MAIN_THREAD =
  IN_BROWSER &&
  typeof window !== "undefined" &&
  typeof document !== "undefined" &&
  typeof document.createElement !== "undefined" &&
  typeof sessionStorage !== "undefined";

export const IN_BROWSER_WEB_WORKER =
  IN_BROWSER &&
  typeof importScripts !== "undefined" &&
  typeof self !== "undefined";
