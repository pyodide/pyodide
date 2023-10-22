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

EM_JS(JsVal, JsvInt, (int x), { return x; })

EM_JS(bool, Jsv_to_bool, (JsVal x), { return !!x; })

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
    const ref = _python2js_val(DEREF_U32(values, i));
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
  return Hiwire.isPromise(obj);
  // clang-format on
});

EM_JS_VAL(JsVal, JsvPromise_Resolve, (JsVal obj), {
  // clang-format off
  return Promise.resolve(obj);
  // clang-format on
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
