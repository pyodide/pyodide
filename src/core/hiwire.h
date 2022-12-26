#ifndef HIWIRE_H
#define HIWIRE_H
#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "stdalign.h"
#include "types.h"
#define WARN_UNUSED __attribute__((warn_unused_result))

/**
 * hiwire: A super-simple framework for converting values between C and
 * JavaScript.
 *
 * Arbitrary JavaScript objects are referenced from C using an opaque JsRef
 * value.
 *
 * JavaScript objects passed to the C side must be manually reference-counted.
 * Use `hiwire_incref` if you plan to store the object on the C side. Use
 * `hiwire_decref` when done. Internally, the objects are stored in a global
 * object. There may be one or more keys pointing to the same object.
 */

// JsRef is a NewType of int. We need
//
// alignof(JsRef) = alignof(int) = 4 and
// sizeof(JsRef) = sizeof(int) = 4
//
// To be future proof, we have _Static_asserts for this.
// I also added
// -Werror=int-conversion -Werror=incompatible-pointer-types
// to the compile flags, to ensure that no implicit casts will happen between
// JsRef and any other type.
struct _JsRefStruct
{};

typedef struct _JsRefStruct* JsRef;

_Static_assert(alignof(JsRef) == alignof(int),
               "JsRef should have the same alignment as int.");
_Static_assert(sizeof(JsRef) == sizeof(int),
               "JsRef should have the same size as int.");

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
 * Create a new JavaScript string, given a pointer to a null-terminated buffer
 * containing UTF8. The string data itself is copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_string_utf8(const char* ptr);

/**
 * Create a new JavaScript boolean value.
 * Return value is true if boolean != 0, false if boolean == 0.
 *
 * Returns: "New" reference
 */
JsRef
hiwire_from_bool(bool boolean);

/**
 * Convert value to C boolean
 */
bool
hiwire_to_bool(JsRef value);

/**
 * Throw a javascript Error object.
 * Steals a reference to the argument.
 */
void _Py_NO_RETURN
hiwire_throw_error(JsRef iderr);

/**
 * Call a js function
 *
 * idargs is a hiwire Array containing the arguments.
 *
 */
JsRef
hiwire_call(JsRef idobj, JsRef idargs);

/**
 * Call a js function with one argument
 */
JsRef
hiwire_call_OneArg(JsRef idobj, JsRef idarg);

/**
 * Call a function
 *
 * Arguments are specified as a NULL-terminated variable arguments list of
 * JsRefs.
 *
 */
JsRef
hiwire_call_va(JsRef idobj, ...);

JsRef
hiwire_call_bound(JsRef idfunc, JsRef idthis, JsRef idargs);

bool
hiwire_HasMethod(JsRef obj, JsRef name);

bool
hiwire_HasMethodId(JsRef obj, Js_Identifier* name);

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

/**
 * name is the method name, as null-terminated UTF8.
 * Arguments are specified as a NULL-terminated variable arguments list of
 * JsRefs.
 */
JsRef
hiwire_CallMethodString_va(JsRef obj, const char* name, ...);

JsRef
hiwire_CallMethod(JsRef obj, JsRef name, JsRef args);

JsRef
hiwire_CallMethod_OneArg(JsRef obj, JsRef name, JsRef arg);

JsRef
hiwire_CallMethod_va(JsRef obj, JsRef name, ...);

/**
 * name is the method name, as a Js_Identifier
 * args is a hiwire Array containing the arguments.
 */
JsRef
hiwire_CallMethodId(JsRef obj, Js_Identifier* name, JsRef args);

/**
 * name is the method name, as a Js_Identifier
 * Arguments are specified as a NULL-terminated variable arguments list of
 * JsRefs.
 */
JsRef
hiwire_CallMethodId_va(JsRef obj, Js_Identifier* name, ...);

JsRef
hiwire_CallMethodId_NoArgs(JsRef obj, Js_Identifier* name);

JsRef
hiwire_CallMethodId_OneArg(JsRef obj, Js_Identifier* name, JsRef arg);

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
 * Test if the object has a `size` or `length` member which is a number. As a
 * special case, if the object is a function the `length` field is ignored.
 */
bool
hiwire_has_length(JsRef idobj);

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
 * Check if the object is a function.
 */
bool
hiwire_is_function(JsRef idobj);

bool
hiwire_is_generator(JsRef idobj);

bool
hiwire_is_async_generator(JsRef idobj);

/**
 * Check if the object is a comlink proxy.
 */
bool
hiwire_is_comlink_proxy(JsRef idobj);

/**
 * Check if the object is an error.
 */
bool
hiwire_is_error(JsRef idobj);

/**
 * Returns true if the object is a promise.
 */
bool
hiwire_is_promise(JsRef idobj);

/**
 * Returns Promise.resolve(obj)
 *
 * Returns: New reference to JavaScript promise
 */
JsRef
hiwire_resolve_promise(JsRef idobj);

/**
 * Gets the string representation of an object by calling `toString`.
 *
 * Returns: New reference to JavaScript string
 */
