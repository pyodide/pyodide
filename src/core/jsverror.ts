// @ts-ignore Can't find jsverror.wasm or it's corresponding type declarations
import jsverrorWasm from "./jsverror.wasm";

declare const jsverrorWasm: Uint8Array;

const jsvErrorInstancePromise: Promise<WebAssembly.Instance | undefined> =
  (async function () {
    try {
      const module = await WebAssembly.compile(jsverrorWasm);
      return await WebAssembly.instantiate(module);
    } catch (e) {
      if (e instanceof WebAssembly.CompileError) {
        return undefined;
      }
      throw e;
    }
  })();

type JsvErrorInstance<T> = {
  Jsv_GetError_import: () => T;
  JsvError_Check: (val: any) => val is T;
};

/**
 * @private
 */
export async function getJsvErrorImport(): Promise<JsvErrorInstance<Symbol>> {
  const jsvErrorInstance = await jsvErrorInstancePromise;
  if (jsvErrorInstance) {
    return jsvErrorInstance.exports as JsvErrorInstance<Symbol>;
  }
  const error_marker = Symbol("error marker");
  return {
    Jsv_GetError_import: () => error_marker,
    JsvError_Check: (val: any): val is typeof error_marker =>
      val === error_marker,
  };
}
