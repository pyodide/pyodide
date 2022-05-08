#include "Python.h"

#include "emscripten.h"

#define LOAD(n) ((offset += n, buffer.subarray(offset - n, offset)))

#define LOAD_STRING(n) text_decoder.decode(up_to_first_zero(LOAD(n)))

#define SET_STRING(var, n) var = LOAD_STRING(n)

#define SET_OCTAL(var, n) var = parseInt(LOAD_STRING(n), 8)

#define SKIP_STRING(var, n) offset += n

#define SKIP_OCTAL(var, n) offset += n

int
tar_init_js(void);

EMSCRIPTEN_KEEPALIVE int
tar_init(void)
{
  return tar_init_js();
}

#include "include_js_file.h"
#include "tar.js"
