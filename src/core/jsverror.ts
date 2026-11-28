// @ts-ignore Can't find jsverror.wasm or it's corresponding type declarations
import jsverrorWasm from "./jsverror.wasm";

declare const jsverrorWasm: BufferSource;

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

type JsvErrorInstance<E, N> = {
  Jsv_GetError_import: () => E;
  JsvError_Check: (val: any) => val is E;
  Jsv_GetNoValue_import: () => N;
  JsvNoValue_Check: (val: any) => val is N;
};

/**
 * Returns the sentinel-related functions that are imported into the main
 * wasm module. When wasm-gc is available, these are the exports of
 * jsverror.wasm and the sentinels are opaque wasm-gc structs. Otherwise (e.g.
 * on iOS) we fall back to JavaScript Symbols and identity comparisons.
 * @private
 */
export async function getJsvErrorImport(): Promise<
  JsvErrorInstance<Symbol, Symbol>
> {
  const jsvErrorInstance = await jsvErrorInstancePromise;
  if (jsvErrorInstance) {
    return jsvErrorInstance.exports as JsvErrorInstance<Symbol, Symbol>;
  }
  const error_marker = Symbol("error marker");
  const novalue_marker = Symbol("novalue marker");
  return {
    Jsv_GetError_import: () => error_marker,
    JsvError_Check: (val: any): val is typeof error_marker =>
      val === error_marker,
    Jsv_GetNoValue_import: () => novalue_marker,
    JsvNoValue_Check: (val: any): val is typeof novalue_marker =>
      val === novalue_marker,
  };
}
