#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"
#include "jsmemops.h"
#undef hiwire_incref

#define ERROR_REF (0)
#define ERROR_NUM (-1)

#ifdef DEBUG_F
int tracerefs = 0;
#endif

// For when the return value would be Option<JsRef>
// we use the largest possible immortal reference so that `get_value` on it will
// always raise an error.
const JsRef Js_novalue = ((JsRef)(2147483644));

#define HIWIRE_INIT_CONSTS()                                                   \
  HIWIRE_INIT_CONST(undefined)                                                 \
  HIWIRE_INIT_CONST(null)                                                      \
  HIWIRE_INIT_CONST(true)                                                      \
  HIWIRE_INIT_CONST(false)

// we use HIWIRE_INIT_CONSTS once in C and once inside JS with different
// definitions of HIWIRE_INIT_CONST to ensure everything lines up properly
// C definition:
#define HIWIRE_INIT_CONST(js_value)                                            \
  EMSCRIPTEN_KEEPALIVE const JsRef Js_##js_value;
HIWIRE_INIT_CONSTS();

#undef HIWIRE_INIT_CONST

#define HIWIRE_INIT_CONST(js_value)                                            \
  HEAP32[_Js_##js_value / 4] = _hiwire_intern(js_value);

EM_JS_NUM(int, hiwire_init_js, (void), {
  HIWIRE_INIT_CONSTS();
  // clang-format off
  Hiwire.new_value = _hiwire_new;
  Hiwire.new_stack = _hiwire_new;
  Hiwire.intern_object = _hiwire_intern;
  Hiwire.num_keys = _hiwire_num_refs;
  Hiwire.stack_length = () => 0;
  Hiwire.get_value = _hiwire_get;
  Hiwire.incref = (x) =>
  {
    _hiwire_incref(x);
    return x;
  };
  Hiwire.decref = _hiwire_decref;
  Hiwire.pop_value = _hiwire_pop;
  // clang-format on

  // This is factored out primarily for testing purposes.
  Hiwire.isPromise = function(obj)
  {
    try {
      // clang-format off
      return !!obj && typeof obj.then === "function";
      // clang-format on
    } catch (e) {
      return false;
    }
  };

  /**
   * Turn any ArrayBuffer view or ArrayBuffer into a Uint8Array.
   *
   * This respects slices: if the ArrayBuffer view is restricted to a slice of
   * the backing ArrayBuffer, we return a Uint8Array that shows the same slice.
   */
  API.typedArrayAsUint8Array = function(arg)
  {
    if (ArrayBuffer.isView(arg)) {
      return new Uint8Array(arg.buffer, arg.byteOffset, arg.byteLength);
    } else {
      return new Uint8Array(arg);
    }
  };

  {
    let dtypes_str =
      [ "b", "B", "h", "H", "i", "I", "f", "d" ].join(String.fromCharCode(0), );
    let dtypes_ptr = stringToNewUTF8(dtypes_str);
    let dtypes_map = {};
    for (let[idx, val] of Object.entries(dtypes_str)) {
      dtypes_map[val] = dtypes_ptr + Number(idx);
    }

    let buffer_datatype_map = new Map([
      [ "Int8Array", [ dtypes_map["b"], 1, true ] ],
      [ "Uint8Array", [ dtypes_map["B"], 1, true ] ],
      [ "Uint8ClampedArray", [ dtypes_map["B"], 1, true ] ],
      [ "Int16Array", [ dtypes_map["h"], 2, true ] ],
      [ "Uint16Array", [ dtypes_map["H"], 2, true ] ],
      [ "Int32Array", [ dtypes_map["i"], 4, true ] ],
      [ "Uint32Array", [ dtypes_map["I"], 4, true ] ],
      [ "Float32Array", [ dtypes_map["f"], 4, true ] ],
      [ "Float64Array", [ dtypes_map["d"], 8, true ] ],
      // These last two default to Uint8. They have checked : false to allow use
      // with other types.
      [ "DataView", [ dtypes_map["B"], 1, false ] ],
      [ "ArrayBuffer", [ dtypes_map["B"], 1, false ] ],
    ]);

    /**
     * This gets the dtype of a ArrayBuffer or ArrayBuffer view. We return a
     * triple: [char* format_ptr, int itemsize, bool checked] If argument is
     * untyped (a DataView or ArrayBuffer) then we say it's a Uint8, but we set
     * the flag checked to false in that case so we allow assignment to/from
     * anything.
     *
     * This is the API for use from JavaScript, there's also an EM_JS
     * hiwire_get_buffer_datatype wrapper for use from C. Used in js2python and
     * in jsproxy.c for buffers.
     */
    Module.get_buffer_datatype = function(jsobj)
    {
      return buffer_datatype_map.get(jsobj.constructor.name) || [ 0, 0, false ];
    };
  }

  Module.iterObject = function * (object)
  {
    for (let k in object) {
      if (Object.prototype.hasOwnProperty.call(object, k)) {
        yield k;
      }
    }
  };
  return 0;
});

int
hiwire_init()
{
  return hiwire_init_js();
}

HwRef
wrapped_hiwire_incref(HwRef ref)
{
  hiwire_incref(ref);
  return ref;
}

// Called by libhiwire if an invalid ID is dereferenced.
// clang-format off
EM_JS_MACROS(void, hiwire_invalid_ref, (int type, JsRef ref), {
  API.fail_test = true;
  if (type === HIWIRE_FAIL_GET && !ref) {
    // hiwire_get on NULL.
    // This might have happened because the error indicator is set. Let's
    // check.
    if (_PyErr_Occurred()) {
      // This will lead to a more helpful error message.
      const e = _wrap_exception();
      console.error(
        "Pyodide internal error: Argument to hiwire_get is falsy. This was " +
        "probably because the Python error indicator was set when get_value was " +
        "called. The Python error that caused this was:",
        e
      );
      throw e;
    } else {
      const msg = (
          "Pyodide internal error: Argument to hiwire_get is falsy (but error " +
          "indicator is not set)."
      );
      console.error(msg);
      throw new Error(msg);
    }
  }
  const typestr = {
    [HIWIRE_FAIL_GET]: "get",
    [HIWIRE_FAIL_INCREF]: "incref",
    [HIWIRE_FAIL_DECREF]: "decref",
  }[type];
  const msg = (
    `hiwire_${typestr} on invalid reference ${ref}. This is most likely due ` +
    "to use after free. It may also be due to memory corruption."
  );
  console.error(msg);
  throw new Error(msg);
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

// Either syncifyHandler will get filled in by stack_switching/suspenders.mjs or
// stack switching is not available so syncify will always return an error in
// JsProxy.c and syncifyHandler will never be called.
EMSCRIPTEN_KEEPALIVE JsRef (*syncifyHandler)(JsRef idpromise) = NULL;

EM_JS(void, hiwire_syncify_handle_error, (void), {
  if (!Module.syncify_error) {
    // In this case we tried to syncify in a context where there is no
    // suspender. JsProxy.c checks for this case and sets the error flag
    // appropriately.
    return;
  }
  Module.handle_js_error(Module.syncify_error);
  delete Module.syncify_error;
})

JsRef
hiwire_syncify(JsRef idpromise)
{
  JsRef result = syncifyHandler(idpromise);
  if (result == 0) {
    hiwire_syncify_handle_error();
  }
  return result;
}

EM_JS_BOOL(bool, hiwire_HasMethod, (JsRef obj_id, JsRef name), {
  // clang-format off
  let obj = Hiwire.get_value(obj_id);
  return obj && typeof obj[Hiwire.get_value(name)] === "function";
  // clang-format on
})

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
