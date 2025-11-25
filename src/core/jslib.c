#include "jslib.h"
#include "error_handling.h"
#include "jsmemops.h"

#undef true
#undef false

#ifdef DEBUG_F
bool tracerefs;
#endif

#define JS_BUILTIN(val) JS_CONST(val, val)
#define JS_INIT_CONSTS()                                                       \
  JS_BUILTIN(undefined)                                                        \
  JS_BUILTIN(true)                                                             \
  JS_BUILTIN(false)                                                            \
  JS_CONST(error, _Jsv_GetNull())                                              \
  JS_CONST(novalue, { noValueMarker : 1 })

// we use HIWIRE_INIT_CONSTS once in C and once inside JS with different
// definitions of HIWIRE_INIT_CONST to ensure everything lines up properly
// C definition:
#define JS_CONST(name, value) EMSCRIPTEN_KEEPALIVE JsRef Jsr_##name;
JS_INIT_CONSTS();

#undef JS_CONST

#define JS_CONST(name, value) HEAP32[_Jsr_##name / 4] = _hiwire_intern(value);

__attribute__((import_module("sentinel"), import_name("create_sentinel"))) JsVal
Jsv_GetNull_import(void);

EMSCRIPTEN_KEEPALIVE JsVal
Jsv_GetNull(void)
{
  return Jsv_GetNull_import();
}

__attribute__((import_module("sentinel"),
               import_name("is_sentinel"))) int JsvError_Check(JsVal);

EM_JS_NUM(int, jslib_init_js, (void), {
  JS_INIT_CONSTS();
  Module.novalue = _hiwire_get(HEAP32[_Jsr_novalue / 4]);
  Module.error = _hiwire_get(HEAP32[_Jsr_error / 4]);
  Hiwire.num_keys = _hiwire_num_refs;
  return 0;
});

errcode
jslib_init_buffers(void);

errcode
jslib_init(void)
{
  FAIL_IF_MINUS_ONE(jslib_init_buffers());
  FAIL_IF_MINUS_ONE(jslib_init_js());
  return 0;
finally:
  return -1;
}

// clang-format off
EM_JS(int, JsvNoValue_Check, (JsVal v), {
  return v === Module.novalue;
});
// clang-format on

// ==================== Conversions between JsRef and JsVal ====================

JsVal
JsRef_pop(JsRef ref)
{
  if (ref == NULL) {
    return JS_ERROR;
  }
  return hiwire_pop(ref);
}

JsVal
JsRef_toVal(JsRef ref)
{
  if (ref == NULL) {
    return JS_ERROR;
  }
  return hiwire_get(ref);
}

JsRef
JsRef_new(JsVal v)
{
  if (JsvError_Check(v)) {
    return NULL;
  }
  return hiwire_new(v);
}

// ==================== Primitive Conversions ====================

// clang-format off
EM_JS(JsVal, JsvNum_fromInt, (int x), {
  return x;
})

EM_JS(JsVal, JsvNum_fromDouble, (double val), {
  return val;
});

EM_JS_UNCHECKED(JsVal,
JsvNum_fromDigits,
(const unsigned int* digits, size_t ndigits),
{
  let result = BigInt(0);
  for (let i = 0; i < ndigits; i++) {
    result += BigInt(DEREF_U32(digits, i)) << BigInt(32 * i);
  }
  result += BigInt(DEREF_U32(digits, ndigits - 1) & 0x80000000)
            << BigInt(1 + 32 * (ndigits - 1));
  if (-Number.MAX_SAFE_INTEGER < result &&
      result < Number.MAX_SAFE_INTEGER) {
    result = Number(result);
  }
  return result;
});

EM_JS(bool, Jsv_to_bool, (JsVal x), {
  return !!x;
})

EM_JS(JsVal, Jsv_typeof, (JsVal x), {
  return typeof x;
})

EM_JS_REF(char*, Jsv_constructorName, (JsVal obj), {
  return stringToNewUTF8(obj.constructor.name);
});
// clang-format on

