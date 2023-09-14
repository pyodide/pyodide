#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"
#include "jsmemops.h"

#define ERROR_REF (0)
#define ERROR_NUM (-1)

#define HIWIRE_INIT_CONSTS()                                                   \
  HIWIRE_INIT_CONST(UNDEFINED, undefined, 4);                                  \
  HIWIRE_INIT_CONST(JSNULL, null, 8);                                          \
  HIWIRE_INIT_CONST(TRUE, true, 12);                                           \
  HIWIRE_INIT_CONST(FALSE, false, 16)

// we use HIWIRE_INIT_CONSTS once in C and once inside JS with different
// definitions of HIWIRE_INIT_CONST to ensure everything lines up properly
// C definition:
#define HIWIRE_INIT_CONST(hiwire_attr, js_value, id)                           \
  const JsRef Js_##js_value = ((JsRef)(id));

HIWIRE_INIT_CONSTS();

// JS definition:
#undef HIWIRE_INIT_CONST
#define HIWIRE_INIT_CONST(hiwire_attr, js_value, id)                           \
  Hiwire.hiwire_attr = DEREF_U8(_Js_##js_value, 0);                            \
  _hiwire.immortals.push(js_value);                                            \
  _hiwire.obj_to_key.set(js_value, Hiwire.hiwire_attr);

// clang-format off
// JsRefs are:
// * heap             if they are odd,
// * immortal         if they are divisible by 4
// * stack references if they are congruent to 2 mod 4
//
// Note that "NULL" is immortal which is important.
//
// Both immortal and stack indexes are converted to id by bitshifting right by
// two to remove the lower order bits which indicate the reference type.
#define IS_IMMORTAL(idval) (((idval) & 3) === 0)
#define IMMORTAL_REF_TO_INDEX(idval) ((idval) >> 2)
#define IMMORTAL_INDEX_TO_REF(idval) ((idval) << 2)

#define IS_STACK(idval) (((idval) & 3) === 2)
#define STACK_REF_TO_INDEX(idval) ((idval) >> 2)
#define STACK_INDEX_TO_REF(index) (((index) << 2) | 2)

// For when the return value would be Option<JsRef>
// we use the largest possible immortal reference so that `get_value` on it will
// always raise an error.
const JsRef Js_novalue = ((JsRef)(2147483644));


// Heap slotmap layout macros

// The idea of a slotmap is that we use a list for storage. we use the empty
// slots in the list to maintain a linked list of freed indices in the same
// place as the values. This means that the next slot we assign is always the
// most recently freed. This leads to the possibility of masking use after free
// errors, since a recently freed reference will likely point to a valid but
// different object. To deal with this, we include as part of the reference a 5
// bit version for each slot. Only if the same slot is freed and reassigned 32
// times can the two references be the same. The references look as follows:
//
//   [version (5 bits)][index (25 bits)]1
//
// The highest order 5 bits are the version, the middle 25 bits are the index,
// and the least order bit indicates that it is a heap reference. Since we have
// 25 bits for the index, we can store up to 2^25 = 33,554,432 distinct objects.
// For each slot we associate an 32 bit "info" integer, which we store as part
// of the slotmap state. So references, occupied slot info, and unoccupied slot
// info all look like:
//
//  [version (5 bits)][multipurpose field (25 bits)][1 bit]
//
// The least significant bit is set in the references to indicate that they are
// heap references. The least significant bit is set in the info if the slot is
// occupied and unset if the slot is unoccupied.
//
// In a reference, the mulipurpose field contains the slot index.
//
//          reference: [version (5 bits)][index (25 bits)]1
//
// If a slot is unoccupied, the multipurpose field of the slotInfo contains the
// index of the next free slot in the free list or zero if this is the last free
// slot (for this reason, we do not use slot 0).
//
//    unoccupied slot: [version (5 bits)][next free index (25 bits)]0
//
// If a slot is occupied, the multipurpose field of the slotInfo contains a 24
// bit reference count and an IS_DEDUPLICATED bit.
//
//      occupied slot: [version (5 bits)][refcount (24 bits)][IS_DEDUPLICATED bit]1
//
// References used by JsProxies are deduplicated which makes allocating/freeing
// them more expensive.


#define VERSION_SHIFT 26 // 1 occupied bit, 25 bits of index/nextfree/refcount, then the version
#define INDEX_MASK            0x03FFFFFE // mask for index/nextfree
#define REFCOUNT_MASK         0x03FFFFFC // mask for refcount
#define VERSION_OCCUPIED_MASK 0xFc000001 // mask for version and occupied bit
#define VERSION_MASK          0xFc000000 // mask for version
#define OCCUPIED_BIT 1                   // occupied bit mask
#define DEDUPLICATED_BIT 2               // is it deduplicated? (used for JsRefs)
#define REFCOUNT_INTERVAL 4              // The refcount starts after OCCUPIED_BIT and DEDUPLICATED_BIT
#define NEW_INFO_FLAGS 5                 // REFCOUNT_INTERVAL | OCCUPIED_BIT

// Check that the constants are internally consistent
_Static_assert(INDEX_MASK == ((1 << VERSION_SHIFT) - 2), "Oops!");
_Static_assert((REFCOUNT_MASK | DEDUPLICATED_BIT) == INDEX_MASK, "Oops!");
_Static_assert(VERSION_OCCUPIED_MASK == (~INDEX_MASK), "Oops!");
_Static_assert(VERSION_OCCUPIED_MASK == (VERSION_MASK | OCCUPIED_BIT), "Oops!");
_Static_assert(NEW_INFO_FLAGS == (REFCOUNT_INTERVAL | OCCUPIED_BIT), "Oops");

#define HEAP_REF_TO_INDEX(ref) (((ref) & INDEX_MASK) >> 1)
#define HEAP_INFO_TO_NEXTFREE(info) HEAP_REF_TO_INDEX(info)

// The ref is always odd so this is truthy if info is even (meaning unoccupied)
// or info has a different version than ref. Masking removes the bits that form
// the index in the reference and the refcount/next free index in the info.
#define HEAP_REF_IS_OUT_OF_DATE(ref, info) \
  (((ref) ^ (info)) & VERSION_OCCUPIED_MASK)

#define HEAP_IS_REFCNT_ZERO(info) (!((info) & REFCOUNT_MASK))
#define HEAP_IS_DEDUPLICATED(info) ((info) & DEDUPLICATED_BIT)

#define HEAP_INCREF(info) info += REFCOUNT_INTERVAL
#define HEAP_DECREF(info) info -= REFCOUNT_INTERVAL

// increment the version in info.
#define _NEXT_VERSION(info) (info + (1 << VERSION_SHIFT))
// assemble version, field, and occupied
#define _NEW_INFO(version, field_and_flag) \
  (((version) & VERSION_MASK) | (field_and_flag))

// make a new reference with the same version as info and the given index.
#define HEAP_NEW_REF(index, info) _NEW_INFO(info, ((index) << 1) | 1)
// new occupied info: same version as argument info, NEW_INFO_FLAGS says occupied with refcount 1
#define HEAP_NEW_OCCUPIED_INFO(info) _NEW_INFO(info, NEW_INFO_FLAGS)
// new unoccupied info, increment version and nextfree in the field
#define FREE_LIST_INFO(info, nextfree) _NEW_INFO(_NEXT_VERSION(info), (nextfree) << 1)

// clang-format on

JsRef
hiwire_from_bool(bool boolean)
{
  return boolean ? Js_true : Js_false;
}

// clang-format off
EM_JS(bool, hiwire_to_bool, (JsRef val), {
  return !!Hiwire.get_value(val);
});
// clang-format on

#ifdef DEBUG_F
bool tracerefs;

#define TRACEREFS(args...)                                                     \
  if (DEREF_U8(_tracerefs, 0)) {                                               \
    console.warn(args);                                                        \
  }

#define DEBUG_INIT(cb) (cb)()

#else

#define TRACEREFS(args...)
#define DEBUG_INIT(cb)

#endif

#include <include_js_file.h>

#include "hiwire.js"

EM_JS(JsRef WARN_UNUSED, hiwire_incref, (JsRef idval), {
  return Hiwire.incref(idval);
});

EM_JS(JsRef WARN_UNUSED, hiwire_incref_deduplicate, (JsRef idval), {
  return Hiwire.incref_deduplicate(idval);
});

// clang-format off
EM_JS(void, hiwire_decref, (JsRef idval), {
  Hiwire.decref(idval);
});
// clang-format on

// clang-format off
EM_JS_REF(JsRef, hiwire_int, (int val), {
  return Hiwire.new_stack(val);
});
// clang-format on

// clang-format off
EM_JS_REF(JsRef,
hiwire_int_from_digits, (const unsigned int* digits, size_t ndigits), {
  let result = BigInt(0);
  for (let i = 0; i < ndigits; i++) {
    result += BigInt(DEREF_U32(digits, i)) << BigInt(32 * i);
  }
  result += BigInt(DEREF_U32(digits, ndigits - 1) & 0x80000000)
            << BigInt(1 + 32 * (ndigits - 1));
  if (-Number.MAX_SAFE_INTEGER < result && result < Number.MAX_SAFE_INTEGER) {
    result = Number(result);
  }
  return Hiwire.new_stack(result);
})
// clang-format on

EM_JS_REF(JsRef, hiwire_double, (double val), {
  return Hiwire.new_stack(val);
});

EM_JS_REF(JsRef, hiwire_string_utf8, (const char* ptr), {
  return Hiwire.new_stack(UTF8ToString(ptr));
});

EM_JS(void _Py_NO_RETURN, hiwire_throw_error, (JsRef iderr), {
  throw Hiwire.pop_value(iderr);
});

static JsRef
convert_va_args(va_list args)
{
  JsRef idargs = JsArray_New();
  while (true) {
    JsRef idarg = va_arg(args, JsRef);
    if (idarg == NULL) {
      break;
    }
    JsArray_Push_unchecked(idargs, idarg);
  }
  va_end(args);
  return idargs;
}

EM_JS_REF(JsRef, hiwire_call, (JsRef idfunc, JsRef idargs), {
  let jsfunc = Hiwire.get_value(idfunc);
  let jsargs = Hiwire.get_value(idargs);
  return Hiwire.new_value(jsfunc(... jsargs));
});

JsRef
hiwire_call_va(JsRef idobj, ...)
{
  va_list args;
  va_start(args, idobj);
  JsRef idargs = convert_va_args(args);
  JsRef idresult = hiwire_call(idobj, idargs);
  hiwire_decref(idargs);
  return idresult;
}

EM_JS_REF(JsRef, hiwire_call_OneArg, (JsRef idfunc, JsRef idarg), {
  let jsfunc = Hiwire.get_value(idfunc);
  let jsarg = Hiwire.get_value(idarg);
  return Hiwire.new_value(jsfunc(jsarg));
});

// clang-format off
EM_JS_REF(JsRef,
          hiwire_call_bound,
          (JsRef idfunc, JsRef idthis, JsRef idargs),
{
  let func = Hiwire.get_value(idfunc);
  let this_;
  if (idthis === 0) {
    this_ = null;
  } else {
    this_ = Hiwire.get_value(idthis);
  }
  let args = Hiwire.get_value(idargs);
  return Hiwire.new_value(func.apply(this_, args));
});
// clang-format on

EM_JS_BOOL(bool, hiwire_HasMethod, (JsRef obj_id, JsRef name), {
  // clang-format off
  let obj = Hiwire.get_value(obj_id);
  return obj && typeof obj[Hiwire.get_value(name)] === "function";
  // clang-format on
})

bool
hiwire_HasMethodId(JsRef obj, Js_Identifier* name)
{
  return hiwire_HasMethod(obj, JsString_FromId(name));
}

// clang-format off
EM_JS_REF(JsRef,
          hiwire_CallMethodString,
          (JsRef idobj, const char* name, JsRef idargs),
{
  let jsobj = Hiwire.get_value(idobj);
  let jsname = UTF8ToString(name);
  let jsargs = Hiwire.get_value(idargs);
  return Hiwire.new_value(jsobj[jsname](...jsargs));
});
// clang-format on

EM_JS_REF(JsRef, hiwire_CallMethod, (JsRef idobj, JsRef name, JsRef idargs), {
  let jsobj = Hiwire.get_value(idobj);
  let jsname = Hiwire.get_value(name);
  let jsargs = Hiwire.get_value(idargs);
  return Hiwire.new_value(jsobj[jsname](... jsargs));
});

EM_JS_REF(JsRef, hiwire_CallMethod_NoArgs, (JsRef idobj, JsRef name), {
  let jsobj = Hiwire.get_value(idobj);
  let jsname = Hiwire.get_value(name);
  return Hiwire.new_value(jsobj[jsname]());
});

// clang-format off
EM_JS_REF(
JsRef,
hiwire_CallMethod_OneArg,
(JsRef idobj, JsRef name, JsRef idarg),
{
  let jsobj = Hiwire.get_value(idobj);
  let jsname = Hiwire.get_value(name);
  let jsarg = Hiwire.get_value(idarg);
  return Hiwire.new_value(jsobj[jsname](jsarg));
});
// clang-format on

JsRef
hiwire_CallMethodId(JsRef idobj, Js_Identifier* name_id, JsRef idargs)
{
  JsRef name_ref = JsString_FromId(name_id);
  if (name_ref == NULL) {
    return NULL;
  }
  return hiwire_CallMethod(idobj, name_ref, idargs);
}

JsRef
hiwire_CallMethodString_va(JsRef idobj, const char* ptrname, ...)
{
  va_list args;
  va_start(args, ptrname);
  JsRef idargs = convert_va_args(args);
  JsRef idresult = hiwire_CallMethodString(idobj, ptrname, idargs);
  hiwire_decref(idargs);
  return idresult;
}

JsRef
hiwire_CallMethodId_va(JsRef idobj, Js_Identifier* name, ...)
{
  va_list args;
  va_start(args, name);
  JsRef idargs = convert_va_args(args);
  JsRef idresult = hiwire_CallMethodId(idobj, name, idargs);
  hiwire_decref(idargs);
  return idresult;
}

JsRef
hiwire_CallMethodId_NoArgs(JsRef obj, Js_Identifier* name)
{
  JsRef name_ref = JsString_FromId(name);
  if (name_ref == NULL) {
    return NULL;
  }
  return hiwire_CallMethod_NoArgs(obj, name_ref);
}

JsRef
hiwire_CallMethodId_OneArg(JsRef obj, Js_Identifier* name, JsRef arg)
{
  JsRef name_ref = JsString_FromId(name);
  if (name_ref == NULL) {
    return NULL;
  }
  return hiwire_CallMethod_OneArg(obj, name_ref, arg);
}

EM_JS_REF(JsRef, hiwire_construct, (JsRef idobj, JsRef idargs), {
  let jsobj = Hiwire.get_value(idobj);
  let jsargs = Hiwire.get_value(idargs);
  return Hiwire.new_value(Reflect.construct(jsobj, jsargs));
});

EM_JS_BOOL(bool, hiwire_has_length, (JsRef idobj), {
  let val = Hiwire.get_value(idobj);
  // clang-format off
  return (typeof val.size === "number") ||
         (typeof val.length === "number" && typeof val !== "function");
  // clang-format on
});

EM_JS_NUM(int, hiwire_get_length_helper, (JsRef idobj), {
  let val = Hiwire.get_value(idobj);
  // clang-format off
  let result;
  if (typeof val.size === "number") {
    result = val.size;
  } else if (typeof val.length === "number") {
    result = val.length;
  } else {
    return -2;
  }
  if(result < 0){
    return -3;
  }
  if(result > INT_MAX){
    return -4;
  }
  return result;
  // clang-format on
});

// Needed to render the length accurately when there is an error
EM_JS_REF(char*, hiwire_get_length_string, (JsRef idobj), {
  const val = Hiwire.get_value(idobj);
  let result;
  // clang-format off
  if (typeof val.size === "number") {
    result = val.size;
  } else if (typeof val.length === "number") {
    result = val.length;
  }
  // clang-format on
  return stringToNewUTF8(" " + result.toString())
})

int
hiwire_get_length(JsRef idobj)
{
  int result = hiwire_get_length_helper(idobj);
  if (result >= 0) {
    return result;
  }
  // Something went wrong. Case work:
  // * -1: Either `val.size` or `val.length` was a getter which managed to raise
  //    an error. Rude. (Also we don't defend against this in hiwire_has_length)
  // * -2: Doesn't have a length or size, or they aren't of type "number".
  //   But `hiwire_has_length` returned true? So it must have changed somehow.
  // * -3: Length was >= 2^{31}
  // * -4: Length was negative
  if (result == -2) {
    PyErr_SetString(PyExc_TypeError, "object does not have a valid length");
  }
  if (result == -1 || result == -2) {
    return -1;
  }

  char* length_as_string_alloc = hiwire_get_length_string(idobj);
  char* length_as_string = length_as_string_alloc;
  if (length_as_string == NULL) {
    // Really screwed up.
    length_as_string = "";
  }
  if (result == -3) {
    PyErr_Format(
      PyExc_ValueError, "length%s of object is negative", length_as_string);
  }
  if (result == -4) {
    PyErr_Format(PyExc_OverflowError,
                 "length%s of object is larger than INT_MAX (%d)",
                 length_as_string,
                 INT_MAX);
  }
  if (length_as_string_alloc != NULL) {
    free(length_as_string_alloc);
  }
  return -1;
}

EM_JS_BOOL(bool, hiwire_get_bool, (JsRef idobj), {
  let val = Hiwire.get_value(idobj);
  // clang-format off
  if (!val) {
    return false;
  }
  // We want to return false on container types with size 0.
  if (val.size === 0) {
    if(/HTML[A-Za-z]*Element/.test(getTypeTag(val))){
      // HTMLSelectElement and HTMLInputElement can have size 0 but we still
      // want to return true.
      return true;
    }
    // I think other things with a size are container types.
    return false;
  }
  if (val.length === 0 && JsArray_Check(idobj)) {
    return false;
  }
  if (val.byteLength === 0) {
    return false;
  }
  return true;
  // clang-format on
});

EM_JS_BOOL(bool, hiwire_is_function, (JsRef idobj), {
  // clang-format off
  return typeof Hiwire.get_value(idobj) === 'function';
  // clang-format on
});

EM_JS_BOOL(bool, hiwire_is_generator, (JsRef idobj), {
  // clang-format off
  return getTypeTag(Hiwire.get_value(idobj)) === "[object Generator]";
  // clang-format on
});

EM_JS_BOOL(bool, hiwire_is_async_generator, (JsRef idobj), {
  // clang-format off
  return getTypeTag(Hiwire.get_value(idobj)) === "[object AsyncGenerator]";
  // clang-format on
});

EM_JS_BOOL(bool, hiwire_is_comlink_proxy, (JsRef idobj), {
  let value = Hiwire.get_value(idobj);
  return !!(API.Comlink && value[API.Comlink.createEndpoint]);
});

EM_JS_BOOL(bool, hiwire_is_error, (JsRef idobj), {
  // From https://stackoverflow.com/a/45496068
  let value = Hiwire.get_value(idobj);
  // clang-format off
  return !!(value && typeof value.stack === "string" &&
            typeof value.message === "string");
  // clang-format on
});

EM_JS_BOOL(bool, hiwire_is_promise, (JsRef idobj), {
  // clang-format off
  let obj = Hiwire.get_value(idobj);
  return Hiwire.isPromise(obj);
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_resolve_promise, (JsRef idobj), {
  // clang-format off
  let obj = Hiwire.get_value(idobj);
  let result = Promise.resolve(obj);
  return Hiwire.new_value(result);
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_to_string, (JsRef idobj), {
  return Hiwire.new_value(Hiwire.get_value(idobj).toString());
});

EM_JS(JsRef, hiwire_typeof, (JsRef idobj), {
  return Hiwire.new_value(typeof Hiwire.get_value(idobj));
});

EM_JS_REF(char*, hiwire_constructor_name, (JsRef idobj), {
  return stringToNewUTF8(Hiwire.get_value(idobj).constructor.name);
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS_BOOL(bool, hiwire_##name, (JsRef ida, JsRef idb), {                    \
    return !!(Hiwire.get_value(ida) op Hiwire.get_value(idb));                 \
  })

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
// clang-format off
MAKE_OPERATOR(equal, ===);
MAKE_OPERATOR(not_equal, !==);
// clang-format on
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

EM_JS_REF(JsRef, hiwire_reversed_iterator, (JsRef idarray), {
  if (!Module._reversedIterator) {
    Module._reversedIterator = class ReversedIterator
    {
      constructor(array)
      {
        this._array = array;
        this._i = array.length - 1;
      }

      __length_hint__() { return this._array.length; }

      [Symbol.toStringTag]() { return "ReverseIterator"; }

      next()
      {
        const i = this._i;
        const a = this._array;
        const done = i < 0;
        const value = done ? undefined : a[i];
        this._i--;
        return { done, value };
      }
    };
  }
  let array = Hiwire.get_value(idarray);

  return Hiwire.new_value(new Module._reversedIterator(array));
})

EM_JS_NUM(errcode, hiwire_assign_to_ptr, (JsRef idobj, void* ptr), {
  let jsobj = Hiwire.get_value(idobj);
  Module.HEAPU8.set(API.typedArrayAsUint8Array(jsobj), ptr);
});

EM_JS_NUM(errcode, hiwire_assign_from_ptr, (JsRef idobj, void* ptr), {
  let jsobj = Hiwire.get_value(idobj);
  API.typedArrayAsUint8Array(jsobj).set(
    Module.HEAPU8.subarray(ptr, ptr + jsobj.byteLength));
});

EM_JS_NUM(errcode, hiwire_read_from_file, (JsRef idobj, int fd), {
  let jsobj = Hiwire.get_value(idobj);
  let uint8_buffer = API.typedArrayAsUint8Array(jsobj);
  let stream = Module.FS.streams[fd];
  Module.FS.read(stream, uint8_buffer, 0, uint8_buffer.byteLength);
});

EM_JS_NUM(errcode, hiwire_write_to_file, (JsRef idobj, int fd), {
  let jsobj = Hiwire.get_value(idobj);
  let uint8_buffer = API.typedArrayAsUint8Array(jsobj);
  let stream = Module.FS.streams[fd];
  Module.FS.write(stream, uint8_buffer, 0, uint8_buffer.byteLength);
});

EM_JS_NUM(errcode, hiwire_into_file, (JsRef idobj, int fd), {
  let jsobj = Hiwire.get_value(idobj);
  let uint8_buffer = API.typedArrayAsUint8Array(jsobj);
  let stream = Module.FS.streams[fd];
  // set canOwn param to true, leave position undefined.
  Module.FS.write(
    stream, uint8_buffer, 0, uint8_buffer.byteLength, undefined, true);
});

// clang-format off
EM_JS_UNCHECKED(
void,
hiwire_get_buffer_info, (JsRef idobj,
                         Py_ssize_t* byteLength_ptr,
                         char** format_ptr,
                         Py_ssize_t* size_ptr,
                         bool* checked_ptr),
{
  let jsobj = Hiwire.get_value(idobj);
  let byteLength = jsobj.byteLength;
  let [format_utf8, size, checked] = Module.get_buffer_datatype(jsobj);
  // Store results into arguments
  DEREF_U32(byteLength_ptr, 0) = byteLength;
  DEREF_U32(format_ptr, 0) = format_utf8;
  DEREF_U32(size_ptr, 0) = size;
  DEREF_U8(checked_ptr, 0) = checked;
});
// clang-format on

EM_JS_REF(JsRef, hiwire_subarray, (JsRef idarr, int start, int end), {
  let jsarr = Hiwire.get_value(idarr);
  let jssub = jsarr.subarray(start, end);
  return Hiwire.new_value(jssub);
});

// ==================== JsArray API  ====================

EM_JS_BOOL(bool, JsArray_Check, (JsRef idobj), {
  let obj = Hiwire.get_value(idobj);
  if (Array.isArray(obj)) {
    return true;
  }
  let typeTag = getTypeTag(obj);
  // We want to treat some standard array-like objects as Array.
  // clang-format off
  if(typeTag === "[object HTMLCollection]" || typeTag === "[object NodeList]"){
    // clang-format on
    return true;
  }
  // What if it's a TypedArray?
  // clang-format off
  if (ArrayBuffer.isView(obj) && obj.constructor.name !== "DataView") {
    // clang-format on
    return true;
  }
  return false;
});

// clang-format off
EM_JS_REF(JsRef, JsArray_New, (), {
  return Hiwire.new_value([]);
});
// clang-format on

EM_JS_NUM(errcode, JsArray_Push, (JsRef idarr, JsRef idval), {
  Hiwire.get_value(idarr).push(Hiwire.get_value(idval));
});

EM_JS(int, JsArray_Push_unchecked, (JsRef idarr, JsRef idval), {
  const arr = Hiwire.get_value(idarr);
  arr.push(Hiwire.get_value(idval));
  return arr.length - 1;
});

EM_JS_NUM(errcode, JsArray_Extend, (JsRef idarr, JsRef idvals), {
  Hiwire.get_value(idarr).push(... Hiwire.get_value(idvals));
});

EM_JS_REF(JsRef, JsArray_Get, (JsRef idobj, int idx), {
  let obj = Hiwire.get_value(idobj);
  let result = obj[idx];
  // clang-format off
  if (result === undefined && !(idx in obj)) {
    // clang-format on
    return ERROR_REF;
  }
  return Hiwire.new_value(result);
});

EM_JS_NUM(errcode, JsArray_Set, (JsRef idobj, int idx, JsRef idval), {
  Hiwire.get_value(idobj)[idx] = Hiwire.get_value(idval);
});

EM_JS_NUM(errcode, JsArray_Delete, (JsRef idobj, int idx), {
  let obj = Hiwire.get_value(idobj);
  // Weird edge case: allow deleting an empty entry, but we raise a key error if
  // access is attempted.
  if (idx < 0 || idx >= obj.length) {
    return ERROR_NUM;
  }
  obj.splice(idx, 1);
});

EM_JS_REF(JsRef, JsArray_Splice, (JsRef idobj, int idx), {
  let obj = Hiwire.get_value(idobj);
  // Weird edge case: allow deleting an empty entry, but we raise a key error if
  // access is attempted.
  if (idx < 0 || idx >= obj.length) {
    return 0;
  }
  return Hiwire.new_value(obj.splice(idx, 1));
});

// clang-format off
EM_JS_REF(JsRef,
JsArray_slice,
(JsRef idobj, int length, int start, int stop, int step),
{
  let obj = Hiwire.get_value(idobj);
  let result;
  if (step === 1) {
    result = obj.slice(start, stop);
  } else {
    result = Array.from({ length }, (_, i) => obj[start + i * step]);
  }
  return Hiwire.new_value(result);
});

EM_JS_NUM(errcode,
JsArray_slice_assign,
(JsRef idobj, int slicelength, int start, int stop, int step, int values_length, PyObject **values),
{
  let obj = Hiwire.get_value(idobj);
  let jsvalues = [];
  for(let i = 0; i < values_length; i++){
    let ref = _python2js(DEREF_U32(values, i));
    if(ref === 0){
      return -1;
    }
    jsvalues.push(Hiwire.pop_value(ref));
  }
  if (step === 1) {
    obj.splice(start, slicelength, ...jsvalues);
  } else {
    if(values !== 0) {
      for(let i = 0; i < slicelength; i ++){
        obj.splice(start + i * step, 1, jsvalues[i]);
      }
    } else {
      for(let i = slicelength - 1; i >= 0; i --){
        obj.splice(start + i * step, 1);
      }
    }
  }
});
// clang-format on

EM_JS_NUM(errcode, JsArray_Clear, (JsRef idobj), {
  let obj = Hiwire.get_value(idobj);
  obj.splice(0, obj.length);
})

EM_JS_NUM(JsRef, JsArray_ShallowCopy, (JsRef idobj), {
  const obj = Hiwire.get_value(idobj);
  const res = ("slice" in obj) ? obj.slice() : Array.from(obj);
  return Hiwire.new_value(res);
})

// ==================== JsObject API  ====================

// clang-format off
EM_JS_REF(JsRef, JsObject_New, (), {
  return Hiwire.new_value({});
});
// clang-format on

void
setReservedError(char* action, char* word)
{
  PyErr_Format(PyExc_AttributeError,
               "The string '%s' is a Python reserved word. To %s an attribute "
               "on a JS object called '%s' use '%s_'.",
               word,
               action,
               word,
               word);
}

EM_JS(bool, isReservedWord, (int word), {
  if (!Module.pythonReservedWords) {
    Module.pythonReservedWords = new Set([
      "False",  "await", "else",     "import", "pass",   "None",    "break",
      "except", "in",    "raise",    "True",   "class",  "finally", "is",
      "return", "and",   "continue", "for",    "lambda", "try",     "as",
      "def",    "from",  "nonlocal", "while",  "assert", "del",     "global",
      "not",    "with",  "async",    "elif",   "if",     "or",      "yield",
    ])
  }
  return Module.pythonReservedWords.has(word);
})

/**
 * action: a javascript string, one of get, set, or delete. For error reporting.
 * word: a javascript string, the property being accessed
 */
EM_JS(int, normalizeReservedWords, (int word), {
  // clang-format off
  // 1. if word is not a reserved word followed by 0 or more underscores, return
  //    it unchanged.
  const noTrailing_ = word.replace(/_*$/, "");
  if (!isReservedWord(noTrailing_)) {
    return word;
  }
  // 2. If there is at least one trailing underscore, return the word with a
  //    single underscore removed.
  if (noTrailing_ !== word) {
    return word.slice(0, -1);
  }
  // 3. If the word is exactly a reserved word, return it unchanged
  return word;
  // clang-format on
});

EM_JS_REF(JsRef, JsObject_GetString, (JsRef idobj, const char* ptrkey), {
  const jsobj = Hiwire.get_value(idobj);
  const jskey = normalizeReservedWords(UTF8ToString(ptrkey));
  const result = jsobj[jskey];
  // clang-format off
  if (result === undefined && !(jskey in jsobj)) {
    // clang-format on
    return ERROR_REF;
  }
  return Hiwire.new_value(result);
});

// clang-format off
EM_JS_NUM(errcode,
JsObject_SetString,
(JsRef idobj, const char* ptrkey, JsRef idval),
{
  let jsobj = Hiwire.get_value(idobj);
  let jskey = normalizeReservedWords(UTF8ToString(ptrkey));
  let jsval = Hiwire.get_value(idval);
  jsobj[jskey] = jsval;
});
// clang-format on

EM_JS_NUM(errcode, JsObject_DeleteString, (JsRef idobj, const char* ptrkey), {
  let jsobj = Hiwire.get_value(idobj);
  let jskey = normalizeReservedWords(UTF8ToString(ptrkey));
  delete jsobj[jskey];
});

EM_JS_REF(JsRef, JsObject_Dir, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  let result = [];
  do {
    // clang-format off
    const names = Object.getOwnPropertyNames(jsobj);
    result.push(...names.filter(
      s => {
        let c = s.charCodeAt(0);
        return c < 48 || c > 57; /* Filter out integer array indices */
      }
    )
    // If the word is a reserved word followed by 0 or more underscores, add an
    // extra underscore to reverse the transformation applied by normalizeReservedWords.
    .map(word => isReservedWord(word.replace(/_*$/, "")) ? word + "_" : word));
    // clang-format on
  } while (jsobj = Object.getPrototypeOf(jsobj));
  return Hiwire.new_value(result);
});

EM_JS_REF(JsRef, JsObject_Entries, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  return Hiwire.new_value(Object.entries(jsobj));
});

EM_JS_REF(JsRef, JsObject_Keys, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  return Hiwire.new_value(Object.keys(jsobj));
});

EM_JS_REF(JsRef, JsObject_Values, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  return Hiwire.new_value(Object.values(jsobj));
});

// ==================== JsString API  ====================

EM_JS_REF(JsRef, JsString_InternFromCString, (const char* str), {
  let jsstring = UTF8ToString(str);
  return Hiwire.intern_object(jsstring);
})

JsRef
JsString_FromId(Js_Identifier* id)
{
  if (!id->object) {
    id->object = JsString_InternFromCString(id->string);
  }
  return id->object;
}

// ==================== JsMap API  ====================

// clang-format off
EM_JS_REF(JsRef, JsMap_New, (), {
  return Hiwire.new_value(new Map());
})
// clang-format on

EM_JS_NUM(errcode, JsMap_Set, (JsRef mapid, JsRef keyid, JsRef valueid), {
  let map = Hiwire.get_value(mapid);
  let key = Hiwire.get_value(keyid);
  let value = Hiwire.get_value(valueid);
  map.set(key, value);
})

// ==================== JsSet API  ====================

// clang-format off
EM_JS_REF(JsRef, JsSet_New, (), {
  return Hiwire.new_value(new Set());
})
// clang-format on

EM_JS_NUM(errcode, JsSet_Add, (JsRef mapid, JsRef keyid), {
  let set = Hiwire.get_value(mapid);
  let key = Hiwire.get_value(keyid);
  set.add(key);
})
