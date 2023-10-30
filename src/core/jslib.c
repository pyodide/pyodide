#include "jslib.h"
#include "error_handling.h"
#include "jsmemops.h"

// ==================== Conversions between JsRef and JsVal ====================

JsVal
JsRef_pop(JsRef ref)
{
  if (ref == NULL) {
    return JS_NULL;
  }
  return hiwire_pop(ref);
}

JsVal
JsRef_toVal(JsRef ref)
{
  if (ref == NULL) {
    return JS_NULL;
  }
  return hiwire_get(ref);
}

JsRef
JsRef_new(JsVal v)
{
  if (JsvNull_Check(v)) {
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

EM_JS(JsVal, JsvArray_New, (), {
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
    return null;
  }
  return nullToUndefined(result);
});

EM_JS_NUM(errcode, JsvArray_Set, (JsVal arr, int idx, JsVal val), {
  arr[idx] = val;
});

EM_JS_VAL(JsVal, JsvArray_Delete, (JsVal arr, int idx), {
  // Weird edge case: allow deleting an empty entry, but we raise a key error if
  // access is attempted.
  if (idx < 0 || idx >= arr.length) {
    return null;
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

EM_JS_NUM(JsVal, JsvArray_ShallowCopy, (JsVal arr), {
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
    if(ref === null){
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


EM_JS(JsVal, JsvObject_New, (), {
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
  return obj.toString();
});


EM_JS_VAL(JsVal, JsvObject_CallMethod, (JsVal obj, JsVal meth, JsVal args), {
  return nullToUndefined(obj[meth](... args));
})

EM_JS_VAL(JsVal, JsvObject_CallMethod_NoArgs, (JsVal obj, JsVal meth), {
  return nullToUndefined(obj[meth]());
})

EM_JS_VAL(JsVal, JsvObject_CallMethod_OneArg, (JsVal obj, JsVal meth, JsVal arg), {
  return nullToUndefined(obj[meth](arg));
})

EM_JS_VAL(JsVal, JsvObject_CallMethod_TwoArgs, (JsVal obj, JsVal meth, JsVal arg1, JsVal arg2), {
  return nullToUndefined(obj[meth](arg1, arg2));
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
  return nullToUndefined(func.apply(this_, args));
});

EM_JS_VAL(JsVal, JsvFunction_Call_OneArg, (JsVal func, JsVal arg), {
  return nullToUndefined(func.apply(null, [arg]));
});

// clang-format off
EM_JS_VAL(JsVal,
JsvFunction_Construct,
(JsVal func, JsVal args),
{
  return nullToUndefined(Reflect.construct(func, args));
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

// Either syncifyHandler will get filled in by stack_switching/suspenders.mjs or
// stack switching is not available so syncify will always return an error in
// JsProxy.c and syncifyHandler will never be called.
EMSCRIPTEN_KEEPALIVE JsVal (*syncifyHandler)(JsVal promise) = NULL;

EM_JS(void, JsvPromise_Syncify_handleError, (void), {
  if (!Module.syncify_error) {
    // In this case we tried to syncify in a context where there is no
    // suspender. JsProxy.c checks for this case and sets the error flag
    // appropriately.
    return;
  }
  Module.handle_js_error(Module.syncify_error);
  delete Module.syncify_error;
})

JsVal
JsvPromise_Syncify(JsVal promise)
{
  JsVal result = syncifyHandler(promise);
  if (JsvNull_Check(result)) {
    JsvPromise_Syncify_handleError();
  }
  return result;
}

// ==================== Buffers ====================

// clang-format off
EM_JS_NUM(errcode, jslib_init_buffers, (), {
  const dtypes_str = ["b", "B", "h", "H", "i", "I", "f", "d"].join(
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
    ["Int32Array", [dtypes_map["i"], 4, true]],
    ["Uint32Array", [dtypes_map["I"], 4, true]],
    ["Float32Array", [dtypes_map["f"], 4, true]],
    ["Float64Array", [dtypes_map["d"], 8, true]],
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
  Module.get_buffer_datatype = function (jsobj) {
    return buffer_datatype_map.get(jsobj.constructor.name) || [0, 0, false];
  };
});
// clang-format on

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

EM_JS(void _Py_NO_RETURN, JsvError_Throw, (JsVal e), { throw e; })

EM_JS(JsVal, jslib_init_novalue_js, (), {
  Module.Jsv_NoValue = { noValueMarker : 1 };
  return Module.Jsv_NoValue;
})

JsRef Jsr_NoValue = NULL;

void
jslib_init_novalue()
{
  Jsr_NoValue = hiwire_intern(jslib_init_novalue_js());
}

// clang-format off
EM_JS(int, JsvNoValue_Check, (JsVal v), {
  return v === Module.Jsv_NoValue;
});
// clang-format on

errcode
jslib_init(void)
{
  FAIL_IF_MINUS_ONE(jslib_init_buffers());
  jslib_init_novalue();
  return 0;
finally:
  return -1;
}

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
