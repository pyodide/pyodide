#ifndef JSLIB_H
#define JSLIB_H
#include "hiwire.h"

#define JS_NULL __builtin_wasm_ref_null_extern()

int Jsv_is_null(JsVal);

JsVal
JsvArray_New();

JsVal
JsvArray_Get(JsVal, int);

void JsvArray_Push(JsVal, JsVal);

JsVal
JsvUTF8ToString(const char*);

#endif
