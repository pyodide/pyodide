;; TODO: figure out how to write this in C
;; Either requires fixes for the following:
;; https://github.com/emscripten-core/emscripten/issues/20512
;; Or changing our dynamic wasm generation a bit
(module
    (global $suspender (import "e" "s") (mut externref))
    ;; Status flag to tell us if suspender is usable
    (global $check (import "e" "c") (mut i32))
    ;; Wrapped syncify function. Expects suspender as a first argument and a
    ;; JsRef to promise as second argument. Returns a JsRef to the result.
    (import "e" "i" (func $syncify_promise_import (param externref externref) (result externref)))
    ;; Wrapped syncify_promise that handles suspender stuff automatically so
    ;; callee doesn't need to worry about it.
    (func $syncify_promise_export (export "o")
      (param $promise externref) (result externref)
      (global.get $check)
      (i32.eqz)
      if
        ;; We tried to syncify with no valid suspender, return 0.
        ;; JsProxy.c checks for this case and sets Python error flag appropriately.
        ref.null extern
        return
      end
      (global.get $suspender)
      (local.get $promise)
      (call $syncify_promise_import) ;; onwards call args are (suspender, orig argument)
    )
)
