/** @private */

const WASM_PAGE_SIZE = 65536;
const MAX_PAGES = 65535; // 4 GiB - 1 page, the most Emscripten allows

/**
 * The ``INITIAL_MEMORY`` that the Pyodide build links with, see Makefile.envs.
 *
 * @private
 */
export const DEFAULT_INITIAL_MEMORY = 31457280;

/**
 * Create the WebAssembly heap with ``maxMemoryBytes`` as its maximum size, so
 * that the engine itself refuses to grow it any further.
 *
 * @private
 */
export function createLimitedMemory(
  initialBytes: number,
  maxMemoryBytes: number,
): WebAssembly.Memory {
  if (!(maxMemoryBytes >= initialBytes)) {
    throw new RangeError(
      `maxMemoryBytes must be at least ${initialBytes}, the initial size of the heap, got ${String(maxMemoryBytes)}`,
    );
  }
  return new WebAssembly.Memory({
    initial: Math.ceil(initialBytes / WASM_PAGE_SIZE),
    maximum: Math.min(Math.floor(maxMemoryBytes / WASM_PAGE_SIZE), MAX_PAGES),
  });
}
