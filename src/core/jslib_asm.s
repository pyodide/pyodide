.globl JsvNull_Check
JsvNull_Check:
  .functype JsvNull_Check (externref) -> (i32)
  local.get 0
  ref.is_null
  end_function
