;; This module is needed for two reasons:
;; 1. Clang/llvm is unable to generate the wasm GC instructions and types we
;;    need.
;; 2. wasm-gc has only been supported in Safari since December 2024 and since
;;    NodeJS 22 in April 2024.
;;
;; In another year or so, reason 2 will go away. To address reason 1 my pipe
;; dream is to implement the needed primitives into llvm. But that will be a lot
;; of work.
;;
;; Once it works in Safari, we can use wasm-merge to merge this module with the
;; main module which will allow better optimization.
;;
;; We define two sentinel values here: the error marker and the "no value"
;; marker. They need to have distinct types so that we can tell them apart with
;; ref.test but aside from that the type is not important.
(module
  (type $error_struct (struct))
  (type $novalue_struct (struct (field i8)))

  (func (export "Jsv_GetError_import") (result externref)
    struct.new_default $error_struct
    extern.convert_any
  )

  (func (export "JsvError_Check") (param $input externref) (result i32)
    local.get $input
    any.convert_extern
    ref.test (ref $error_struct)
  )

  (func (export "Jsv_GetNoValue_import") (result externref)
    struct.new_default $novalue_struct
    extern.convert_any
  )

  (func (export "JsvNoValue_Check") (param $input externref) (result i32)
    local.get $input
    any.convert_extern
    ref.test (ref $novalue_struct)
  )
)
