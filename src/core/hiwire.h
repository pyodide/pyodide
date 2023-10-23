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
 * Convert an array of int32s to a Number or BigInt depending on whether it is
 * less than MAX_SAFE_INTEGER or not. The representation is assumed to be signed
 * and little endian.
 */
JsRef
hiwire_int_from_digits(const unsigned int* bytes, size_t nbytes);

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

/**
 * Create a new JavaScript integer with the given value.
 *
 * Returns: New reference
 */
JsRef
hiwire_int(int val);

/**
 * Create a new JavaScript float with the given value.
 *
 * Returns: New reference
 */
JsRef
hiwire_double(double val);

/**
 * Call a js function with one argument
 */
JsRef
hiwire_call_OneArg(JsRef idobj, JsRef idarg);

JsRef
hiwire_call_bound(JsRef idfunc, JsRef idthis, JsRef idargs);

bool
hiwire_HasMethod(JsRef obj, JsRef name);

/**
 * name is the method name, as null-terminated UTF8.
 * args is an Array containing the arguments.
 *
 */
JsRef
hiwire_CallMethodString(JsRef obj, const char* name, JsRef args);

/**
 * name is the method name, as null-terminated UTF8.
 * arg is the argument
 */
JsRef
hiwire_CallMethodString_OneArg(JsRef obj, const char* name, JsRef arg);

JsRef
hiwire_CallMethod(JsRef obj, JsRef name, JsRef args);

JsRef
hiwire_CallMethod_OneArg(JsRef obj, JsRef name, JsRef arg);

/**
 * Calls the constructor of a class object.
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
JsRef
hiwire_construct(JsRef idobj, JsRef idargs);

/**
 * Returns the value of the `size` or `length` member on a JavaScript object.
 * Prefers the `size` member if present and a number to the `length` field. If
 * both `size` and `length` are missing or not a number, returns `-1` to
 * indicate error.
 */
int
hiwire_get_length(JsRef idobj);

/**
 * Returns the boolean value of a JavaScript object.
 */
bool
hiwire_get_bool(JsRef idobj);

/**
 * Check if the object is a comlink proxy.
 */
bool
hiwire_is_comlink_proxy(JsRef idobj);

/**
 * Returns Promise.resolve(obj)
 *
 * Returns: New reference to JavaScript promise
 */
JsRef
hiwire_resolve_promise(JsRef idobj);

/**
 * Get a subarray from a TypedArray
 */
JsRef
hiwire_subarray(JsRef idarr, int start, int end);

// ==================== JsMap API  ====================

/**
 * Create a new Map.
 */
JsRef
JsMap_New();

/**
 * Does map.set(key, value).
 */
errcode WARN_UNUSED
JsMap_Set(JsRef mapid, JsRef keyid, JsRef valueid);

// ==================== JsSet API  ====================

/**
 * Create a new Set.
 */
JsRef
JsSet_New();

/**
 * Does set.add(key).
 */
errcode WARN_UNUSED
JsSet_Add(JsRef mapid, JsRef keyid);

#endif /* HIWIRE_H */
