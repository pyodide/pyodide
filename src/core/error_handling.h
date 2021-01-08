#ifndef ERROR_HANDLING_H
#define ERROR_HANDLING_H

typedef int errcode;

// Hiwire wants to import us for errcode, so import hiwire after "typedef int
// errcode;".
#include "hiwire.h"
#include <emscripten.h>

int
error_handling_init();

errcode
log_error(char* msg);

/** EM_JS Wrappers
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

/** Failure Macros
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
    log_error(msg);                                                            \
    free(msg);                                                                 \
    goto finally                                                               \
  } while (0)

#else
#define FAIL() goto finally
#endif

#define FAIL_IF_NULL(ref)                                                      \
  do {                                                                         \
    if (ref == NULL) {                                                         \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#define FAIL_IF_MINUS_ONE(num)                                                 \
  do {                                                                         \
    if (num != 0) {                                                            \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

#define FAIL_IF_ERR_OCCURRED()                                                 \
  do {                                                                         \
    if (PyErr_Occurred()) {                                                    \
      FAIL();                                                                  \
    }                                                                          \
  } while (0)

/** Reference counting Macros
 * These macros are for use with the FAIL macros above to help simplify
 * reference counting, in particular to simplify analysis of the interaction
 * between error handling and refcounts. Code with error handling has LOTS of
 * branching. We collect all the different branches into the "finally" block
 * and CLEAR all of our references there other than the return value.
 *
 * DECLARE_PyObjects(id1, id2, ...) -- expands to:
 *      PyObject* id1 = NULL;
 *      PyObject* id2 = NULL;
 *      ...
 * DECLARE_JsRefs(id1, id2, ...) -- expands to:
 *      JsRef id1 = NULL;
 *      JsRef id2 = NULL;
 *      ...
 *
 * It's key that each variable be initialized to NULL, otherwise we will crash
 * if an error occurs before we assign to the variable.
 *
 * CLEAR_PyObjects(id1, id2, ...) -- expands to:
 *      hiwire_CLEAR(id1);
 *      hiwire_CLEAR(id2);
 *      ...
 *
 * CLEAR_JsRefs(id1, id2, ...) -- expands to:
 *      hiwire_CLEAR(id1);
 *      hiwire_CLEAR(id2);
 *      ...
 *
 * In the finally block of each function, CLEAR_PyObjects resp CLEAR_JsRefs
 * should be called with exactly the same arguments as DECLARE_PyObjects, resp
 * DECLARE_JsRefs were called with at the beginning of the function.
 * In particular, the return varible of the function should be declared
 * separately, not DECLARE_PyObjects or DECLARE_JsRefs.
 */

#include "map.h"

// Declare a list of identifiers as PyObject* and initialize to NULL.
#define DECLARE_PyObjects(identifiers...)                                      \
  _eh_MAP_ALLOW_TRAILING_COMMA(_eh_DECLARE_PyObject, identifiers)

// Declare a list of identifiers as JsRef and initialize to NULL.
#define DECLARE_JsRefs(identifiers...)                                         \
  _eh_MAP_ALLOW_TRAILING_COMMA(_eh_DECLARE_JsRef, identifiers)

// Do `Py_CLEAR(x);` on a list of identifiers
#define CLEAR_PyObjects(identifiers...)                                        \
  _eh_MAP_ALLOW_TRAILING_COMMA(Py_CLEAR, identifiers)

// Do `hiwire_CLEAR(x);` on a list of identifiers
#define CLEAR_JsRefs(identifiers...)                                           \
  _eh_MAP_ALLOW_TRAILING_COMMA(hiwire_CLEAR, identifiers)

// Helpers
#define _eh_DECLARE_PyObject(name) PyObject* name = NULL

#define _eh_DECLARE_JsRef(name) JsRef name = NULL

// An adjustment of MAP that allows a trailing comma in the argument list.
// Raw map leads to an incomprehensible compiler error
#define _eh_MAP_ALLOW_TRAILING_COMMA(f, args...)                               \
  MAP_UD(_eh_DO_F_If_NONEMPTY, f, args)

// See https://gustedt.wordpress.com/2010/06/08/detect-empty-macro-arguments/

// If "args" has no comma, we see exactly one argument and _2 in
// HAS_COMMA_HELPER is set to 0. If there is exactly one comma, list looks like
// `a,b,1, 0` and _2 is set to 1.
#define _eh_HAS_COMMA(args...) _eh_HAS_COMMA_HELPER(args, 1, 0)
#define _eh_HAS_COMMA_HELPER(_0, _1, _2, ...) _2

// If argument is nonempty (and doesn't start with ()), then
// "_TRIGGER_PARENTHESIS_" is separated from the parens and will not expand. If
// argument is empty,
// "_TRIGGER_PARENTHESIS_()" is seen and expands into a comma, detected by
// HAS_COMMA
#define _eh_IS_EMPTY(args...) _eh_HAS_COMMA(_eh_TRIGGER_PARENTHESIS_ args())
#define _eh_TRIGGER_PARENTHESIS_(...) ,

// If "test" expands to 1, do "case_true", if it's 0 do "case_false"
// ## blocks "test" from being expanded. We want "test" to be expanded
// So first we do extra layer of indirection TEST_EXP.
#define _eh_TEST(test, case_true, case_false)                                  \
  _eh_TEST_EXP(test, case_true, case_false)
#define _eh_TEST_EXP(test, case_true, case_false)                              \
  _eh_TEST_##test(case_true, case_false)
#define _eh_TEST_0(case_true, case_false) case_false
#define _eh_TEST_1(case_true, case_false) case_true

// if "arg" is empty, do "case_true", if nonempty do "case_false"
#define _eh_IF_EMPTY(arg, case_true, case_false)                               \
  _eh_TEST(_eh_IS_EMPTY(arg), case_true, case_false)

#define _eh_DO_F_If_NONEMPTY(arg, f) _eh_IF_EMPTY(arg, , f(arg);)

#endif // ERROR_HANDLING_H
