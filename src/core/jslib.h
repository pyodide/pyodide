#ifndef JSLIB_H
#define JSLIB_H
#include "hiwire.h"

// ==================== JS_NULL ====================

#define JS_NULL __builtin_wasm_ref_null_extern()

int JsvNull_Check(JsVal);

// ==================== Conversions between JsRef and JsVal ====================

JsRef
JsRef_new(JsVal v);

JsVal
JsRef_pop(JsRef ref);

JsVal
JsRef_toVal(JsRef ref);

// ==================== Primitive Conversions ====================

JsVal
JsvInt(int x);

bool
Jsv_to_bool(JsVal x);

JsVal
JsvUTF8ToString(const char*);

JsRef
JsrString_FromId(Js_Identifier* id);

JsVal
JsvString_FromId(Js_Identifier* id);

// ==================== JsvArray API  ====================

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

// ==================== JsvObject API  ====================

JsVal
JsvObject_New();

JsVal JsvObject_Entries(JsVal);

JsVal JsvObject_Keys(JsVal);

JsVal JsvObject_Values(JsVal);

int
JsvObject_SetAttr(JsVal obj, JsVal attr, JsVal value);

JsVal
JsvObject_CallMethod(JsVal obj, JsVal meth, JsVal args);

JsVal
JsvObject_CallMethod_NoArgs(JsVal obj, JsVal meth);

JsVal
JsvObject_CallMethod_OneArg(JsVal obj, JsVal meth, JsVal arg);

JsVal
JsvObject_CallMethod_TwoArgs(JsVal obj, JsVal meth, JsVal arg1, JsVal arg2);

JsVal
JsvObject_CallMethodId(JsVal obj, Js_Identifier* meth_id, JsVal args);

JsVal
JsvObject_CallMethodId_NoArgs(JsVal obj, Js_Identifier* name_id);

JsVal
JsvObject_CallMethodId_OneArg(JsVal obj, Js_Identifier* meth_id, JsVal arg);

JsVal
JsvObject_CallMethodId_TwoArgs(JsVal obj,
                               Js_Identifier* meth_id,
                               JsVal arg1,
                               JsVal arg2);

// ==================== JsvFunction API  ====================

bool
JsvFunction_Check(JsVal obj);

JsVal
JsvFunction_Call_OneArg(JsVal func, JsVal arg);

JsVal
JsvFunction_CallBound(JsVal func, JsVal this, JsVal args);

JsVal
JsvFunction_Construct(JsVal func, JsVal args);

// ==================== Miscellaneous  ====================

bool
JsvPromise_Check(JsVal obj);

JsVal
JsvPromise_Resolve(JsVal obj);

bool
JsvGenerator_Check(JsVal obj);

bool
JsvAsyncGenerator_Check(JsVal obj);

void _Py_NO_RETURN
JsvError_Throw(JsVal e);

#endif
