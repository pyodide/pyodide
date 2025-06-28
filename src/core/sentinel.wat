;; This module is needed for two reasons:
;; 1. Clang/llvm is unable to generate the wasm GC instructions and types we need.
;; 2. wasm-gc has only been supported in Safari since December 2024 and since
;; NodeJS 22 in April 2024.
;;
;; In another year or so, reason 2 will go away. To address reason 1 my pipe dream
;; is to implement the needed primitives into llvm. But that will be a lot of work.
(module
  (type $empty_struct (struct))

  (func (export "create_sentinel") (result externref)
    struct.new $empty_struct
    extern.convert_any
  )

  (func (export "is_sentinel") (param $input externref) (result i32)
    local.get $input
    any.convert_extern
    ref.test (ref $empty_struct)
  )
)