// ==================== Strings API  ====================

// clang-format off
EM_JS(JsVal, JsvUTF8ToString, (const char* ptr), {
  return UTF8ToString(ptr);
})

EMSCRIPTEN_KEEPALIVE JsRef
JsrString_FromId(Js_Identifier* id)
{
  if (!id->object) {
    id->object = hiwire_intern(JsvUTF8ToString(id->string));
  }
  return id->object;
}

EMSCRIPTEN_KEEPALIVE JsVal
JsvString_FromId(Js_Identifier* id)
{
  return JsRef_toVal(JsrString_FromId(id));
}


// ==================== JsvArray API  ====================

EM_JS(JsVal, JsvArray_New, (void), {
  return [];
});

EM_JS_BOOL(bool, JsvArray_Check, (JsVal obj), {
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

EM_JS_VAL(JsVal, JsvArray_Get, (JsVal arr, int idx), {
  const result = arr[idx];
  // clang-format off
  if (result === undefined && !(idx in arr)) {
    // clang-format on
    return Module.error;
  }
  return result;
});

EM_JS_NUM(errcode, JsvArray_Set, (JsVal arr, int idx, JsVal val), {
  arr[idx] = val;
});

EM_JS_VAL(JsVal, JsvArray_Delete, (JsVal arr, int idx), {
  // Weird edge case: allow deleting an empty entry, but we raise a key error if
  // access is attempted.
  if (idx < 0 || idx >= arr.length) {
    return Module.error;
  }
  return arr.splice(idx, 1)[0];
});

// clang-format off
EM_JS(int, JsvArray_Push, (JsVal arr, JsVal obj), {
  return arr.push(obj);
});

EM_JS(void, JsvArray_Extend, (JsVal arr, JsVal vals), {
  arr.push(...vals);
});
// clang-format on

EM_JS_NUM(errcode, JsvArray_Insert, (JsVal arr, int idx, JsVal value), {
  arr.splice(idx, 0, value);
});

EM_JS_VAL(JsVal, JsvArray_ShallowCopy, (JsVal arr), {
  return ("slice" in arr) ? arr.slice() : Array.from(arr);
})

// clang-format off
EM_JS_VAL(JsVal,
JsvArray_slice,
(JsVal obj, int length, int start, int stop, int step),
{
  let result;
  if (step === 1) {
    result = obj.slice(start, stop);
  } else {
    result = Array.from({ length }, (_, i) => obj[start + i * step]);
  }
  return result;
});


EM_JS_NUM(errcode,
JsvArray_slice_assign,
(JsVal obj, int slicelength, int start, int stop, int step, int values_length, PyObject **values),
{
  let jsvalues = [];
  for(let i = 0; i < values_length; i++){
    const ref = _python2js(DEREF_U32(values, i));
    if (ref === Module.error){
      return -1;
    }
    jsvalues.push(ref);
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

// ==================== JsvObject API  ====================


EM_JS(JsVal, JsvObject_New, (void), {
  return {};
});

EM_JS_NUM(int, JsvObject_SetAttr, (JsVal obj, JsVal attr, JsVal value), {
  obj[attr] = value;
});

EM_JS_VAL(JsVal, JsvObject_Entries, (JsVal obj), {
  return Object.entries(obj);
});

EM_JS_VAL(JsVal, JsvObject_Keys, (JsVal obj), {
  return Object.keys(obj);
});

EM_JS_VAL(JsVal, JsvObject_Values, (JsVal obj), {
  return Object.values(obj);
});

EM_JS_VAL(JsVal,
JsvObject_toString, (JsVal obj), {
  if (hasMethod(obj, "toString")) {
    return obj.toString();
  }
  return Object.prototype.toString.call(obj);
});


EM_JS_VAL(JsVal, JsvObject_CallMethod, (JsVal obj, JsVal meth, JsVal args), {
  return obj[meth](... args);
})

EM_JS_VAL(JsVal, JsvObject_CallMethod_NoArgs, (JsVal obj, JsVal meth), {
  return obj[meth]();
})

EM_JS_VAL(JsVal, JsvObject_CallMethod_OneArg, (JsVal obj, JsVal meth, JsVal arg), {
  return obj[meth](arg);
})

EM_JS_VAL(JsVal, JsvObject_CallMethod_TwoArgs, (JsVal obj, JsVal meth, JsVal arg1, JsVal arg2), {
  return obj[meth](arg1, arg2);
})

JsVal
JsvObject_CallMethodId(JsVal obj, Js_Identifier* name_id, JsVal args)
{
  return JsvObject_CallMethod(obj, JsvString_FromId(name_id), args);
}

JsVal
JsvObject_CallMethodId_NoArgs(JsVal obj, Js_Identifier* name_id)
{
  return JsvObject_CallMethod_NoArgs(obj, JsvString_FromId(name_id));
}

JsVal
JsvObject_CallMethodId_OneArg(JsVal obj, Js_Identifier* name_id, JsVal arg)
{
  return JsvObject_CallMethod_OneArg(obj, JsvString_FromId(name_id), arg);
}

JsVal
JsvObject_CallMethodId_TwoArgs(JsVal obj,
                               Js_Identifier* name_id,
                               JsVal arg1,
                               JsVal arg2)
{
  return JsvObject_CallMethod_TwoArgs(obj, JsvString_FromId(name_id), arg1, arg2);
}


// ==================== JsvFunction API  ====================

EM_JS_BOOL(bool, JsvFunction_Check, (JsVal obj), {
  // clang-format off
  return typeof obj === 'function';
  // clang-format on
});

EM_JS_VAL(JsVal, JsvFunction_CallBound, (JsVal func, JsVal this_, JsVal args), {
  return Function.prototype.apply.apply(func, [ this_, args ]);
});

EM_JS_VAL(JsVal, JsvFunction_Call_OneArg, (JsVal func, JsVal arg), {
  return func(arg);
});

// clang-format off
EM_JS_VAL(JsVal,
JsvFunction_Construct,
(JsVal func, JsVal args),
{
  return Reflect.construct(func, args);
});
// clang-format on

// ==================== JsvPromise API  ====================

EM_JS_BOOL(bool, JsvPromise_Check, (JsVal obj), {
  // clang-format off
  return isPromise(obj);
  // clang-format on
});

EM_JS_VAL(JsVal, JsvPromise_Resolve, (JsVal obj), {
  // clang-format off
  return Promise.resolve(obj);
  // clang-format on
});

// ==================== Buffers ====================

// clang-format off
EM_JS_NUM(errcode, jslib_init_buffers_js, (), {
  const dtypes_str = Array.from("bBhHiIqQefd").join(
    String.fromCharCode(0)
  );
  const dtypes_ptr = stringToNewUTF8(dtypes_str);
  const dtypes_map = Object.fromEntries(
    Object.entries(dtypes_str).map(([idx, val]) => [val, dtypes_ptr + +idx])
  );

  const buffer_datatype_map = new Map([
    ["Int8Array", [dtypes_map["b"], 1, true]],
    ["Uint8Array", [dtypes_map["B"], 1, true]],
    ["Uint8ClampedArray", [dtypes_map["B"], 1, true]],
    ["Int16Array", [dtypes_map["h"], 2, true]],
    ["Uint16Array", [dtypes_map["H"], 2, true]],
    ["Float16Array", [dtypes_map["e"], 2, true]],
    ["Int32Array", [dtypes_map["i"], 4, true]],
    ["Uint32Array", [dtypes_map["I"], 4, true]],
    ["Float32Array", [dtypes_map["f"], 4, true]],
    ["Float64Array", [dtypes_map["d"], 8, true]],
    ["BigInt64Array", [dtypes_map["q"], 8, true]],
    ["BigUint64Array", [dtypes_map["Q"], 8, true]],
    // These last two default to Uint8. They have checked : false to allow use
    // with other types.
    ["DataView", [dtypes_map["B"], 1, false]],
    ["ArrayBuffer", [dtypes_map["B"], 1, false]],
  ]);

  /**
   * This gets the dtype of a ArrayBuffer or ArrayBuffer view. We return a
   * triple: [char* format_ptr, int itemsize, bool checked] If argument is
   * untyped (a DataView or ArrayBuffer) then we say it's a Uint8, but we set
   * the flag checked to false in that case so we allow assignment to/from
   * anything.
   *
   * This is the API for use from JavaScript, there's also an EM_JS
   * get_buffer_datatype wrapper for use from C. Used in js2python and
   * in jsproxy.c for buffers.
   */
  API.get_buffer_datatype = function (jsobj) {
    return buffer_datatype_map.get(jsobj.constructor.name) || [0, 0, false];
  };
});
// clang-format on

// DCE has trouble with forward declared EM_JS functions...
errcode
jslib_init_buffers(void)
{
  return jslib_init_buffers_js();
}

EM_JS_NUM(errcode, JsvBuffer_assignToPtr, (JsVal buf, void* ptr), {
  Module.HEAPU8.set(bufferAsUint8Array(buf), ptr);
});

EM_JS_NUM(errcode, JsvBuffer_assignFromPtr, (JsVal buf, void* ptr), {
  bufferAsUint8Array(buf).set(
    Module.HEAPU8.subarray(ptr, ptr + buf.byteLength));
});

EM_JS_NUM(errcode, JsvBuffer_readFromFile, (JsVal buf, int fd), {
  let uint8_buf = bufferAsUint8Array(buf);
  let stream = Module.FS.streams[fd];
  Module.FS.read(stream, uint8_buf, 0, uint8_buf.byteLength);
});

EM_JS_NUM(errcode, JsvBuffer_writeToFile, (JsVal buf, int fd), {
  let uint8_buf = bufferAsUint8Array(buf);
  let stream = Module.FS.streams[fd];
  Module.FS.write(stream, uint8_buf, 0, uint8_buf.byteLength);
});

EM_JS_NUM(errcode, JsvBuffer_intoFile, (JsVal buf, int fd), {
  let uint8_buf = bufferAsUint8Array(buf);
  let stream = Module.FS.streams[fd];
  // set canOwn param to true, leave position undefined.
  Module.FS.write(stream, uint8_buf, 0, uint8_buf.byteLength, undefined, true);
});

// ==================== Miscellaneous  ====================

EM_JS_BOOL(bool, JsvGenerator_Check, (JsVal obj), {
  // clang-format off
  return getTypeTag(obj) === "[object Generator]";
  // clang-format on
});

EM_JS_BOOL(bool, JsvAsyncGenerator_Check, (JsVal obj), {
  // clang-format off
  return getTypeTag(obj) === "[object AsyncGenerator]";
  // clang-format on
});

EM_JS(void __attribute__((__noreturn__)), JsvError_Throw, (JsVal e), {
  throw e;
})

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS_BOOL(bool, Jsv_##name, (JsVal a, JsVal b), { return !!(a op b); })

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
// clang-format off
MAKE_OPERATOR(equal, ===);
MAKE_OPERATOR(not_equal, !==);
// clang-format on
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

// ==================== JsMap API  ====================

// clang-format off
EM_JS_VAL(JsVal, JsvMap_New, (), {
  return new Map();
})

EM_JS_VAL(JsVal, JsvLiteralMap_New, (), {
  return new API.LiteralMap();
})
// clang-format on

EM_JS_NUM(errcode, JsvMap_Set, (JsVal map, JsVal key, JsVal val), {
  map.set(key, val);
})

// ==================== JsSet API  ====================

// clang-format off
EM_JS_VAL(JsVal, JsvSet_New, (), {
  return new Set();
})

EM_JS_NUM(errcode, JsvSet_Add, (JsVal set, JsVal val), {
  set.add(val);
})
// clang-format on
