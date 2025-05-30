#include <emscripten.h>
#include <stdio.h>

EMSCRIPTEN_KEEPALIVE int
print_stdout(const char* msg)
{
  fprintf(stdout, "%s\n", msg);
  return 0;
}

EMSCRIPTEN_KEEPALIVE int
print_stderr(const char* msg)
{
  fprintf(stderr, "%s\n", msg);
  return 0;
}
