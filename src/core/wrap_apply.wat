(module
    (global $suspender (import "e" "s") (mut externref))
    (import "e" "i" (func $apply_import (param i32 i32 i32 i32 i32) (result i32)))
    (func $apply_export (export "o")
      (param $susp externref) (param $a i32) (param $b i32) (param $c i32) (param $d i32) (param $e i32) (result i32)
      ;; Store first variable into suspender global
      (local.get $susp)
      (global.set $suspender)
      ;; Plug remaining args into onwards call
      (local.get $a)
      (local.get $b)
      (local.get $c)
      (local.get $d)
      (local.get $e)
      (call $apply_import)
    )
)
