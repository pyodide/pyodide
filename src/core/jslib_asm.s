.globl Jsv_is_null
Jsv_is_null:
  .functype Jsv_is_null (externref) -> (i32)
  local.get 0
  ref.is_null
  end_function
