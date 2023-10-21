#ifndef JSLIB_H
#define JSLIB_H
#include "hiwire.h"

#define JS_NULL __builtin_wasm_ref_null_extern()

int JsvNull_Check(JsVal);

JsVal
Jsv_pop_ref(JsRef ref);

JsVal
Jsv_from_ref(JsRef ref);

JsVal
JsvInt(int x);

bool
Jsv_to_bool(JsVal x);

JsVal
JsvUTF8ToString(const char*);

JsVal
JsvArray_New();

bool
JsvArray_Check(JsVal obj);

JsVal
JsvArray_Get(JsVal, int);

errcode
JsvArray_Set(JsVal, int, JsVal);

JsVal
JsvArray_Delete(JsVal, int);

int JsvArray_Push(JsVal, JsVal);

void JsvArray_Extend(JsVal, JsVal);

JsVal
JsvArray_ShallowCopy(JsVal obj);

JsVal
JsvArray_slice(JsVal obj, int length, int start, int stop, int step);

errcode
JsvArray_slice_assign(JsVal idobj,
                      int slicelength,
                      int start,
                      int stop,
                      int step,
                      int values_length,
                      PyObject** values);

JsVal
JsvObject_New();

int
JsvObject_SetAttr(JsVal obj, JsVal attr, JsVal value);

JsVal
JsvObject_CallMethod(JsVal obj, JsVal meth, JsVal args);

JsVal
JsvObject_CallMethodId(JsVal obj, Js_Identifier* meth_id, JsVal args);

JsVal
JsvObject_CallMethodId_OneArg(JsVal obj, Js_Identifier* meth_id, JsVal arg);

JsVal
JsvObject_CallMethodId_TwoArgs(JsVal obj,
                               Js_Identifier* meth_id,
                               JsVal arg1,
                               JsVal arg2);

bool
JsvFunction_Check(JsVal obj);

JsVal
JsvFunction_CallBound(JsVal func, JsVal this, JsVal args);

JsVal
JsvFunction_Construct(JsVal func, JsVal args);

bool
JsvPromise_Check(JsVal obj);

JsVal
JsvPromise_Resolve(JsVal obj);

bool
JsvGenerator_Check(JsVal obj);

bool
JsvAsyncGenerator_Check(JsVal obj);
#endif
