# 1 "src/core/jslib_asm.S"
# 1 "<built-in>" 1
# 1 "<built-in>" 3
# 347 "<built-in>" 3
# 1 "<command line>" 1
# 1 "<built-in>" 2
# 1 "src/core/jslib_asm.S" 2
.globl Jsv_is_null
Jsv_is_null:
  .functype Jsv_is_null (externref) -> (i32)
  local.get 0
  ref.is_null
  end_function
