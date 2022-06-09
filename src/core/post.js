// Emscripten doesn't make UTF8ToString or wasmTable available on Module by default...
Module.UTF8ToString = UTF8ToString;
Module.wasmTable = wasmTable;
// Emscripten has a bug where it accidentally exposes an empty object as Module.ERRNO_CODES
Module.ERRNO_CODES = ERRNO_CODES;
// preloadedWasm isn't exposed on Module by default anymore. TODO: We should use
// a less hacky approach via the fs argument to loadDynamicLibrary
Module.preloadedWasm = preloadedWasm;
