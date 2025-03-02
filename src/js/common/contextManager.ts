/**
 * Python's ContextManager-like higher-order function.
 * Works with both synchronous and asynchronous callbacks.
 *
 * @param setup A function that will be called to setup the context
 * @param cleanup A function that will be called to cleanup the context
 * @param callback A function that will be called with the context
 * @returns The result of the callback function (or a Promise if callback is async)
 */
export function withContext<T>(
  setup: () => any,
  cleanup: () => void,
  callback: () => T | Promise<T>,
): T | Promise<T> {
  setup();
  try {
    const result = callback();
    if (result instanceof Promise) {
      return result.finally(() => cleanup());
    } else {
      cleanup();
      return result;
    }
  } catch (e) {
    cleanup();
    throw e;
  }
}

/**
 * Creates a function wrapper that sets up a context before calling the function
 * and cleans up afterwards. Works with both synchronous and asynchronous functions.
 *
 * @param setup Function to call before the wrapped function
 * @param cleanup Function to call after the wrapped function
 * @returns A function that wraps another function with the context
 */
export function createContextWrapper(setup: () => any, cleanup: () => void) {
  return <T extends (...args: any[]) => any>(fn: T) => {
    return function (this: any, ...args: Parameters<T>) {
      setup();
      try {
        const result = fn.apply(this, args);
        if (result instanceof Promise) {
          return result.finally(() => cleanup());
        } else {
          cleanup();
          return result;
        }
      } catch (e) {
        cleanup();
        throw e;
      }
    };
  };
}
