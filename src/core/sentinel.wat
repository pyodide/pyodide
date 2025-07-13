;; This module is needed for two reasons:
;; 1. Clang/llvm is unable to generate the wasm GC instructions and types we need.
;; 2. wasm-gc has only been supported in Safari since December 2024 and since
;; NodeJS 22 in April 2024.
;;
;; In another year or so, reason 2 will go away. To address reason 1 my pipe dream
;; is to implement the needed primitives into llvm. But that will be a lot of work.
;;
;; Once it works in Safari, we can use wasm-merge to merge this module with the
;; main module which will allow better optimization.
(module
  (type $struct (struct i32))

  (func (export "create_sentinel") (param $tag i32) (result externref)
    local.get $tag
    struct.new $struct
    extern.convert_any
  )

  (func (export "sentinel_get_value") (param $input externref) (result i32)
    (block $b (result (ref null any))
      local.get $input
      any.convert_extern
      br_on_cast_fail $b (ref null any) (ref $struct)
      struct.get_u $struct 0
      return
    )
    drop
    i32.const -1
  )
)
