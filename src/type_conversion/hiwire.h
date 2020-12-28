#ifndef HIWIRE_H
#define HIWIRE_H
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

// HwObject is a NewType of int.
// I checked and
//  alignof(HwObject) = alignof(int) = 4
//  sizeof(HwObject) = sizeof(int) = 4
// Just to be extra future proof, I added assertions about this to the begining
// of main.c So we are all good for using HwObject as a newtype for int. I also
// added
//  -Werror=int-conversion -Werror=incompatible-pointer-types
// to the compile flags, so that no implicit casts will happen between HwObject
// and any other type.
struct _HwObjectStruct
{};

typedef struct _HwObjectStruct* HwObject;

// Define special ids for singleton constants. These must be negative to
// avoid being reused for other values.
#define HW_ERROR ((HwObject)(-1))
#define HW_UNDEFINED ((HwObject)(-2))
#define HW_TRUE ((HwObject)(-3))
#define HW_FALSE ((HwObject)(-4))
#define HW_NULL ((HwObject)(-5))

/**
 * Initialize the variables and functions required for hiwire.
 */
void
hiwire_setup();

/**
 * Increase the reference count on an object.
 *
 * Returns: The new reference
 */
HwObject
hiwire_incref(HwObject idval);

/**
 * Decrease the reference count on an object.
 */
void
hiwire_decref(HwObject idval);

/**
 * Create a new Javascript integer with the given value.
 *
 * Returns: New reference
 */
HwObject
hiwire_int(int val);

/**
 * Create a new Javascript float with the given value.
 *
 * Returns: New reference
 */
