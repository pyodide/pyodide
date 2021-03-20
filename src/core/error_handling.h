#ifndef ERROR_HANDLING_H
#define ERROR_HANDLING_H
// clang-format off
#define PY_SSIZE_T_CLEAN
#include "Python.h"
// clang-format on
#include <emscripten.h>

typedef int errcode;
#include "hiwire.h"

int
error_handling_init();

extern PyObject* internal_error;

/**
 * Raised when conversion between Javascript and Python fails.
 */
extern PyObject* conversion_error;

JsRef
wrap_exception(bool attach_python_error);

/**
 * Argument should be output of wrap_exception.
 */
errcode log_python_error(JsRef);

/**
 * Convert the active Python exception into a Javascript Error object and print
 * it to the console.
 */
void
pythonexc2js();

// Used by LOG_EM_JS_ERROR (behind DEBUG_F flag)
errcode
console_error(char* msg);

// Right now this is dead code (probably), please don't remove it.
// Intended for debugging purposes.
errcode
console_error_obj(JsRef obj);

/**
 * EM_JS Wrappers
 * Wrap EM_JS so that it produces functions that follow the Python return
 * conventions. We catch javascript errors and proxy them and use
 * `PyErr_SetObject` to hand them off to python. We need two variants, one
 * for functions that return pointers / references (return 0)
 * the other for functions that return numbers (return -1).
 *
 * WARNING: These wrappers around EM_JS cause macros in body to be expanded,
 * where this would be prevented by the ordinary EM_JS macro.
 * This causes trouble with true and false.
 * In types.h we provide nonstandard definitions:
 * false ==> (!!0)
 * true ==> (!!1)
 * These work as expected in both C and javascript.
 *
 * Note: this change in expansion behavior is unavoidable unless we copy the
 * definition of macro EM_JS into our code due to limitations of the C macro
 * engine. It is useful to be able to use macros in the EM_JS, but it might lead
 * to some unpleasant surprises down the road...
 */

// clang-format off
#ifdef DEBUG_F
// Yes, the "do {} while(0)" trick solves the same problem in the same way in
// javascript!
#define LOG_EM_JS_ERROR(__funcname__, err)                                              \
  do {                                                                                  \
    console.error(                                                                      \
      `EM_JS raised exception on line __LINE__ in func __funcname__ in file __FILE__`); \
    console.error("Error was:", err);                                                   \
  } while (0)
#else
#define LOG_EM_JS_ERROR(__funcname__, err)
#endif

// Need an extra layer to expand LOG_EM_JS_ERROR.
#define EM_JS_DEFER(ret, func_name, args, body...)                             \
  EM_JS(ret, func_name, args, body)

#define EM_JS_REF(ret, func_name, args, body...)                               \
  EM_JS_DEFER(ret, func_name, args, {                                          \
    "use strict";                                                              \
    try    /* intentionally no braces, body already has them */                \
      body /* <== body of func */                                              \
    catch (e) {                                                                \
        LOG_EM_JS_ERROR(func_name, e);                                         \
        Module.handle_js_error(e);                                             \
        return 0;                                                              \
    }                                                                          \
    throw new Error(                                                           \
      "Assertion error: control reached end of function without return"        \
    );                                                                         \
  })

#define EM_JS_NUM(ret, func_name, args, body...)                               \
  EM_JS_DEFER(ret, func_name, args, {                                          \
    "use strict";                                                              \
    try    /* intentionally no braces, body already has them */                \
      body /* <== body of func */                                              \
    catch (e) {                                                                \
        LOG_EM_JS_ERROR(func_name, e);                                       \
        Module.handle_js_error(e);                                             \
        return -1;                                                             \
    }                                                                          \
    return 0;  /* some of these were void */                                   \
  })
// clang-format on

/**
 * Failure Macros
 * These macros are intended to help make error handling as uniform and
 * unobtrusive as possible. The EM_JS wrappers above make it so that the
 * EM_JS calls behave just like Python API calls when it comes to errors
 * So these can be used equally well for both cases.
 *
 * These all use "goto finally;" so any function that uses them must have
 * a finally label. Luckily, the compiler errors triggered byforgetting
 * this are usually quite clear.
 *
 * We define a feature flag "DEBUG_F" that will use "console.error" to
 * report a message whenever these functions exit with error. This should
 * particularly help to track down problems when C code fails to handle
 * the error generated.
 *
 * FAIL() -- unconditionally goto finally; (but also log it with
 *           console.error if DEBUG_F is enabled)
 * FAIL_IF_NULL(ref) -- FAIL() if ref == NULL
 * FAIL_IF_MINUS_ONE(num) -- FAIL() if num == -1
 * FAIL_IF_ERR_OCCURRED(num) -- FAIL() if PyErr_Occurred()
 */

#ifdef DEBUG_F
#define FAIL()                                                                 \
  do {                                                                         \
    char* msg;                                                                 \
    asprintf(&msg,                                                             \
             "Raised exception on line %d in func %s, file %s\n",              \
             __LINE__,                                                         \
             __func__,                                                         \
             __FILE__);                                                        \
    console_error(msg);                                                        \
    free(msg);                                                                 \
    goto finally;                                                              \
  } while (0)

#else
#define FAIL() goto finally
#endif

#define FAIL_IF_NULL(ref)                                                      \
  do {                                                                         \
    if ((ref) == NULL) {                                                       \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#define FAIL_IF_MINUS_ONE(num)                                                 \
  do {                                                                         \
    if ((num) == -1) {                                                         \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#define FAIL_IF_NONZERO(num)                                                   \
  do {                                                                         \
    if ((num) != 0) {                                                          \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#define FAIL_IF_ERR_OCCURRED()                                                 \
  do {                                                                         \
    if (PyErr_Occurred()) {                                                    \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#endif // ERROR_HANDLING_H
