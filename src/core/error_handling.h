#ifndef ERROR_HANDLING_H
#define ERROR_HANDLING_H

/**  Wrap EM_JS so that it produces functions that follow the Python return
 *  conventions. We catch javascript errors and proxy them and use
 *  `PyErr_SetObject` to hand them off to python. We need two variants, one
 *  for functions that return pointers / references (return 0)
 *  the other for functions that return numbers (return -1).
 */

typedef int errcode;

// Hiwire wants to import us for errcode, so import hiwire after typedef.
#include "hiwire.h"
#include <emscripten.h>

// clang-format off
#define EM_JS_REF(ret, func_name, args, body...)                               \
  EM_JS(ret, func_name, args, {                                                \
    /* "use strict";  TODO: enable this. */                                    \
    try    /* intentionally no braces. */                                      \
      body /* <== body of func */                                              \
    catch (e) {                                                                \
        throw e;                                                               \
        /* Dummied out until calling code is ready to catch these errors */    \
        Module.handle_js_error(e);                                             \
        return -1;                                                             \
    }                                                                          \
  })

#define EM_JS_NUM(ret, func_name, args, body...)                               \
  EM_JS(ret, func_name, args, {                                                \
    /* "use strict";  TODO: enable this. */                                    \
    try    /* intentionally no braces. */                                      \
      body /* <== body of func */                                              \
    catch (e) {                                                                \
        throw e;                                                               \
        /* Dummied out until calling code is ready to catch these errors */    \
        Module.handle_js_error(e);                                             \
        return -1;                                                             \
    }                                                                          \
  })
// clang-format on

#define FAIL() goto finally

#define FAIL_IF_NULL(x)                                                        \
  do {                                                                         \
    if (x == NULL) {                                                           \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#define FAIL_IF_MINUS_ONE(x)                                                   \
  do {                                                                         \
    if (x != 0) {                                                              \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#define FAIL_IF_ERR_OCCURRED(x)                                                \
  do {                                                                         \
    if (PyErr_Occurred()) {                                                    \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#endif // ERROR_HANDLING_H
