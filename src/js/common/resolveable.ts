export interface ResolvablePromise extends Promise<void> {
      resolve: (value?: any) => void;
      reject: (err?: Error) => void;
}

/**
 * Create a promise that can be resolved or rejected from the outside.
 */
export function createResolvable(): ResolvablePromise {
      let _resolve: (value: any) => void = () => {};
      let _reject: (err: Error) => void = () => {};

      const p: any = new Promise<void>((resolve, reject) => {
            _resolve = resolve;
            _reject = reject;
      });

      p.resolve = _resolve;
      p.reject = _reject;
      return p;
}
