/**
 * Python's ContextManager-like higher-order function.
 * Works with both synchronous and asynchronous callbacks.
 *
 * @param setup A function that will be called to setup the context
 * @param cleanup A function that will be called to cleanup the context
 * @param callback A function that will be called with the context
 * @returns The result of the callback function (or a Promise if callback is async)
 */
export function withContext<T>(setup: () => void, cleanup: () => void, callback: () => T): T {
      setup();
      let result: T;
      try {
            result = callback();
      } catch (e) {
            cleanup();
            throw e;
      }
      if (result instanceof Promise) {
            return result.finally(() => cleanup()) as T;
      }

      cleanup();
      return result;
}

// A type for a function that wraps another function and preserves its type
type FunctionWrapper = <T extends (...args: any[]) => any>(fn: T) => (...args: Parameters<T>) => ReturnType<T>;

/**
 * Creates a function wrapper that sets up a context before calling the function
 * and cleans up afterwards. Works with both synchronous and asynchronous functions.
 *
 * @param setup Function to call before the wrapped function
 * @param cleanup Function to call after the wrapped function
 * @returns A function that wraps another function with the context
 */
export function createContextWrapper(setup: () => void, cleanup: () => void): FunctionWrapper {
      return function (fn) {
            return function (this: any, ...args: Parameters<typeof fn>) {
                  return withContext(setup, cleanup, () => fn.apply(this, args));
            };
      };
}
