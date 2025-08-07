/** @private */
export function makeWarnOnce(warning: string) {
      let warned = false;
      return function () {
            if (!warned) {
                  warned = true;
                  console.warn(warning);
            }
      };
}

/** @private */
export function warnOnce(warning: string): MethodDecorator {
      let warned = false;
      return function (
            _target: any,
            _key: string | symbol,
            descriptor: TypedPropertyDescriptor<any>,
      ): TypedPropertyDescriptor<any> {
            const key = descriptor.value ? "value" : "get";
            const original = descriptor[key];
            descriptor[key] = function (...args: any) {
                  if (!warned) {
                        warned = true;
                        console.warn(warning);
                  }
                  return original.call(this, ...args);
            };
            return descriptor;
      };
}
