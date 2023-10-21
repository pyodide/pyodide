(module
  (import "e" "s" (global (mut externref)))
  (import "e" "i" (func (param f64) (result f64)))
  (func (param externref) (param f64) (result f64)
    local.get 0
    global.set 0
    local.get 1
    call 0)
  (export "o" (func 1)))
