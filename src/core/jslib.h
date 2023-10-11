#ifndef JSLIB_H
#define JSLIB_H
#include "hiwire.h"

int Jsv_is_null(JsVal);

JsVal
JsvArray_New();

JsVal
JsvArray_Get(JsVal, int);

void JsvArray_Push(JsVal, JsVal);

JsVal
JsvUTF8ToString(const char*);

#endif
