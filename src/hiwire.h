#ifndef HIWIRE_H
#define HIWIRE_H

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

#define HW_ERROR -1

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
int
hiwire_incref(int idval);

/**
 * Decrease the reference count on an object.
 */
void
hiwire_decref(int idval);

/**
 * Create a new Javascript integer with the given value.
 *
 * Returns: New reference
 */
int
hiwire_int(int val);

/**
 * Create a new Javascript float with the given value.
 *
 * Returns: New reference
 */
int
hiwire_double(double val);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS4 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
int
hiwire_string_ucs4(int ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS2 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
int
hiwire_string_ucs2(int ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a buffer
 * containing UCS1 and a length. The string data itself is copied.
 *
 * Returns: New reference
 */
int
hiwire_string_ucs1(int ptr, int len);

/**
 * Create a new Javascript string, given a pointer to a null-terminated buffer
 * containing UTF8. The string data itself is copied.
 *
 * Returns: New reference
 */
int
hiwire_string_utf8(int ptr);

/**
 * Create a new Javascript string, given a pointer to a null-terminated buffer
 * containing ascii (well, technically latin-1). The string data itself is
 * copied.
 *
 * Returns: New reference
 */
int
hiwire_string_ascii(int ptr);

/**
 * Create a new Javascript Uint8ClampedArray, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_bytes(int ptr, int len);

/**
 * Create a new Javascript Int8Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_int8array(int ptr, int len);

/**
 * Create a new Javascript Uint8Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_uint8array(int ptr, int len);

/**
 * Create a new Javascript Int16Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_int16array(int ptr, int len);

/**
 * Create a new Javascript Uint16Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_uint16array(int ptr, int len);

/**
 * Create a new Javascript Int32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_int32array(int ptr, int len);

/**
 * Create a new Javascript Uint32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_uint32array(int ptr, int len);

/**
 * Create a new Javascript Float32Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_float32array(int ptr, int len);

/**
 * Create a new Javascript Float64Array, given a pointer to a buffer and a
 * length, in bytes.
 *
 * The array's data is not copied.
 *
 * Returns: New reference
 */
int
hiwire_float64array(int ptr, int len);

/**
 * Create a new Javascript undefined value.
 *
 * Returns: New reference
 */
int
hiwire_undefined();

/**
 * Create a new Javascript null value.
 *
 * Returns: New reference
 */
int
hiwire_null();

/**
 * Create a new Javascript true value.
 *
 * Returns: New reference
 */
int
hiwire_true();

/**
 * Create a new Javascript false value.
 *
 * Returns: New reference
 */
int
hiwire_false();

/**
 * Create a new Javascript Array.
 *
 * Returns: New reference
 */
int
hiwire_array();

/**
 * Push a value to the end of a Javascript array.
 *
 * If the user no longer needs the value outside of the array, it is the user's
 * responsibility to decref it.
 */
void
hiwire_push_array(int idobj, int idval);

/**
 * Create a new Javascript object.
 *
 * Returns: New reference
 */
int
hiwire_object();

/**
 * Add a new key/value pair to a Javascript object.
 *
 * If the user no longer needs the key or value outside of the object, it is the
 * user's responsibility to decref them.
 */
void
hiwire_push_object_pair(int idobj, int idkey, int idval);

/**
 * Throws a new Error object with the given message.
 *
 * The message is conventionally a Javascript string, but that is not required.
 */
void
hiwire_throw_error(int idmsg);

/**
 * Get a Javascript object from the global namespace, i.e. window.
 *
 * Returns: New reference
 */
int
hiwire_get_global(int ptrname);

/**
 * Get an object member by string.
 *
 * The string is a char* to null-terminated UTF8.
 *
 * Returns: New reference
 */
int
hiwire_get_member_string(int idobj, int ptrname);

/**
 * Set an object member by string.
 *
 * The string is a char* to null-terminated UTF8.
 */
void
hiwire_set_member_string(int idobj, int ptrname, int idval);

/**
 * Delete an object member by string.
 *
 * The string is a char* to null-terminated UTF8.
 */
void
hiwire_delete_member_string(int idobj, int ptrname);

/**
 * Get an object member by integer.
 *
 * The integer is a C integer, not an id reference to a Javascript integer.
 *
 * Returns: New reference
 */
int
hiwire_get_member_int(int idobj, int idx);

/**
 * Set an object member by integer.
 *
 * The integer is a C integer, not an id reference to a Javascript integer.
 *
 */
void
hiwire_set_member_int(int idobj, int idx, int idval);

/**
 * Get an object member by object.
 *
 * Returns: New reference
 */
int
hiwire_get_member_obj(int idobj, int ididx);

/**
 * Set an object member by object.
 *
 */
void
hiwire_set_member_obj(int idobj, int ididx, int idval);

/**
 * Delete an object member by object.
 *
 */
void
hiwire_delete_member_obj(int idobj, int ididx);

/**
 * Get the methods on an object, both on itself and what it inherits.
 *
 */
int
hiwire_dir(int idobj);

/**
 * Call a function
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
int
hiwire_call(int idobj, int idargs);

/**
 * Call a member function.
 *
 * ptrname is the member name, as a char * to null-terminated UTF8.
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
int
hiwire_call_member(int idobj, int ptrname, int idargs);

/**
 * Calls the constructor of a class object.
 *
 * idargs is a hiwire Array containing the arguments.
 *
 * Returns: New reference
 */
int
hiwire_new(int idobj, int idargs);

/**
 * Returns the value of the `length` member on a Javascript object.
 *
 * Returns: C int
 */
int
hiwire_get_length(int idobj);

/**
 * Returns the boolean value of a Javascript object.
 *
 * Returns: C int
 */
int
hiwire_get_bool(int idobj);

/**
 * Returns 1 if the object is a function.
 *
 * Returns: C int
 */
int
hiwire_is_function(int idobj);

/**
 * Gets the string representation of an object by calling `toString`.
 *
 * Returns: New reference to Javascript string
 */
int
hiwire_to_string(int idobj);

/**
 * Gets the "typeof" string for a value.
 *
 * Returns: New reference to Javascript string
 */
int
hiwire_typeof(int idobj);

/**
 * Returns non-zero if a < b.
 */
int
hiwire_less_than(int ida, int idb);

/**
 * Returns non-zero if a <= b.
 */
int
hiwire_less_than_equal(int ida, int idb);

/**
 * Returns non-zero if a == b.
 */
int
hiwire_equal(int ida, int idb);

/**
 * Returns non-zero if a != b.
 */
int
hiwire_not_equal(int idx, int idb);

/**
 * Returns non-zero if a > b.
 */
int
hiwire_greater_than(int ida, int idb);

/**
 * Returns non-zero if a >= b.
 */
int
hiwire_greater_than_equal(int ida, int idb);

/**
 * Calls the `next` function on an iterator.
 *
 * Returns: HW_ERROR if `next` function is undefined.
 */
int
hiwire_next(int idobj);

/**
 * Returns the iterator associated with the given object, if any.
 */
int
hiwire_get_iterator(int idobj);

/**
 * Returns 1 if the value is non-zero.
 *
 */
int
hiwire_nonzero(int idobj);

/**
 * Returns 1 if the value is a typedarray.
 */
int
hiwire_is_typedarray(int idobj);

/**
 * Returns 1 if the value is a typedarray whose buffer is part of the WASM heap.
 */
int
hiwire_is_on_wasm_heap(int idobj);

/**
 * Returns the value of obj.byteLength.
 *
 * There is no error checking. Caller must ensure that hiwire_is_typedarray is
 * true.
 */
int
hiwire_get_byteLength(int idobj);

/**
 * Returns the value of obj.byteOffset.
 *
 * There is no error checking. Caller must ensure that hiwire_is_typedarray is
 * true and hiwire_is_on_wasm_heap is true.
 */
int
hiwire_get_byteOffset(int idobj);

/**
 * Copies the buffer contents of a given typed array or buffer into the memory
 * at ptr.
 */
int
hiwire_copy_to_ptr(int idobj, int ptr);

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
hiwire_get_dtype(int idobj);

/**
 * Get a subarray from a TypedArray
 */
int
hiwire_subarray(int idarr, int start, int end);

#endif /* HIWIRE_H */
