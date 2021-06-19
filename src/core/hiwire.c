#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"

#define ERROR_REF (0)
#define ERROR_NUM (-1)

const JsRef Js_undefined = ((JsRef)(2));
const JsRef Js_true = ((JsRef)(4));
const JsRef Js_false = ((JsRef)(6));
const JsRef Js_null = ((JsRef)(8));

// For when the return value would be Option<JsRef>
const JsRef Js_novalue = ((JsRef)(1000));

JsRef
hiwire_bool(bool boolean)
{
  return boolean ? Js_true : Js_false;
}

EM_JS_NUM(int, hiwire_init, (), {
  let _hiwire = {
    objects : new Map(),
    // counter is used to allocate keys for the objects map.
    // We use even integers to represent singleton constants which we won't
    // reference count. We only want to allocate odd keys so we start at 1 and
    // step by 2. We use a native uint32 for our counter, so counter
    // automatically overflows back to 1 if it ever gets up to the max u32 =
    // 2^{31} - 1. This ensures we can keep recycling keys even for very long
    // sessions. (Also the native u32 is faster since javascript won't convert
    // it to a float.)
    // 0 == C NULL is an error code for compatibility with Python calling
    // conventions.
    counter : new Uint32Array([1])
  };
  Module.hiwire = {};
  Module.hiwire.UNDEFINED = HEAP8[_Js_undefined];
  Module.hiwire.JSNULL = HEAP8[_Js_null];
  Module.hiwire.TRUE = HEAP8[_Js_true];
  Module.hiwire.FALSE = HEAP8[_Js_false];

  _hiwire.objects.set(Module.hiwire.UNDEFINED, undefined);
  _hiwire.objects.set(Module.hiwire.JSNULL, null);
  _hiwire.objects.set(Module.hiwire.TRUE, true);
  _hiwire.objects.set(Module.hiwire.FALSE, false);

#ifdef DEBUG_F
  Module.hiwire._hiwire = _hiwire;
  let many_objects_warning_threshold = 200;
#endif

  Module.hiwire.new_value = function(jsval)
  {
    // Should we guard against duplicating standard values?
    // Probably not worth it for performance: it's harmless to ocassionally
    // duplicate. Maybe in test builds we could raise if jsval is a standard
    // value?
    while (_hiwire.objects.has(_hiwire.counter[0])) {
      // Increment by two here (and below) because even integers are reserved
      // for singleton constants
      _hiwire.counter[0] += 2;
    }
    let idval = _hiwire.counter[0];
    _hiwire.objects.set(idval, jsval);
    _hiwire.counter[0] += 2;
#ifdef DEBUG_F
    if (_hiwire.objects.size > many_objects_warning_threshold) {
      console.warn(
        "A fairly large number of hiwire objects are present, this could " +
        "be a sign of a memory leak.");
      many_objects_warning_threshold += 100;
    }
#endif
#ifdef HW_TRACE_REFS
    console.warn("hw.new_value", idval, jsval);
#endif
    return idval;
  };

  Module.hiwire.num_keys = function() { return _hiwire.objects.size; };

  Module.hiwire.get_value = function(idval)
  {
    if (!idval) {
      // clang-format off
      // This might have happened because the error indicator is set. Let's
      // check.
      if (_PyErr_Occurred()) {
        // This will lead to a more helpful error message.
        let exc = _wrap_exception();
        let e = Module.hiwire.pop_value(exc);
        console.error(
          `Internal error: Argument '${idval}' to hiwire.get_value is falsy. ` +
          "This was probably because the Python error indicator was set when get_value was called. " +
          "The Python error that caused this was:",
          e
        );
        throw e;
      } else {
        throw new Error(
          `Internal error: Argument '${idval}' to hiwire.get_value is falsy`
          + ' (but error indicator is not set).'
        );
      }
      // clang-format on
    }
    if (!_hiwire.objects.has(idval)) {
      // clang-format off
      console.error(`Undefined id ${ idval }`);
      throw new Error(`Undefined id ${ idval }`);
      // clang-format on
    }
    return _hiwire.objects.get(idval);
  };

  Module.hiwire.decref = function(idval)
  {
    // clang-format off
    if ((idval & 1) === 0) {
      // clang-format on
      // least significant bit unset ==> idval is a singleton.
      // We don't reference count singletons.
      return;
    }
    _hiwire.objects.delete(idval);
  };

  Module.hiwire.pop_value = function(idval)
  {
    let result = Module.hiwire.get_value(idval);
    Module.hiwire.decref(idval);
    return result;
  };

  Module.hiwire.isPromise = function(obj)
  {
    // clang-format off
    return (!!obj) && typeof obj.then === 'function';
    // clang-format on
  };

  /**
   * Turn any ArrayBuffer view or ArrayBuffer into a Uint8Array.
   *
   * This respects slices: if the ArrayBuffer view is restricted to a slice of
   * the backing ArrayBuffer, we return a Uint8Array that shows the same slice.
   */
  Module.typedArrayAsUint8Array = function(arg)
  {
    // clang-format off
    if(arg.buffer !== undefined){
      // clang-format on
      return new Uint8Array(arg.buffer, arg.byteOffset, arg.byteLength);
    } else {
      return new Uint8Array(arg);
    }
  };

  {
    let dtypes_str =
      [ "b", "B", "h", "H", "i", "I", "f", "d" ].join(String.fromCharCode(0));
    let dtypes_ptr = stringToNewUTF8(dtypes_str);
    let dtypes_map = {};
    for (let[idx, val] of Object.entries(dtypes_str)) {
      dtypes_map[val] = dtypes_ptr + Number(idx);
    }

    let buffer_datatype_map = new Map([
      [ 'Int8Array', [ dtypes_map['b'], 1, true ] ],
      [ 'Uint8Array', [ dtypes_map['B'], 1, true ] ],
      [ 'Uint8ClampedArray', [ dtypes_map['B'], 1, true ] ],
      [ 'Int16Array', [ dtypes_map['h'], 2, true ] ],
      [ 'Uint16Array', [ dtypes_map['H'], 2, true ] ],
      [ 'Int32Array', [ dtypes_map['i'], 4, true ] ],
      [ 'Uint32Array', [ dtypes_map['I'], 4, true ] ],
      [ 'Float32Array', [ dtypes_map['f'], 4, true ] ],
      [ 'Float64Array', [ dtypes_map['d'], 8, true ] ],
      // These last two default to Uint8. They have checked : false to allow use
      // with other types.
      [ 'DataView', [ dtypes_map['B'], 1, false ] ],
      [ 'ArrayBuffer', [ dtypes_map['B'], 1, false ] ],
    ]);

    /**
     * This gets the dtype of a ArrayBuffer or ArrayBuffer view. We return a
     * triple: [char* format_ptr, int itemsize, bool checked] If argument is
     * untyped (a DataView or ArrayBuffer) then we say it's a Uint8, but we set
     * the flag checked to false in that case so we allow assignment to/from
     * anything.
     *
     * This is the API for use from Javascript, there's also an EM_JS
     * hiwire_get_buffer_datatype wrapper for use from C. Used in js2python and
     * in jsproxy.c for buffers.
     */
    Module.get_buffer_datatype = function(jsobj)
    {
      return buffer_datatype_map.get(jsobj.constructor.name) || [ 0, 0, false ];
    }
  }

  if (globalThis.BigInt) {
    Module.BigInt = BigInt;
  } else {
    Module.BigInt = Number;
  }
  return 0;
});

