// @ts-ignore
import sentinelWasm from "./sentinel.wasm";

declare const sentinelWasm: Uint8Array;

const sentinelInstancePromise: Promise<WebAssembly.Instance | undefined> =
  (async function () {
    const isIOS =
      globalThis.navigator && /iPad|iPhone|iPod/.test(navigator.platform);
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

export async function getSentinelImport() {
  await sentinelInstancePromise;
  const sentinelInstance = await sentinelInstancePromise;
  if (sentinelInstance) {
    return sentinelInstance.exports;
  }
  const error_marker = Symbol("error marker");
  return {
    create_sentinel: () => error_marker,
    is_sentinel: (val: any) => val === error_marker,
  };
}
