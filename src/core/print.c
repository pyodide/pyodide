#include <emscripten.h>
#include <stdio.h>

// Note: We cannot use stdout / stderr const from stdio.h because we override
// the stream when initializing the Pyodide runtime. Also users can override the
// streams using `setStderr` and `setStdout`. Therefore, we always need to open
// the stream on each call.

EMSCRIPTEN_KEEPALIVE int
print_stdout(const char* msg)
{
  FILE* fp = fopen("/dev/stdout", "w");
  if (fp == NULL) {
    return -1;
  }
  fprintf(fp, "%s\n", msg);
  fclose(fp);

  return 0; // Success
}

EMSCRIPTEN_KEEPALIVE int
print_stderr(const char* msg)
{
  FILE* fp = fopen("/dev/stderr", "w");
  if (fp == NULL) {
    return -1;
  }
  fprintf(fp, "%s\n", msg);
  fclose(fp);

  return 0; // Success
}
