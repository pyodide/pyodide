(module
  (type $empty_struct (struct))
  (import "env" "is_safari" (global $is_safari i32))
  (import "env" "safari_error" (global $safari_error externref))
  (import "env" "safari_is_error" (func $safari_is_error (param externref) (result i32)))

  (func (export "create_sentinel") (result externref)
    (global.get $is_safari)
    (if (then
      (global.get $safari_error)
      (return)
    ))
    struct.new $empty_struct
    extern.convert_any
  )

  (func (export "is_sentinel") (param $input externref) (result i32)
    (global.get $is_safari)
    (if
    (then
      (local.get $input)
      call $safari_is_error
      return
    ))
    (local.get $input)
    any.convert_extern
    ref.test (ref $empty_struct)
  )
)
