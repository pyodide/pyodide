# Pseudocode:
#
#   __externref_t syncify_catch_trampoline(__externref_t p) {
#     try {
#       return suspendForPromise(p);
#     } catch (JSTag error) {
#       set_syncify_error(error);
#       return JS_ERROR;
#     }
#   }
#
# See discussion in suspenders.c

.tagtype JSTag externref

.functype suspendForPromise (externref) -> (externref)

.functype set_syncify_error (externref) -> (externref)

.section .text.syncify_catch_trampoline,"",@
.globl syncify_catch_trampoline
syncify_catch_trampoline:
  .functype syncify_catch_trampoline (externref) -> (externref)
  try externref
    local.get 0
    call suspendForPromise
  catch JSTag
    call set_syncify_error
  end_try
  end_function
