#include "jslib.h"

EM_JS(JsVal, JsLib_Array_Get, (JsVal array, int idx), { return array[idx]; })
