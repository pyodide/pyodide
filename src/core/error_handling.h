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

// Poor clang-format, both macros and javascript at once make it pretty sick.
// clang-format off
#ifdef EM_JS_TRACE_F
// Tracing macros if compiled with "-D EM_JS_TRACE_F"
// Print extra info whenever we enter or exit EM_JS calls.
// Yes, the "do {} while(0)" trickworks in javascript too!
#define EM_JS_TRACE_ENTER(func_name)                                           \
  let ____haderr = false;                                                      \
  do {                                                                         \
    console.log(`Entering function func_name                                   \
      (line __LINE__ file __FILE__ )`);                                        \
    console.log("Arguments were:", arguments);                                 \
  } while (0)

#define EM_JS_TRACE_ERROR(func_name, err)                                      \
  do {                                                                         \
    ____haderr = true;                                                         \
    console.log(`Exiting function with error func_name                         \
      (line __LINE__ file __FILE__ )`);                                        \
    console.error("error was:", err);                                          \
  } while (0)

#define EM_JS_TRACE_EXIT(func_name)                                            \
  if(!____haderr){                                                             \
    console.log(`Exiting function func_name                                    \
      (line __LINE__ file __FILE__ )`);                                        \
  }

#else
// Without "-D EM_JS_TRACE_F" these just do nothing.
#define EM_JS_TRACE_ENTER(func_name)
#define EM_JS_TRACE_ERROR(func_name, err)
#define EM_JS_TRACE_EXIT(func_name)
#endif

// WARNING: These wrappers around EM_JS cause macros in body to be expanded.
// This causes trouble with true and false.
// In types.h we provide nonstandard definitions:
// false ==> (!!0)
// true ==> (!!1)
// These work as expected in both C and javascript.


#define _EM_JS_WRAP_HELPER2(ret, func_name, args, body...)  \
  EM_JS(ret, func_name, args, body)

#define _EM_JS_WRAP_HELPER(succ_ret, err_ret, ret, func_name, args, body...)   \
  _EM_JS_WRAP_HELPER2(ret, func_name, args, {                                  \
    /* "use strict";  TODO: enable this. */                                    \
    EM_JS_TRACE_ENTER(func_name);                                              \
    try    /* intentionally no braces, body already has them */                \
      body /* <== body of func */                                              \
    catch (e) {                                                                \
      EM_JS_TRACE_ERROR(func_name, e);                                         \
      /* Dummied out until calling code is ready to catch these errors */      \
      throw e;                                                                 \
      Module.handle_js_error(e);                                               \
      err_ret;                                                                 \
    } finally {                                                                \
      EM_JS_TRACE_EXIT(func_name);                                             \
    }                                                                          \
    succ_ret;                                                                  \
  })

#define EM_JS_REF(ret, func_name, args, body...)                               \
  _EM_JS_WRAP_HELPER(                                                          \
    /* In this case, throw error if we don't return otherwise */               \
    Module.handle_js_error(                                                    \
      new Error("Control reached end of nonvoid function w/o return")          \
    );                                                                         \
    return 0;,                                                                 \
    return 0,  /* on failure return 0 (null) */                                \
    ret, func_name, args, body)

#define EM_JS_NUM(ret, func_name, args, body...)                               \
  _EM_JS_WRAP_HELPER(                                                          \
    return 0,  /* if control reaches end with no error return 0 */             \
    return -1, /* on failure return -1 */                                      \
    ret, func_name, args, body)
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
    goto finally;                                                              \
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
