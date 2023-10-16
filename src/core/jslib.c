#include "jslib.h"

EM_JS(JsVal, JsvArray_New, (), { return []; });

EM_JS(JsVal, JsvArray_Get_js, (JsVal array, int idx), { return array[idx]; })

JsVal
JsvArray_Get(JsVal array, int idx)
{
  return JsvArray_Get_js(array, idx);
}

EM_JS(void, JsvArray_Push, (JsVal array, JsVal obj), { array.push(obj); });

EM_JS(JsVal, JsvUTF8ToString, (const char* ptr), { return UTF8ToString(ptr); })
