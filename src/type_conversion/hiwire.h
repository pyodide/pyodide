#ifndef HIWIRE_H
#define HIWIRE_H
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

// Define special ids for singleton constants. These must be negative to
// avoid being reused for other values.
#define Js_ERROR ((JsRef)(-1))
#define Js_UNDEFINED ((JsRef)(-2))
#define Js_TRUE ((JsRef)(-3))
#define Js_FALSE ((JsRef)(-4))
#define Js_NULL ((JsRef)(-5))

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
 * Decrease the reference count on an object.
 */
void
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
 * Create a new Javascript Uint8ClampedArray, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_bytes(char* ptr, int len);

/**
 * Create a new Javascript Int8Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_int8array(i8* ptr, int len);

/**
 * Create a new Javascript Uint8Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_uint8array(u8* ptr, int len);

/**
 * Create a new Javascript Int16Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_int16array(i16* ptr, int len);

/**
 * Create a new Javascript Uint16Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_uint16array(u16* ptr, int len);

/**
 * Create a new Javascript Int32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_int32array(i32* ptr, int len);

/**
 * Create a new Javascript Uint32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_uint32array(u32* ptr, int len);

/**
 * Create a new Javascript Float32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_float32array(f32* ptr, int len);

/**
 * Create a new Javascript Float64Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
JsRef
hiwire_float64array(f64* ptr, int len);

/**
 * Create a new Javascript undefined value.
 *
 * Returns: "New" reference
 */
JsRef
hiwire_undefined();

/**
 * Create a new Javascript null value.
 *
 * Returns: "New" reference
 */
JsRef
hiwire_null();

/**
 * Create a new Javascript true value.
 *
 * Returns: "New" reference
 */
JsRef
hiwire_true();

/**
 * Create a new Javascript false value.
 *
 * Returns: "New" reference
 */
JsRef
hiwire_false();

/**
 * Create a new Javascript boolean value.
 * Return value is true if boolean != 0, false if boolean == 0.
 *
 * Returns: "New" reference
 */
JsRef
hiwire_bool(bool boolean);

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
void
hiwire_push_array(JsRef idobj, JsRef idval);

/**
 * Create a new Javascript object.
 *
 * Returns: New reference
 */
JsRef
hiwire_object();

/**
 * Add a new key/value pair to a Javascript object.
 *
 * If the user no longer needs the key or value outside of the object, it is the
 * user's responsibility to decref them.
 */
void
hiwire_push_object_pair(JsRef idobj, JsRef idkey, JsRef idval);

/**
 * Throws a new Error object with the given message.
 *
 * The message is conventionally a Javascript string, but that is not required.
 * TODO: should be hiwire_set_error.
 */
void
hiwire_throw_error(JsRef idmsg);

/**
 * Get a Javascript object from the global namespace, i.e. window.
 *
 * Returns: New reference
 */
JsRef
hiwire_get_global(const char* ptrname);

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
void
hiwire_set_member_string(JsRef idobj, const char* ptrname, JsRef idval);

/**
 * Delete an object member by string.
 *
 */
void
hiwire_delete_member_string(JsRef idobj, const char* ptrname);

/**
 * Get an object member by integer.
 *
 * The integer is a C integer, not an id reference to a Javascript integer.
 *
 * Returns: New reference
 */
JsRef
hiwire_get_member_int(JsRef idobj, int idx);

/**
 * Set an object member by integer.
 *
 * The integer is a C integer, not an id reference to a Javascript integer.
 *
 */
void
hiwire_set_member_int(JsRef idobj, int idx, JsRef idval);

/**
 * Get an object member by object.
 *
 * Returns: New reference
 */
JsRef
hiwire_get_member_obj(JsRef idobj, JsRef ididx);

/**
 * Set an object member by object.
 *
 */
void
hiwire_set_member_obj(JsRef idobj, JsRef ididx, JsRef idval);

/**
 * Delete an object member by object.
 *
 */
void
hiwire_delete_member_obj(JsRef idobj, JsRef ididx);

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
 * Returns: New reference
 */
JsRef
hiwire_call(JsRef idobj, JsRef idargs);

/**
 * Call a member function.
 *
 * ptrname is the member name, as a char * to null-terminated UTF8.
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
JsRef
hiwire_call_member(JsRef idobj, const char* ptrname, JsRef idargs);

/**
 * Calls the constructor of a class object.
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
JsRef
hiwire_new(JsRef idobj, JsRef idargs);

/**
 * Returns the value of the `length` member on a Javascript object.
 *
 * Returns: C int
 */
int
hiwire_get_length(JsRef idobj);

/**
 * Returns the boolean value of a Javascript object.
 *
 * Returns: C int
 */
bool
hiwire_get_bool(JsRef idobj);

/**
 * Returns 1 if the object is a function.
 *
 * Returns: C int
 */
bool
hiwire_is_function(JsRef idobj);

/**
 * Gets the string representation of an object by calling `toString`.
 *
 * Returns: New reference to Javascript string
 */
JsRef
hiwire_to_string(JsRef idobj);

/**
 * Gets the "typeof" string for a value.
 *
 * Returns: New reference to Javascript string
 */
JsRef
hiwire_typeof(JsRef idobj);

/**
 * Gets "value.constructor.name".
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
 * Calls the `next` function on an iterator.
 *
 * Returns: Js_ERROR if `next` function is undefined.
 */
JsRef
hiwire_next(JsRef idobj);

/**
 * Returns the iterator associated with the given object, if any.
 */
JsRef
hiwire_get_iterator(JsRef idobj);

/**
 * Returns 1 if the value is non-zero.
 *
 */
bool
hiwire_nonzero(JsRef idobj);

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
 * Returns the value of obj.byteLength.
 *
 * There is no error checking. Caller must ensure that hiwire_is_typedarray is
 * true.
 */
int
hiwire_get_byteLength(JsRef idobj);

/**
 * Returns the value of obj.byteOffset.
 *
 * There is no error checking. Caller must ensure that hiwire_is_typedarray is
 * true and hiwire_is_on_wasm_heap is true.
 */
int
hiwire_get_byteOffset(JsRef idobj);

/**
 * Copies the buffer contents of a given typed array or buffer into the memory
 * at ptr.
 */
void
hiwire_copy_to_ptr(JsRef idobj, void* ptr);

/**
 * Get a data type identifier for a given typedarray.
 */
void
hiwire_get_dtype(JsRef idobj, char** format_ptr, Py_ssize_t* size_ptr);

/**
 * Get a subarray from a TypedArray
 */
JsRef
hiwire_subarray(JsRef idarr, int start, int end);

#endif /* HIWIRE_H */
