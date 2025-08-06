// @ts-nocheck

/** @private */
export const IN_NODE =
	typeof process === "object" &&
	typeof process.versions === "object" &&
	typeof process.versions.node === "string" &&
	!process.browser; /* This last condition checks if we run the browser shim of process */

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
export const IN_BUN = typeof globalThis.Bun !== "undefined";

/** @private */
export const IN_DENO = typeof Deno !== "undefined"; // just in case...

/** @private */
export const IN_BROWSER = !IN_NODE && !IN_DENO;

/** @private */
export const IN_BROWSER_MAIN_THREAD =
	IN_BROWSER &&
	typeof window === "object" &&
	typeof document === "object" &&
	typeof document.createElement === "function" &&
	"sessionStorage" in window &&
	typeof importScripts !== "function";

/** @private */
export const IN_BROWSER_WEB_WORKER =
	IN_BROWSER && typeof importScripts === "function" && typeof self === "object";

/** @private */
export const IN_SAFARI =
	typeof navigator === "object" &&
	typeof navigator.userAgent === "string" &&
	navigator.userAgent.indexOf("Chrome") == -1 &&
	navigator.userAgent.indexOf("Safari") > -1;

/** @private */
export const IN_SHELL = typeof read == "function" && typeof load === "function";

/**
 * Detects the current environment and returns a record with the results.
 * This function is useful for debugging and testing purposes.
 * @private
 */
export function detectEnvironment(): Record<string, boolean> {
	return {
		IN_NODE,
		IN_NODE_COMMONJS,
		IN_NODE_ESM,
		IN_BUN,
		IN_DENO,
		IN_BROWSER,
		IN_BROWSER_MAIN_THREAD,
		IN_BROWSER_WEB_WORKER,
		IN_SAFARI,
		IN_SHELL,
	};
}
