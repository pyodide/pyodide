#include <emscripten.h>
#include <stdio.h>

// Note: We cannot use stdout / stderr const from stdio.h because we override
// the stream when initializing the Pyodide runtime. Also users can override the
// streams using `setStderr` and `setStdout`. Therefore, we always need to open
// the stream on each call.

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