HwObject
hiwire_double(double val);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS4 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_string_ucs4(const char* ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS2 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_string_ucs2(const char* ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS1 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_string_ucs1(const char* ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a null-terminated buffer
 * containing UTF8. The string data itself is copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_string_utf8(const char* ptr);

/**
 * Create a new Javascript string, given a pointer to a null-terminated buffer
 * containing ascii (well, technically latin-1). The string data itself is
 * copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_string_ascii(const char* ptr);

/**
 * Create a new Javascript Uint8ClampedArray, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_bytes(char* ptr, int len);

/**
 * Create a new Javascript Int8Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_int8array(i8* ptr, int len);

/**
 * Create a new Javascript Uint8Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_uint8array(u8* ptr, int len);

/**
 * Create a new Javascript Int16Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_int16array(i16* ptr, int len);

/**
 * Create a new Javascript Uint16Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_uint16array(u16* ptr, int len);

/**
 * Create a new Javascript Int32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_int32array(i32* ptr, int len);

/**
 * Create a new Javascript Uint32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_uint32array(u32* ptr, int len);

/**
 * Create a new Javascript Float32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_float32array(f32* ptr, int len);

/**
 * Create a new Javascript Float64Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
HwObject
hiwire_float64array(f64* ptr, int len);

/**
 * Create a new Javascript undefined value.
 *
 * Returns: "New" reference
 */
HwObject
hiwire_undefined();

/**
 * Create a new Javascript null value.
 *
 * Returns: "New" reference
 */
HwObject
hiwire_null();

/**
 * Create a new Javascript true value.
 *
 * Returns: "New" reference
 */
HwObject
hiwire_true();

/**
 * Create a new Javascript false value.
 *
 * Returns: "New" reference
 */
HwObject
hiwire_false();

/**
 * Create a new Javascript boolean value.
 * Return value is true if boolean != 0, false if boolean == 0.
 *
 * Returns: "New" reference
 */
HwObject
hiwire_bool(bool boolean);

/**
 * Create a new Javascript Array.
 *
 * Returns: New reference
 */
HwObject
hiwire_array();

/**
 * Push a value to the end of a Javascript array.
 *
 * If the user no longer needs the value outside of the array, it is the user's
 * responsibility to decref it.
 */
void
hiwire_push_array(HwObject idobj, HwObject idval);

/**
 * Create a new Javascript object.
 *
 * Returns: New reference
 */
HwObject
hiwire_object();

/**
 * Add a new key/value pair to a Javascript object.
 *
 * If the user no longer needs the key or value outside of the object, it is the
 * user's responsibility to decref them.
 */
void
hiwire_push_object_pair(HwObject idobj, HwObject idkey, HwObject idval);

/**
 * Throws a new Error object with the given message.
 *
 * The message is conventionally a Javascript string, but that is not required.
 */
void
hiwire_throw_error(HwObject idmsg);

/**
 * Get a Javascript object from the global namespace, i.e. window.
 *
 * Returns: New reference
 */
HwObject
hiwire_get_global(const char* ptrname);

/**
 * Get an object member by string.
 *
 *
 * Returns: New reference
 */
HwObject
hiwire_get_member_string(HwObject idobj, const char* ptrname);

/**
 * Set an object member by string.
 */
void
hiwire_set_member_string(HwObject idobj, const char* ptrname, HwObject idval);

/**
 * Delete an object member by string.
 *
 */
void
hiwire_delete_member_string(HwObject idobj, const char* ptrname);

/**
 * Get an object member by integer.
 *
 * The integer is a C integer, not an id reference to a Javascript integer.
 *
 * Returns: New reference
 */
HwObject
hiwire_get_member_int(HwObject idobj, int idx);

/**
 * Set an object member by integer.
 *
 * The integer is a C integer, not an id reference to a Javascript integer.
 *
 */
void
hiwire_set_member_int(HwObject idobj, int idx, HwObject idval);

/**
 * Get an object member by object.
 *
 * Returns: New reference
 */
HwObject
hiwire_get_member_obj(HwObject idobj, HwObject ididx);

/**
 * Set an object member by object.
 *
 */
void
hiwire_set_member_obj(HwObject idobj, HwObject ididx, HwObject idval);

/**
 * Delete an object member by object.
 *
 */
void
hiwire_delete_member_obj(HwObject idobj, HwObject ididx);

/**
 * Get the methods on an object, both on itself and what it inherits.
 *
 */
HwObject
hiwire_dir(HwObject idobj);

/**
 * Call a function
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
HwObject
hiwire_call(HwObject idobj, HwObject idargs);

/**
 * Call a member function.
 *
 * ptrname is the member name, as a char * to null-terminated UTF8.
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
HwObject
hiwire_call_member(HwObject idobj, const char* ptrname, HwObject idargs);

/**
 * Calls the constructor of a class object.
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
HwObject
hiwire_new(HwObject idobj, HwObject idargs);

/**
 * Returns the value of the `length` member on a Javascript object.
 *
 * Returns: C int
 */
bool
hiwire_get_length(HwObject idobj);

/**
 * Returns the boolean value of a Javascript object.
 *
 * Returns: C int
 */
bool
hiwire_get_bool(HwObject idobj);

/**
 * Returns 1 if the object is a function.
 *
 * Returns: C int
 */
bool
hiwire_is_function(HwObject idobj);

/**
 * Gets the string representation of an object by calling `toString`.
 *
 * Returns: New reference to Javascript string
 */
HwObject
hiwire_to_string(HwObject idobj);

/**
 * Gets the "typeof" string for a value.
 *
 * Returns: New reference to Javascript string
 */
HwObject
hiwire_typeof(HwObject idobj);

/**
 * Returns non-zero if a < b.
 */
bool
hiwire_less_than(HwObject ida, HwObject idb);

/**
 * Returns non-zero if a <= b.
 */
bool
hiwire_less_than_equal(HwObject ida, HwObject idb);

/**
 * Returns non-zero if a == b.
 */
bool
hiwire_equal(HwObject ida, HwObject idb);

/**
 * Returns non-zero if a != b.
 */
bool
hiwire_not_equal(HwObject idx, HwObject idb);

/**
 * Returns non-zero if a > b.
 */
bool
hiwire_greater_than(HwObject ida, HwObject idb);

/**
 * Returns non-zero if a >= b.
 */
bool
hiwire_greater_than_equal(HwObject ida, HwObject idb);

/**
 * Calls the `next` function on an iterator.
 *
 * Returns: HW_ERROR if `next` function is undefined.
 */
HwObject
hiwire_next(HwObject idobj);

/**
 * Returns the iterator associated with the given object, if any.
 */
HwObject
hiwire_get_iterator(HwObject idobj);

/**
 * Returns 1 if the value is non-zero.
 *
 */
bool
hiwire_nonzero(HwObject idobj);

/**
 * Returns 1 if the value is a typedarray.
 */
bool
hiwire_is_typedarray(HwObject idobj);

/**
 * Returns 1 if the value is a typedarray whose buffer is part of the WASM heap.
 */
bool
hiwire_is_on_wasm_heap(HwObject idobj);

/**
 * Returns the value of obj.byteLength.
 *
 * There is no error checking. Caller must ensure that hiwire_is_typedarray is
 * true.
 */
int
hiwire_get_byteLength(HwObject idobj);

/**
 * Returns the value of obj.byteOffset.
 *
 * There is no error checking. Caller must ensure that hiwire_is_typedarray is
 * true and hiwire_is_on_wasm_heap is true.
 */
int
hiwire_get_byteOffset(HwObject idobj);

/**
 * Copies the buffer contents of a given typed array or buffer into the memory
 * at ptr.
 */
void
hiwire_copy_to_ptr(HwObject idobj, int ptr);

#define INT8_TYPE 1
#define UINT8_TYPE 2
#define UINT8CLAMPED_TYPE 3
#define INT16_TYPE 4
#define UINT16_TYPE 5
#define INT32_TYPE 6
#define UINT32_TYPE 7
#define FLOAT32_TYPE 8
#define FLOAT64_TYPE 9

/**
 * Get a data type identifier for a given typedarray.
 *
 * It will be one of INT8_TYPE, UINT8_TYPE, UINT8CLAMPED_TYPE, INT16_TYPE,
 * UINT16_TYPE, INT32_TYPE, UINT32_TYPE, FLOAT32_TYPE, FLOAT64_TYPE.
 */
int
hiwire_get_dtype(HwObject idobj);

/**
 * Get a subarray from a TypedArray
 */
HwObject
hiwire_subarray(HwObject idarr, int start, int end);

#endif /* HIWIRE_H */
