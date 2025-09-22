// @ts-ignore Can't find sentinel.wasm or it's corresponding type declarations
import sentinelWasm from "./sentinel.wasm";

declare const sentinelWasm: Uint8Array;

const sentinelInstancePromise: Promise<WebAssembly.Instance | undefined> =
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
      const module = await WebAssembly.compile(sentinelWasm);
      return await WebAssembly.instantiate(module);
    } catch (e) {
      if (e instanceof WebAssembly.CompileError) {
        return undefined;
      }
      throw e;
    }
  })();

type SentinelInstance<T> = {
  create_sentinel: () => T;
  is_sentinel: (val: any) => val is T;
};

/**
 * @private
 */
export async function getSentinelImport(): Promise<SentinelInstance<Symbol>> {
  const sentinelInstance = await sentinelInstancePromise;
  if (sentinelInstance) {
    return sentinelInstance.exports as SentinelInstance<Symbol>;
  }
  const error_marker = Symbol("error marker");
  return {
    create_sentinel: () => error_marker,
    is_sentinel: (val: any): val is typeof error_marker => val === error_marker,
  };
}