JsRef
hiwire_to_string(JsRef idobj);

/**
 * Gets the `typeof` string for a value.
 *
 * Returns: New reference to JavaScript string
 */
JsRef
hiwire_typeof(JsRef idobj);

/**
 * Gets `value.constructor.name`.
 *
 * Returns: New reference to JavaScript string
 */
char*
hiwire_constructor_name(JsRef idobj);

/**
 * Returns non-zero if a < b.
 */
bool
hiwire_less_than(JsRef ida, JsRef idb);

/**
 * Returns non-zero if a <= b.
 */
bool
hiwire_less_than_equal(JsRef ida, JsRef idb);

/**
 * Returns non-zero if a == b.
 */
bool
hiwire_equal(JsRef ida, JsRef idb);

/**
 * Returns non-zero if a != b.
 */
bool
hiwire_not_equal(JsRef idx, JsRef idb);

/**
 * Returns non-zero if a > b.
 */
bool
hiwire_greater_than(JsRef ida, JsRef idb);

/**
 * Returns non-zero if a >= b.
 */
bool
hiwire_greater_than_equal(JsRef ida, JsRef idb);

/**
 * Returns the reversed iterator associated with an array.
 */
JsRef
hiwire_reversed_iterator(JsRef idobj);

/**
 * Copies the buffer contents of a given ArrayBuffer view or ArrayBuffer into
 * the memory at ptr.
 */
errcode WARN_UNUSED
hiwire_assign_to_ptr(JsRef idobj, void* ptr);

/**
 * Copies the memory at ptr into a given ArrayBuffer view or ArrayBuffer.
 */
errcode WARN_UNUSED
hiwire_assign_from_ptr(JsRef idobj, void* ptr);

errcode
hiwire_write_to_file(JsRef idobj, int fd);

errcode
hiwire_read_from_file(JsRef idobj, int fd);

/**
 * Convert a buffer into a file in a copy-free manner using "canOwn" parameter.
 * Cannot directly use the buffer anymore after using this.
 */
errcode
hiwire_into_file(JsRef idobj, int fd);

/**
 * Get a data type identifier for a given typedarray.
 */
void
hiwire_get_buffer_info(JsRef idobj,
                       Py_ssize_t* byteLength_ptr,
                       char** format_ptr,
                       Py_ssize_t* size_ptr,
                       bool* check_assignments);

/**
 * Get a subarray from a TypedArray
 */
JsRef
hiwire_subarray(JsRef idarr, int start, int end);

// ==================== JsArray API  ====================

bool
JsArray_Check(JsRef idobj);

/**
 * Create a new JavaScript Array.
 *
 * Returns: New reference
 */
JsRef
JsArray_New();

/**
 * Push a value to the end of a JavaScript array.
 */
errcode WARN_UNUSED
JsArray_Push(JsRef idobj, JsRef idval);

/**
 * Same as JsArray_Push but panics on failure
 */
int
JsArray_Push_unchecked(JsRef idobj, JsRef idval);

/**
 * Get an object member by integer.
 *
 * Returns: New reference
 */
JsRef
JsArray_Get(JsRef idobj, int idx);

/**
 * Set an object member by integer.
 */
errcode WARN_UNUSED
JsArray_Set(JsRef idobj, int idx, JsRef idval);

errcode WARN_UNUSED
JsArray_Delete(JsRef idobj, int idx);

JsRef
JsArray_Splice(JsRef idobj, int idx);

JsRef
JsArray_slice(JsRef idobj, int slicelength, int start, int stop, int step);

errcode
JsArray_slice_assign(JsRef idobj,
                     int slicelength,
                     int start,
                     int stop,
                     int step,
                     int values_length,
                     PyObject** values);

errcode
JsArray_Clear(JsRef idobj);

// ==================== JsObject API  ====================

/**
 * Create a new JavaScript object.
 *
 * Returns: New reference
 */
JsRef
JsObject_New();

/**
 * Get an object member by string.
 *
 *
 * Returns: New reference
 */
JsRef
JsObject_GetString(JsRef idobj, const char* ptrname);

/**
 * Set an object member by string.
 */
errcode WARN_UNUSED
JsObject_SetString(JsRef idobj, const char* ptrname, JsRef idval);

/**
 * Delete an object member by string.
 */
errcode WARN_UNUSED
JsObject_DeleteString(JsRef idobj, const char* ptrname);

/**
 * Get the methods on an object, both on itself and what it inherits.
 *
 */
JsRef
JsObject_Dir(JsRef idobj);

/**
 * Returns `Object.entries(obj)`
 */
JsRef
JsObject_Entries(JsRef idobj);

/**
 * Returns `Object.keys(obj)`
 */
JsRef
JsObject_Keys(JsRef idobj);

/**
 * Returns `Object.values(obj)`
 */
JsRef
JsObject_Values(JsRef idobj);

// ==================== JsString API  ====================

JsRef
JsString_InternFromCString(const char* str);

JsRef
JsString_FromId(Js_Identifier* id);

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
