export let Module = {};
Module.noImageDecoding = true;
Module.noAudioDecoding = true;
Module.noWasmDecoding = false; // we preload wasm using the built in plugin now
Module.preloadedWasm = {};

export let HEAPU32 = undefined;
export let HEAP32 = undefined;
