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

int
error_handling_init();

// WARNING: These wrappers around EM_JS cause macros in body to be expanded.
// This causes trouble with true and false.
// In types.h we provide nonstandard definitions:
// false ==> (!!0)
// true ==> (!!1)
// These work as expected in both C and javascript.

// clang-format off
#define EM_JS_REF(ret, func_name, args, body...)                               \
  EM_JS(ret, func_name, args, {                                                \
    /* "use strict";  TODO: enable this. */                                    \
    try    /* intentionally no braces, body already has them */                \
      body /* <== body of func */                                              \
    catch (e) {                                                                \
        /* Dummied out until calling code is ready to catch these errors */    \
        throw e;                                                               \
        Module.handle_js_error(e);                                             \
        return 0;                                                              \
    }                                                                          \
  })

#define EM_JS_NUM(ret, func_name, args, body...)                               \
  EM_JS(ret, func_name, args, {                                                \
    /* "use strict";  TODO: enable this. */                                    \
    try    /* intentionally no braces, body already has them */                \
      body /* <== body of func */                                              \
    catch (e) {                                                                \
        /* Dummied out until calling code is ready to catch these errors */    \
        throw e;                                                               \
        Module.handle_js_error(e);                                             \
        return -1;                                                             \
    }                                                                          \
  })
// clang-format on

#endif // ERROR_HANDLING_H
