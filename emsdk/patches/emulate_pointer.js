diff --git a/emsdk/fastcomp/emscripten/src/library.js b/emsdk/fastcomp/emscripten/src/library.js
index 97cca10..5c002d7 100644
--- a/emsdk/fastcomp/emscripten/src/library.js
+++ b/emsdk/fastcomp/emscripten/src/library.js
@@ -2194,7 +2194,7 @@ LibraryManager.library = {
     // can call (which does not use that ABI), as the function pointer would
     // not be usable from wasm. instead, the wasm has exported function pointers
     // for everything we need, with prefix fp$, use those
-    result = lib.module['fp$' + symbol];
+    result = lib.module['fp$' + mangled];
     if (typeof result === 'object') {
       // a breaking change in the wasm spec, globals are now objects
       // https://github.com/WebAssembly/mutable-global/issues/1
