#ifndef HIWIRE_H
#define HIWIRE_H
#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "stdalign.h"
#include "types.h"

/**
 * hiwire: A super-simple framework for converting values between C and
 * Javascript.
 *
 * Arbitrary Javascript objects are referenced from C using an opaque int value.
 * By convention, these ids are stored in variable names beginning with `id`.
 *
 * Javascript objects passed to the C side must be manually reference-counted.
 * Use `hiwire_incref` if you plan to store the object on the C side. Use
 * `hiwire_decref` when done. Internally, the objects are stored in a global
 * object. There may be one or more keys pointing to the same object.
 */

// JsRef is a NewType of int.
// I checked and
//  alignof(JsRef) = alignof(int) = 4
//  sizeof(JsRef) = sizeof(int) = 4
// Just to be extra future proof, I added assertions about this to the begining
// of main.c So we are all good for using JsRef as a newtype for int. I also
// added
//  -Werror=int-conversion -Werror=incompatible-pointer-types
// to the compile flags, so that no implicit casts will happen between JsRef
// and any other type.
struct _JsRefStruct
{};

typedef struct _JsRefStruct* JsRef;

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

#define hiwire_CLEAR(x)                                                        \
  do {                                                                         \
    hiwire_decref(x);                                                          \
    x = NULL;                                                                  \
  } while (0)

/**
 * Initialize the variables and functions required for hiwire.
 */
int
hiwire_init();

/**
 * Convert a string of hexadecimal digits to a Number or BigInt depending on
 * whether it is less than MAX_SAFE_INTEGER or not. The string is assumed to
 * begin with an optional sign followed by 0x followed by one or more digits.
 */
JsRef
hiwire_int_from_hex(const char* s);

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
errcode
hiwire_decref(JsRef idval);

/**
 * Create a new Javascript integer with the given value.
 *
 * Returns: New reference
 */
JsRef
hiwire_int(int val);

/**
 * Create a new Javascript float with the given value.
 *
 * Returns: New reference
 */
