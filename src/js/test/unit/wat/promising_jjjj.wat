(module
  (import "e" "s" (global (mut externref)))
  (import "e" "i" (func (param i64) (param i64) (param i64) (result i64)))
  (func (param externref) (param i64) (param i64) (param i64) (result i64)
    local.get 0
    global.set 0
    local.get 1
    local.get 2
    local.get 3
    call 0)
  (export "o" (func 1)))