EM_JS_REF(JsRef, hiwire_incref, (JsRef idval), {
  // clang-format off
  if ((idval & 1) === 0) {
    // least significant bit unset ==> idval is a singleton.
    // We don't reference count singletons.
    // clang-format on
    return;
  }
  return Module.hiwire.new_value(Module.hiwire.get_value(idval));
});

EM_JS_NUM(errcode, hiwire_decref, (JsRef idval), {
  Module.hiwire.decref(idval);
});

EM_JS_REF(JsRef, hiwire_int, (int val), {
  return Module.hiwire.new_value(val);
});

EM_JS_REF(JsRef, hiwire_int_from_hex, (const char* s), {
  let result;
  // clang-format off
  // Check if number starts with a minus sign
  if (HEAP8[s] === 45) {
    // clang-format on
    result = -Module.BigInt(UTF8ToString(s + 1));
  } else {
    result = Module.BigInt(UTF8ToString(s));
  }
  if (-Number.MAX_SAFE_INTEGER < result && result < Number.MAX_SAFE_INTEGER) {
    result = Number(result);
  }
  return Module.hiwire.new_value(result);
});

EM_JS_REF(JsRef, hiwire_double, (double val), {
  return Module.hiwire.new_value(val);
});

EM_JS_REF(JsRef, hiwire_string_ucs4, (const char* ptr, int len), {
  let jsstr = "";
  let idx = ptr / 4;
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(Module.HEAPU32[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_ucs2, (const char* ptr, int len), {
  let jsstr = "";
  let idx = ptr / 2;
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU16[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_ucs1, (const char* ptr, int len), {
  let jsstr = "";
  let idx = ptr;
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU8[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_utf8, (const char* ptr), {
  return Module.hiwire.new_value(UTF8ToString(ptr));
});

EM_JS_REF(JsRef, hiwire_string_ascii, (const char* ptr), {
  return Module.hiwire.new_value(AsciiToString(ptr));
});

EM_JS(void _Py_NO_RETURN, hiwire_throw_error, (JsRef iderr), {
  throw Module.hiwire.pop_value(iderr);
});

EM_JS_NUM(bool, JsArray_Check, (JsRef idobj), {
  let obj = Module.hiwire.get_value(idobj);
  if (Array.isArray(obj)) {
    return true;
  }
  let typeTag = Object.prototype.toString.call(obj);
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

EM_JS_REF(JsRef, JsArray_New, (), { return Module.hiwire.new_value([]); });

EM_JS_NUM(errcode, JsArray_Push, (JsRef idarr, JsRef idval), {
  Module.hiwire.get_value(idarr).push(Module.hiwire.get_value(idval));
});

EM_JS_REF(JsRef, JsObject_New, (), { return Module.hiwire.new_value({}); });

EM_JS_REF(JsRef, JsObject_GetString, (JsRef idobj, const char* ptrkey), {
  let jsobj = Module.hiwire.get_value(idobj);
  let jskey = UTF8ToString(ptrkey);
  let result = jsobj[jskey];
  // clang-format off
  if (result === undefined && !(jskey in jsobj)) {
    // clang-format on
    return ERROR_REF;
  }
  return Module.hiwire.new_value(result);
});

// clang-format off
EM_JS_NUM(
errcode,
JsObject_SetString,
(JsRef idobj, const char* ptrkey, JsRef idval),
{
  let jsobj = Module.hiwire.get_value(idobj);
  let jskey = UTF8ToString(ptrkey);
  let jsval = Module.hiwire.get_value(idval);
  jsobj[jskey] = jsval;
});

EM_JS_NUM(
errcode,
JsObject_DeleteString,
(JsRef idobj, const char* ptrkey),
{
  let jsobj = Module.hiwire.get_value(idobj);
  let jskey = UTF8ToString(ptrkey);
  delete jsobj[jskey];
});
// clang-format on

EM_JS_REF(JsRef, JsArray_Get, (JsRef idobj, int idx), {
  let obj = Module.hiwire.get_value(idobj);
  let result = obj[idx];
  // clang-format off
  if (result === undefined && !(idx in obj)) {
    // clang-format on
    return ERROR_REF;
  }
  return Module.hiwire.new_value(result);
});

EM_JS_NUM(errcode, JsArray_Set, (JsRef idobj, int idx, JsRef idval), {
  Module.hiwire.get_value(idobj)[idx] = Module.hiwire.get_value(idval);
});

EM_JS_NUM(errcode, JsArray_Delete, (JsRef idobj, int idx), {
  let obj = Module.hiwire.get_value(idobj);
  // Weird edge case: allow deleting an empty entry, but we raise a key error if
  // access is attempted.
  if (idx < 0 || idx >= obj.length) {
    return ERROR_NUM;
  }
  obj.splice(idx, 1);
});

EM_JS_REF(JsRef, JsObject_Dir, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  let result = [];
  do {
    // clang-format off
    result.push(... Object.getOwnPropertyNames(jsobj).filter(
      s => {
        let c = s.charCodeAt(0);
        return c < 48 || c > 57; /* Filter out integer array indices */
      }
    ));
    // clang-format on
  } while (jsobj = Object.getPrototypeOf(jsobj));
  return Module.hiwire.new_value(result);
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
    JsArray_Push(idargs, idarg);
  }
  va_end(args);
  return idargs;
}

EM_JS_REF(JsRef, hiwire_call, (JsRef idfunc, JsRef idargs), {
  let jsfunc = Module.hiwire.get_value(idfunc);
  let jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(jsfunc(... jsargs));
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

EM_JS_REF(JsRef,
          hiwire_call_bound,
          (JsRef idfunc, JsRef idthis, JsRef idargs),
          {
            let func = Module.hiwire.get_value(idfunc);
            let this_;
            // clang-format off
            if (idthis === 0) {
              // clang-format on
              this_ = null;
            } else {
              this_ = Module.hiwire.get_value(idthis);
            }
            let args = Module.hiwire.get_value(idargs);
            return Module.hiwire.new_value(func.apply(this_, args));
          });

EM_JS_REF(JsRef,
          hiwire_call_member,
          (JsRef idobj, const char* ptrname, JsRef idargs),
          {
            let jsobj = Module.hiwire.get_value(idobj);
            let jsname = UTF8ToString(ptrname);
            let jsargs = Module.hiwire.get_value(idargs);
            return Module.hiwire.new_value(jsobj[jsname](... jsargs));
          });

JsRef
hiwire_call_member_va(JsRef idobj, const char* ptrname, ...)
{
  va_list args;
  va_start(args, ptrname);
  JsRef idargs = convert_va_args(args);
  JsRef idresult = hiwire_call_member(idobj, ptrname, idargs);
  hiwire_decref(idargs);
  return idresult;
}

EM_JS_REF(JsRef, hiwire_construct, (JsRef idobj, JsRef idargs), {
  let jsobj = Module.hiwire.get_value(idobj);
  let jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(Reflect.construct(jsobj, jsargs));
});

EM_JS_NUM(bool, hiwire_has_length, (JsRef idobj), {
  let val = Module.hiwire.get_value(idobj);
  // clang-format off
  return (typeof val.size === "number") ||
         (typeof val.length === "number" && typeof val !== "function");
  // clang-format on
});

EM_JS_NUM(int, hiwire_get_length, (JsRef idobj), {
  let val = Module.hiwire.get_value(idobj);
  // clang-format off
  if (typeof val.size === "number") {
    return val.size;
  }
  if (typeof val.length === "number") {
    return val.length;
  }
  // clang-format on
  return ERROR_NUM;
});

EM_JS_NUM(bool, hiwire_get_bool, (JsRef idobj), {
  let val = Module.hiwire.get_value(idobj);
  // clang-format off
  if (!val) {
    return false;
  }
  if (val.size === 0) {
    // I think things with a size are all container types.
    return false;
  }
  if (Array.isArray(val) && val.length === 0) {
    return false;
  }
  return true;
  // clang-format on
});

EM_JS_NUM(bool, hiwire_has_has_method, (JsRef idobj), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  return obj && typeof obj.has === "function";
  // clang-format on
});

EM_JS_NUM(bool, hiwire_call_has_method, (JsRef idobj, JsRef idkey), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  let key = Module.hiwire.get_value(idkey);
  return obj.has(key);
  // clang-format on
});

EM_JS_NUM(bool, hiwire_has_includes_method, (JsRef idobj), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  return obj && typeof obj.includes === "function";
  // clang-format on
});

EM_JS_NUM(bool, hiwire_call_includes_method, (JsRef idobj, JsRef idval), {
  let obj = Module.hiwire.get_value(idobj);
  let val = Module.hiwire.get_value(idval);
  return obj.includes(val);
});

EM_JS_NUM(bool, hiwire_has_get_method, (JsRef idobj), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  return obj && typeof obj.get === "function";
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_call_get_method, (JsRef idobj, JsRef idkey), {
  let obj = Module.hiwire.get_value(idobj);
  let key = Module.hiwire.get_value(idkey);
  let result = obj.get(key);
  // clang-format off
  if (result === undefined) {
    // Try to distinguish between undefined and missing:
    // If the object has a "has" method and it returns false for this key, the
    // key is missing. Otherwise, assume key present and value was undefined.
    // TODO: in absence of a "has" method, should we return None or KeyError?
    if (obj.has && typeof obj.has === "function" && !obj.has(key)) {
      return ERROR_REF;
    }
  }
  // clang-format on
  return Module.hiwire.new_value(result);
});

EM_JS_NUM(bool, hiwire_has_set_method, (JsRef idobj), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  return obj && typeof obj.set === "function";
  // clang-format on
});

EM_JS_NUM(errcode,
          hiwire_call_set_method,
          (JsRef idobj, JsRef idkey, JsRef idval),
          {
            let obj = Module.hiwire.get_value(idobj);
            let key = Module.hiwire.get_value(idkey);
            let val = Module.hiwire.get_value(idval);
            let result = obj.set(key, val);
          });

EM_JS_NUM(errcode, hiwire_call_delete_method, (JsRef idobj, JsRef idkey), {
  let obj = Module.hiwire.get_value(idobj);
  let key = Module.hiwire.get_value(idkey);
  if (!obj.delete(key)) {
    return -1;
  }
});

EM_JS_NUM(bool, hiwire_is_pyproxy, (JsRef idobj), {
  return Module.isPyProxy(Module.hiwire.get_value(idobj));
});

EM_JS_NUM(bool, hiwire_is_function, (JsRef idobj), {
  // clang-format off
  return typeof Module.hiwire.get_value(idobj) === 'function';
  // clang-format on
});

EM_JS_NUM(bool, hiwire_is_comlink_proxy, (JsRef idobj), {
  let value = Module.hiwire.get_value(idobj);
  return !!(Module.Comlink && value[Module.Comlink.createEndpoint]);
});

EM_JS_NUM(bool, hiwire_is_error, (JsRef idobj), {
  // From https://stackoverflow.com/a/45496068
  let value = Module.hiwire.get_value(idobj);
  // clang-format off
  return !!(value && typeof value.stack === "string" &&
            typeof value.message === "string");
  // clang-format on
});

EM_JS_NUM(bool, hiwire_is_promise, (JsRef idobj), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  return Module.hiwire.isPromise(obj);
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_resolve_promise, (JsRef idobj), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  let result = Promise.resolve(obj);
  return Module.hiwire.new_value(result);
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_to_string, (JsRef idobj), {
  return Module.hiwire.new_value(Module.hiwire.get_value(idobj).toString());
});

EM_JS_REF(JsRef, hiwire_typeof, (JsRef idobj), {
  return Module.hiwire.new_value(typeof Module.hiwire.get_value(idobj));
});

EM_JS_REF(char*, hiwire_constructor_name, (JsRef idobj), {
  return stringToNewUTF8(Module.hiwire.get_value(idobj).constructor.name);
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS_NUM(bool, hiwire_##name, (JsRef ida, JsRef idb), {                     \
    return !!(Module.hiwire.get_value(ida) op Module.hiwire.get_value(idb));   \
  })

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
// clang-format off
MAKE_OPERATOR(equal, ===);
MAKE_OPERATOR(not_equal, !==);
// clang-format on
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

EM_JS_REF(JsRef, hiwire_is_iterator, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return typeof jsobj.next === 'function';
  // clang-format on
});

EM_JS_NUM(int, hiwire_next, (JsRef idobj, JsRef* result_ptr), {
  let jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  let { done, value } = jsobj.next();
  // clang-format on
  let result_id = Module.hiwire.new_value(value);
  setValue(result_ptr, result_id, "i32");
  return done;
});

EM_JS_REF(JsRef, hiwire_is_iterable, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return typeof jsobj[Symbol.iterator] === 'function';
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_get_iterator, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(jsobj[Symbol.iterator]());
})

EM_JS_REF(JsRef, JsObject_Entries, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(Object.entries(jsobj));
});

EM_JS_REF(JsRef, JsObject_Keys, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(Object.keys(jsobj));
});

EM_JS_REF(JsRef, JsObject_Values, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(Object.values(jsobj));
});

EM_JS_NUM(bool, hiwire_is_typedarray, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return ArrayBuffer.isView(jsobj) || jsobj.constructor.name === "ArrayBuffer";
  // clang-format on
});

EM_JS_NUM(bool, hiwire_is_on_wasm_heap, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return jsobj.buffer === Module.HEAPU8.buffer;
  // clang-format on
});

