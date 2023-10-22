#include "jslib.h"
#include "error_handling.h"

JsVal
Jsv_pop_ref(JsRef ref)
{
  if (ref == NULL) {
    return JS_NULL;
  }
  return hiwire_pop(ref);
}

JsVal
Jsv_from_ref(JsRef ref)
{
  if (ref == NULL) {
    return JS_NULL;
  }
  return hiwire_get(ref);
}

// clang-format off
EM_JS(JsVal, JsvUTF8ToString, (const char* ptr), {
  return UTF8ToString(ptr);
})

EM_JS(JsVal, JsvArray_New, (), {
  return [];
});

EM_JS(JsVal, JsvArray_Get_js, (JsVal array, int idx), {
  return nullToUndefined(array[idx]);
})

JsVal
JsvArray_Get(JsVal array, int idx)
{
  return JsvArray_Get_js(array, idx);
}

EM_JS(void, JsvArray_Push, (JsVal array, JsVal obj), {
  array.push(obj);
});

EM_JS(JsVal, JsvObject_New, (), {
  return {};
});
// clang-format on

EM_JS_NUM(int, JsvObject_SetAttr, (JsVal obj, JsVal attr, JsVal value), {
  obj[attr] = value;
});

EM_JS_VAL(JsVal, JsvObject_CallMethod, (JsVal obj, JsVal meth, JsVal args), {
  return nullToUndefined(obj[meth](... args));
})

JsVal
JsvObject_CallMethodId(JsVal obj, Js_Identifier* name_id, JsVal args)
{
  JsRef name_ref = JsString_FromId(name_id);
  if (name_ref == NULL) {
    return JS_NULL;
  }
  return JsvObject_CallMethod(obj, hiwire_get(name_ref), args);
}

EM_JS_BOOL(bool, JsvFunction_Check, (JsVal obj), {
  // clang-format off
  return typeof obj === 'function';
  // clang-format on
});

EM_JS_VAL(JsVal, JsvFunction_CallBound, (JsVal func, JsVal this_, JsVal args), {
  return nullToUndefined(func.apply(this_, args));
});

// clang-format off
EM_JS_VAL(JsVal,
JsvFunction_Construct,
(JsVal func, JsVal args),
{
  return nullToUndefined(Reflect.construct(func, args));
});
// clang-format on

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