JsRef
hiwire_double(double val);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS4 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_string_ucs4(const char* ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS2 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_string_ucs2(const char* ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS1 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_string_ucs1(const char* ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a null-terminated buffer
 * containing UTF8. The string data itself is copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_string_utf8(const char* ptr);

/**
 * Create a new Javascript string, given a pointer to a null-terminated buffer
 * containing ascii (well, technically latin-1). The string data itself is
 * copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_string_ascii(const char* ptr);

/**
 * Create a new Javascript boolean value.
 * Return value is true if boolean != 0, false if boolean == 0.
 *
 * Returns: "New" reference
 */
JsRef
hiwire_bool(bool boolean);

bool
hiwire_is_array(JsRef idobj);

/**
 * Create a new Javascript Array.
 *
 * Returns: New reference
 */
JsRef
hiwire_array();

/**
 * Push a value to the end of a Javascript array.
 *
 * If the user no longer needs the value outside of the array, it is the user's
 * responsibility to decref it.
 */
errcode
hiwire_push_array(JsRef idobj, JsRef idval);

/**
 * Create a new Javascript object.
 *
 * Returns: New reference
 */
JsRef
hiwire_object();

/**
 * Throw a javascript Error object.
 * Steals a reference to the argument.
 */
void _Py_NO_RETURN
hiwire_throw_error(JsRef iderr);

/**
 * Get an object member by string.
 *
 *
 * Returns: New reference
 */
JsRef
hiwire_get_member_string(JsRef idobj, const char* ptrname);

/**
 * Set an object member by string.
 */
errcode
hiwire_set_member_string(JsRef idobj, const char* ptrname, JsRef idval);

/**
 * Delete an object member by string.
 */
errcode
hiwire_delete_member_string(JsRef idobj, const char* ptrname);

/**
 * Get an object member by integer.
 *
 * Returns: New reference
 */
JsRef
hiwire_get_member_int(JsRef idobj, int idx);

/**
 * Set an object member by integer.
 */
errcode
hiwire_set_member_int(JsRef idobj, int idx, JsRef idval);

errcode
hiwire_delete_member_int(JsRef idobj, int idx);

/**
 * Get the methods on an object, both on itself and what it inherits.
 *
 */
JsRef
hiwire_dir(JsRef idobj);

/**
 * Call a function
 *
 * idargs is a hiwire Array containing the arguments.
 *
 */
JsRef
hiwire_call(JsRef idobj, JsRef idargs);

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

/**
 * Call a member function.
 *
 * ptrname is the member name, as a null-terminated UTF8.
 *
 * idargs is a hiwire Array containing the arguments.
 *
 */
JsRef
hiwire_call_member(JsRef idobj, const char* ptrname, JsRef idargs);

/**
 * Call a member function.
 *
 * ptrname is the member name, as a null-terminated UTF8.
 *
 * Arguments are specified as a NULL-terminated variable arguments list of
 * JsRefs.
 *
 */
JsRef
hiwire_call_member_va(JsRef idobj, const char* ptrname, ...);

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
 * Returns the value of the `size` or `length` member on a Javascript object.
 * Prefers the `size` member if present and a number to the `length` field. If
 * both `size` and `length` are missing or not a number, returns `-1` to
 * indicate error.
 */
int
hiwire_get_length(JsRef idobj);

/**
 * Returns the boolean value of a Javascript object.
 */
bool
hiwire_get_bool(JsRef idobj);

/**
 * Check whether `typeof obj.has === "function"`
 */
bool
hiwire_has_has_method(JsRef idobj);

/**
 * Does `obj.has(val)`. Doesn't check type of return value, if it isn't a
 * boolean or an integer it will get coerced to false.
 */
bool
hiwire_call_has_method(JsRef idobj, JsRef idval);

/**
 * Check whether `typeof obj.includes === "function"`.
 */
bool
hiwire_has_includes_method(JsRef idobj);

/**
 * Does `obj.includes(val)`. Doesn't check type of return value, if it isn't a
 * boolean or an integer it will get coerced to `false`.
 */
bool
hiwire_call_includes_method(JsRef idobj, JsRef idval);

/**
 * Check whether `typeof obj.get === "function"`.
 */
bool
hiwire_has_get_method(JsRef idobj);

/**
 * Call `obj.get(key)`. If the result is `undefined`, we check for a `has`
 * method and if one is present call `obj.has(key)`. If this returns false we
 * return `NULL` to signal a `KeyError` otherwise we return `Js_Undefined`. If
 * no `has` method is present, we return `Js_Undefined`.
 */
JsRef
hiwire_call_get_method(JsRef idobj, JsRef idkey);

/**
 * Check whether `typeof obj.set === "function"`.
 */
bool
hiwire_has_set_method(JsRef idobj);

/**
 * Call `obj.set(key, value)`. Javascript standard is that `set` returns `false`
 * to indicate an error condition, but we ignore the return value.
 */
errcode
hiwire_call_set_method(JsRef idobj, JsRef idkey, JsRef idval);

/**
 * Call `obj.delete(key)`. Javascript standard is that `delete` returns `false`
 * to indicate an error condition, if `false` is returned we return `-1` to
 * indicate the error.
 */
errcode
hiwire_call_delete_method(JsRef idobj, JsRef idkey);

/**
 * Check whether the object is a PyProxy.
 */
bool
hiwire_is_pyproxy(JsRef idobj);

/**
 * Check if the object is a function.
 */
bool
hiwire_is_function(JsRef idobj);

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
 * Returns: New reference to Javascript promise
 */
JsRef
hiwire_resolve_promise(JsRef idobj);

/**
 * Gets the string representation of an object by calling `toString`.
 *
 * Returns: New reference to Javascript string
 */
JsRef
hiwire_to_string(JsRef idobj);

/**
 * Gets the `typeof` string for a value.
 *
 * Returns: New reference to Javascript string
 */
JsRef
hiwire_typeof(JsRef idobj);

/**
 * Gets `value.constructor.name`.
 *
 * Returns: New reference to Javascript string
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
 * Check if `typeof obj.next === "function"`
 */
JsRef
hiwire_is_iterator(JsRef idobj);

/**
 * Calls the `next` function on an iterator.
 *
 * Returns -1 if an error occurs. Otherwise, `next` should return an object with
 * `value` and `done` fields. We store `value` into the argument `result` and
 * return `done`.
 */
int
hiwire_next(JsRef idobj, JsRef* result);

/**
 * Check if `typeof obj[Symbol.iterator] === "function"`
 */
JsRef
hiwire_is_iterable(JsRef idobj);

/**
 * Returns the iterator associated with the given object, if any.
 */
JsRef
hiwire_get_iterator(JsRef idobj);

/**
 * Returns `Object.entries(obj)`
 */
JsRef
hiwire_object_entries(JsRef idobj);

/**
 * Returns `Object.keys(obj)`
 */
JsRef
hiwire_object_keys(JsRef idobj);

/**
 * Returns `Object.values(obj)`
 */
JsRef
hiwire_object_values(JsRef idobj);

/**
 * Returns 1 if the value is a typedarray.
 */
bool
hiwire_is_typedarray(JsRef idobj);

/**
 * Returns 1 if the value is a typedarray whose buffer is part of the WASM heap.
 */
bool
hiwire_is_on_wasm_heap(JsRef idobj);

/**
 * Returns the value of `obj.byteLength`.
 *
 * There is no error checking. Caller must ensure that hiwire_is_typedarray is
 * true. If these conditions are not met, returns `0`.
 */
int
hiwire_get_byteLength(JsRef idobj);

/**
 * Returns the value of obj.byteOffset.
 *
 * There is no error checking. Caller must ensure that hiwire_is_typedarray is
 * true and hiwire_is_on_wasm_heap is true. If these conditions are not met,
 * returns `0`.
 */
int
hiwire_get_byteOffset(JsRef idobj);

/**
 * Copies the buffer contents of a given typed array or buffer into the memory
 * at ptr.
 */
errcode
hiwire_copy_to_ptr(JsRef idobj, void* ptr);

/**
 * Get a data type identifier for a given typedarray.
 */
errcode
hiwire_get_dtype(JsRef idobj, char** format_ptr, Py_ssize_t* size_ptr);

/**
 * Get a subarray from a TypedArray
 */
JsRef
hiwire_subarray(JsRef idarr, int start, int end);

/**
 * Create a new Map.
 */
JsRef
JsMap_New();

/**
 * Does map.set(key, value).
 */
errcode
JsMap_Set(JsRef mapid, JsRef keyid, JsRef valueid);

/**
 * Create a new Set.
 */
JsRef
JsSet_New();

/**
 * Does set.add(key).
 */
errcode
JsSet_Add(JsRef mapid, JsRef keyid);

#endif /* HIWIRE_H */