EM_JS_NUM(int, hiwire_get_byteOffset, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteOffset'];
});

EM_JS_NUM(int, hiwire_get_byteLength, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteLength'];
});

EM_JS_NUM(errcode, hiwire_assign_to_ptr, (JsRef idobj, void* ptr), {
  let jsobj = Module.hiwire.get_value(idobj);
  Module.HEAPU8.set(Module.typedArrayAsUint8Array(jsobj), ptr);
});

EM_JS_NUM(errcode, hiwire_assign_from_ptr, (JsRef idobj, void* ptr), {
  let jsobj = Module.hiwire.get_value(idobj);
  Module.typedArrayAsUint8Array(jsobj).set(
    Module.HEAPU8.subarray(ptr, ptr + jsobj.byteLength));
});

// clang-format off
EM_JS_NUM(
errcode,
hiwire_get_buffer_datatype,
(JsRef idobj, char** format_ptr, Py_ssize_t* size_ptr, bool* checked_ptr),
{
  let jsobj = Module.hiwire.get_value(idobj);
  let [format_utf8, size, checked] = Module.get_buffer_datatype(jsobj);
  // Store results into arguments
  setValue(format_ptr, format_utf8, "i8*");
  setValue(size_ptr, size, "i32");
  setValue(checked_ptr, size, "i8");
});
// clang-format on

EM_JS_REF(JsRef, hiwire_subarray, (JsRef idarr, int start, int end), {
  let jsarr = Module.hiwire.get_value(idarr);
  let jssub = jsarr.subarray(start, end);
  return Module.hiwire.new_value(jssub);
});

EM_JS_REF(JsRef, JsMap_New, (), { return Module.hiwire.new_value(new Map()); })

EM_JS_NUM(errcode, JsMap_Set, (JsRef mapid, JsRef keyid, JsRef valueid), {
  let map = Module.hiwire.get_value(mapid);
  let key = Module.hiwire.get_value(keyid);
  let value = Module.hiwire.get_value(valueid);
  map.set(key, value);
})

EM_JS_REF(JsRef, JsSet_New, (), { return Module.hiwire.new_value(new Set()); })

EM_JS_NUM(errcode, JsSet_Add, (JsRef mapid, JsRef keyid), {
  let set = Module.hiwire.get_value(mapid);
  let key = Module.hiwire.get_value(keyid);
  set.add(key);
})
