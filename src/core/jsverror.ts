// @ts-ignore Can't find jsverror.wasm or it's corresponding type declarations
import jsverrorWasm from "./jsverror.wasm";

declare const jsverrorWasm: Uint8Array;

const jsvErrorInstancePromise: Promise<WebAssembly.Instance | undefined> =
  (async function () {
    // Starting with iOS 18.3.1, WebKit on iOS has an issue with the garbage
    // collector that breaks the call trampoline. See #130418 and
    // https://bugs.webkit.org/show_bug.cgi?id=293113 for details.
    let isIOS =
      globalThis.navigator &&
      (/iPad|iPhone|iPod/.test(navigator.userAgent) ||
        // Starting with iPadOS 13, iPads might send a platform string that looks like a desktop Mac.
        // To differentiate, we check if the platform is 'MacIntel' (common for Macs and newer iPads)
        // AND if the device has multi-touch capabilities (navigator.maxTouchPoints > 1)
        (navigator.platform === "MacIntel" &&
          typeof navigator.maxTouchPoints !== "undefined" &&
          navigator.maxTouchPoints > 1));
    if (isIOS) {
      return undefined;
    }
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
