/**
 * Policy deciding which shared libraries have to be compiled ahead of time.
 *
 * @private
 */

/**
 * Chromium refuses to compile a WebAssembly module larger than 8MiB
 * synchronously on the main thread. Firefox, Safari, node, Deno and Bun have no
 * such limit, and neither does Chromium off the main thread.
 *
 * The bound is deliberately conservative: overestimating a library's size only
 * costs one extra asynchronous compile, while underestimating it makes the
 * import fail outright.
 *
 * See https://github.com/pyodide/pyodide/issues/6390.
 *
 * @private
 */
export const SYNC_WASM_COMPILE_LIMIT = 8 * 1024 * 1024;

/**
 * A shared library found inside a package.
 *
 * @private
 */
export interface DynlibEntry {
  /** The absolute path the library was extracted to. */
  path: string;
  /** The uncompressed size in bytes, or `undefined` if it is not known. */
  size?: number;
}

/**
 * Whether a shared library has to be compiled before the package finishes
 * installing.
 *
 * @param entry The library and its uncompressed size.
 * @param preloadAll Whether every library should be compiled up front.
 * @private
 */
export function shouldPreloadDynlib(
  entry: DynlibEntry,
  preloadAll: boolean,
): boolean {
  if (preloadAll) {
    return true;
  }
  return entry.size === undefined || entry.size >= SYNC_WASM_COMPILE_LIMIT;
}
