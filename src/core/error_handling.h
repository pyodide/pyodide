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

errcode
log_error(char* msg);

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
    throw new Error("Assertion error: control reached end of function without return");\
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
    return 0;  /* some of these were void */                                   \
  })
// clang-format on

#ifdef DEBUG_F
#define FAIL()                                                                 \
  do {                                                                         \
    char* msg;                                                                 \
    asprintf(&msg,                                                             \
             "Raised exception on line %d in func %s, file %s\n",              \
             __LINE__,                                                         \
             __func__,                                                         \
             __FILE__);                                                        \
    log_error(msg);                                                            \
    free(msg);                                                                 \
    goto finally                                                               \
  } while (0)

#else
#define FAIL() goto finally
#endif

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
