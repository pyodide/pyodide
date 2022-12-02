/**
 * @param fn A function to be memoized.
 * @returns
 */
export const memoize = (fn: CallableFunction) => {
  let cache: any = {};
  return (...args: any) => {
    let n = args[0];
    if (n in cache) {
      return cache[n];
    } else {
      let result = fn(n);
      cache[n] = result;
      return result;
    }
  };
};
