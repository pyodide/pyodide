(module
    (global $suspender (import "e" "s") (mut externref))
    ;; Status flag to tell us if suspender is usable
    (global $check (import "e" "c") (mut i32))
    ;; Wrapped syncify function. Expects suspender as a first argument and a
    ;; JsRef to promise as second argument. Returns a JsRef to the result.
    (import "e" "i" (func $syncify_promise_import (param externref i32) (result i32)))
    (import "e" "save" (func $save_state (result externref)))
    (import "e" "restore" (func $restore_state (param externref)))
    ;; Wrapped syncify_promise that handles suspender stuff automatically so
    ;; callee doesn't need to worry about it.
    (func $syncify_promise_export (export "o")
      (param $idpromise i32) (result i32)
      (local $state externref)
      (global.get $check)
      (i32.eqz)
      if
        ;; If no valid suspender, return 0. Callee needs to check for this case
        ;; and set Python error flag (or otherwise handle it).
        i32.const 0
        return
      end
      (call $save_state)
      (local.set $state)
      (global.get $suspender)
      (local.get $idpromise)
      (call $syncify_promise_import) ;; onwards call args are (suspender, orig argument)
      ;; restore $suspender and $check variable
      (local.get $state)
      (call $restore_state)
    )
)
