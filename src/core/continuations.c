#include "emscripten.h"

// clang-format off
EM_JS(int, continuations_init_js, (), {
  initSuspenders();
})
// clang-format on

int
continuations_init(void)
{
  return continuations_init_js();
}
