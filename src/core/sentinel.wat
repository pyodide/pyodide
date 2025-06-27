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
