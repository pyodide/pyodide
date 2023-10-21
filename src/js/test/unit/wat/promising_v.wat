(module
  (import "e" "s" (global (mut externref)))
  (import "e" "i" (func ))
  (func (param externref)
    local.get 0
    global.set 0
    call 0)
  (export "o" (func 1)))
