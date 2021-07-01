export let Module = {};
Module.noImageDecoding = true;
Module.noAudioDecoding = true;
Module.noWasmDecoding = false; // we preload wasm using the built in plugin now
Module.preloadedWasm = {};
