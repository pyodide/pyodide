#ifndef PYODIDE_HIWIRE_H
#define PYODIDE_HIWIRE_H
#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "hiwire/hiwire.h"
#include "stdalign.h"
#include "types.h"
#define WARN_UNUSED __attribute__((warn_unused_result))
#define hiwire_incref wrapped_hiwire_incref

typedef HwRef JsRef;
typedef __externref_t JsVal;

// Error handling will want to see JsRef.
#include "error_handling.h"

// Special JsRefs for singleton constants.
// (These must be even because the least significance bit is set to 0 for
// singleton constants.)
extern const JsRef Js_undefined;
extern const JsRef Js_true;
extern const JsRef Js_false;
extern const JsRef Js_null;

// For when the return value would be Option<JsRef>
extern const JsRef Js_novalue;

// A mechanism for handling static JavaScript strings from C
// This is copied from the Python mechanism for handling static Python strings
// from C See the Python definition here:
// https://github.com/python/cpython/blob/24da544014f78e6f1440d5ce5c2d14794a020340/Include/cpython/object.h#L37

typedef struct Js_Identifier
{
  const char* string;
  JsRef object;
} Js_Identifier;

#define Js_static_string_init(value)                                           \
  {                                                                            \
    .string = value, .object = NULL                                            \
  }
#define Js_static_string(varname, value)                                       \
  static Js_Identifier varname = Js_static_string_init(value)
#define Js_IDENTIFIER(varname) Js_static_string(JsId_##varname, #varname)

#define hiwire_CLEAR(x)                                                        \
  do {                                                                         \
    hiwire_decref(x);                                                          \
    x = NULL;                                                                  \
  } while (0)

// ==================== hiwire API  ====================

/**
 * Initialize the variables and functions required for hiwire.
 */
int
hiwire_init();

/**
 * Increase the reference count on an object.
 *
 * Returns: The new reference
 */
JsRef
hiwire_incref(JsRef idval);

/**
 * Increase the reference count on an object and return a JsRef which is unique
 * to the object.
 *
 * I.e., if `Hiwire.get_value(id1) === Hiwire.get_value(id2)` then
 * hiwire_incref_deduplicate(id1) == hiwire_incref_deduplicate(id2).
 *
 * This is used for the id for JsProxies so that equality checks work correctly.
 *
 * Returns: The new reference
 */
JsRef
hiwire_incref_deduplicate(JsRef idval);

/**
 * Decrease the reference count on an object.
 */
void
hiwire_decref(JsRef idval);

#endif /* HIWIRE_H */
