(module
    (type $a (func (param i64) (param i64) (param i64) (result i64)))
    (type $x (func (param i32) (param i64) (param i64) (param i64) (result i64)))
    (type $ttag (func (param externref)))
    (type $tsave (func (result i32)))
    (type $trestore (func (param i32)))
    (type $tset_threw (func (param i32 i32)))

    (import "e" "t" (table 0 funcref))
    (import "e" "tag" (tag $tag (type $ttag)))
    (import "e" "s" (func $stack_save (type $tsave)))
    (import "e" "r" (func $stack_restore (type $trestore)))
    (import "e" "q" (func $set_threw (type $tset_threw)))

    (func (export "o") (param $fptr i32) (param $p1 i64) (param $p2 i64) (param $p3 i64) (result i64)
        (local $stack i32)
        call $stack_save
        local.set $stack
        try (result i64)
            local.get $p1
            local.get $p2
            local.get $p3
            local.get $fptr
            call_indirect (type $a)
        catch $tag
            drop
            local.get $stack
            call $stack_restore
            (call $set_threw (i32.const 1) (i32.const 0))
            i64.const 0
        end
    )
)
