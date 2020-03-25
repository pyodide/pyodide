#include <emscripten.h>

#include "hiwire.h"

// Define special ids for singleton constants. These must be less than -1 to
// avoid being reused for other values.
#define HW_UNDEFINED -2
#define HW_TRUE -3
#define HW_FALSE -4
#define HW_NULL -5

EM_JS(void, hiwire_setup, (), {
  // These ids must match the constants above, but we can't use them from JS
  var hiwire = { objects : {}, counter : 1 };
  hiwire.objects[-2] = undefined;
  hiwire.objects[-3] = true;
  hiwire.objects[-4] = false;
  hiwire.objects[-5] = null;

  Module.hiwire_new_value = function(jsval)
  {
    var objects = hiwire.objects;
    while (hiwire.counter in objects) {
      hiwire.counter = (hiwire.counter + 1) & 0x7fffffff;
    }
    var idval = hiwire.counter;
    objects[idval] = jsval;
    hiwire.counter = (hiwire.counter + 1) & 0x7fffffff;
    return idval;
  };

  Module.hiwire_get_value = function(idval) { return hiwire.objects[idval]; };

  Module.hiwire_decref = function(idval)
  {
    if (idval < 0) {
      return;
    }
    var objects = hiwire.objects;
    delete objects[idval];
  };
});

EM_JS(int, hiwire_incref, (int idval), {
  if (idval < 0) {
    return;
  }
  return Module.hiwire_new_value(Module.hiwire_get_value(idval));
});

EM_JS(void, hiwire_decref, (int idval), { Module.hiwire_decref(idval); });

EM_JS(int, hiwire_int, (int val), { return Module.hiwire_new_value(val); });

EM_JS(int, hiwire_double, (double val), {
  return Module.hiwire_new_value(val);
});

EM_JS(int, hiwire_string_ucs4, (int ptr, int len), {
  var jsstr = "";
  var idx = ptr / 4;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(Module.HEAPU32[idx + i]);
  }
  return Module.hiwire_new_value(jsstr);
});

EM_JS(int, hiwire_string_ucs2, (int ptr, int len), {
  var jsstr = "";
  var idx = ptr / 2;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU16[idx + i]);
  }
  return Module.hiwire_new_value(jsstr);
});

EM_JS(int, hiwire_string_ucs1, (int ptr, int len), {
  var jsstr = "";
  var idx = ptr;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU8[idx + i]);
  }
  return Module.hiwire_new_value(jsstr);
});

EM_JS(int, hiwire_string_utf8, (int ptr), {
  return Module.hiwire_new_value(UTF8ToString(ptr));
});

EM_JS(int, hiwire_string_ascii, (int ptr), {
  return Module.hiwire_new_value(AsciiToString(ptr));
});

EM_JS(int, hiwire_bytes, (int ptr, int len), {
  var bytes = new Uint8ClampedArray(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(bytes);
});

EM_JS(int, hiwire_int8array, (int ptr, int len), {
  var array = new Int8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(array);
})

EM_JS(int, hiwire_uint8array, (int ptr, int len), {
  var array = new Uint8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(array);
})

EM_JS(int, hiwire_int16array, (int ptr, int len), {
  var array = new Int16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(array);
})

EM_JS(int, hiwire_uint16array, (int ptr, int len), {
  var array = new Uint16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(array);
})

EM_JS(int, hiwire_int32array, (int ptr, int len), {
  var array = new Int32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(array);
})

EM_JS(int, hiwire_uint32array, (int ptr, int len), {
  var array = new Uint32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(array);
})

EM_JS(int, hiwire_float32array, (int ptr, int len), {
  var array = new Float32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(array);
})

EM_JS(int, hiwire_float64array, (int ptr, int len), {
  var array = new Float64Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(array);
})

int
hiwire_undefined()
{
  return HW_UNDEFINED;
}

int
hiwire_null()
{
  return HW_NULL;
}

int
hiwire_true()
{
  return HW_TRUE;
}

int
hiwire_false()
{
  return HW_FALSE;
}

EM_JS(void, hiwire_throw_error, (int idmsg), {
  var jsmsg = Module.hiwire_get_value(idmsg);
  Module.hiwire_decref(idmsg);
  throw new Error(jsmsg);
});

EM_JS(int, hiwire_array, (), { return Module.hiwire_new_value([]); });

EM_JS(void, hiwire_push_array, (int idarr, int idval), {
  Module.hiwire_get_value(idarr).push(Module.hiwire_get_value(idval));
});

EM_JS(int, hiwire_object, (), { return Module.hiwire_new_value({}); });

EM_JS(void, hiwire_push_object_pair, (int idobj, int idkey, int idval), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jskey = Module.hiwire_get_value(idkey);
  var jsval = Module.hiwire_get_value(idval);
  jsobj[jskey] = jsval;
});

EM_JS(int, hiwire_get_global, (int idname), {
  var jsname = UTF8ToString(idname);
  if (jsname in self) {
    return Module.hiwire_new_value(self[jsname]);
  } else {
    return -1;
  }
});

EM_JS(int, hiwire_get_member_string, (int idobj, int idkey), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jskey = UTF8ToString(idkey);
  if (jskey in jsobj) {
    return Module.hiwire_new_value(jsobj[jskey]);
  } else {
    return -1;
  }
});

EM_JS(void, hiwire_set_member_string, (int idobj, int ptrkey, int idval), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jskey = UTF8ToString(ptrkey);
  var jsval = Module.hiwire_get_value(idval);
  jsobj[jskey] = jsval;
});

EM_JS(void, hiwire_delete_member_string, (int idobj, int ptrkey), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jskey = UTF8ToString(ptrkey);
  delete jsobj[jskey];
});

EM_JS(int, hiwire_get_member_int, (int idobj, int idx), {
  var jsobj = Module.hiwire_get_value(idobj);
  return Module.hiwire_new_value(jsobj[idx]);
});

EM_JS(void, hiwire_set_member_int, (int idobj, int idx, int idval), {
  Module.hiwire_get_value(idobj)[idx] = Module.hiwire_get_value(idval);
});

EM_JS(int, hiwire_get_member_obj, (int idobj, int ididx), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jsidx = Module.hiwire_get_value(ididx);
  if (jsidx in jsobj) {
    return Module.hiwire_new_value(jsobj[jsidx]);
  } else {
    return -1;
  }
});

EM_JS(void, hiwire_set_member_obj, (int idobj, int ididx, int idval), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jsidx = Module.hiwire_get_value(ididx);
  var jsval = Module.hiwire_get_value(idval);
  jsobj[jsidx] = jsval;
});

EM_JS(void, hiwire_delete_member_obj, (int idobj, int ididx), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jsidx = Module.hiwire_get_value(ididx);
  delete jsobj[jsidx];
});

EM_JS(int, hiwire_dir, (int idobj), {
  var jsobj = Module.hiwire_get_value(idobj);
  var result = [];
  do {
    result.push.apply(result, Object.getOwnPropertyNames(jsobj));
  } while ((jsobj = Object.getPrototypeOf(jsobj)));
  return Module.hiwire_new_value(result);
});

EM_JS(int, hiwire_call, (int idfunc, int idargs), {
  var jsfunc = Module.hiwire_get_value(idfunc);
  var jsargs = Module.hiwire_get_value(idargs);
  return Module.hiwire_new_value(jsfunc.apply(jsfunc, jsargs));
});

EM_JS(int, hiwire_call_member, (int idobj, int ptrname, int idargs), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jsname = UTF8ToString(ptrname);
  var jsargs = Module.hiwire_get_value(idargs);
  return Module.hiwire_new_value(jsobj[jsname].apply(jsobj, jsargs));
});

EM_JS(int, hiwire_new, (int idobj, int idargs), {
  function newCall(Cls)
  {
    return new (Function.prototype.bind.apply(Cls, arguments));
  }
  var jsobj = Module.hiwire_get_value(idobj);
  var jsargs = Module.hiwire_get_value(idargs);
  jsargs.unshift(jsobj);
  return Module.hiwire_new_value(newCall.apply(newCall, jsargs));
});

EM_JS(int, hiwire_get_length, (int idobj), {
  return Module.hiwire_get_value(idobj).length;
});

EM_JS(int, hiwire_get_bool, (int idobj), {
  var val = Module.hiwire_get_value(idobj);
  // clang-format off
  return (val && (val.length === undefined || val.length)) ? 1 : 0;
  // clang-format on
});

EM_JS(int, hiwire_is_function, (int idobj), {
  // clang-format off
  return typeof Module.hiwire_get_value(idobj) === 'function';
  // clang-format on
});

EM_JS(int, hiwire_to_string, (int idobj), {
  return Module.hiwire_new_value(Module.hiwire_get_value(idobj).toString());
});

EM_JS(int, hiwire_typeof, (int idobj), {
  return Module.hiwire_new_value(typeof Module.hiwire_get_value(idobj));
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS(int, hiwire_##name, (int ida, int idb), {                              \
    return (Module.hiwire_get_value(ida) op Module.hiwire_get_value(idb)) ? 1  \
                                                                          : 0; \
  });

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
MAKE_OPERATOR(equal, ==);
MAKE_OPERATOR(not_equal, !=);
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

EM_JS(int, hiwire_next, (int idobj), {
  // clang-format off
  if (idobj === -2) {
    // clang-format on
    return -1;
  }

  var jsobj = Module.hiwire_get_value(idobj);
  return Module.hiwire_new_value(jsobj.next());
});

EM_JS(int, hiwire_get_iterator, (int idobj), {
  // clang-format off
  if (idobj === -2) {
    return -1;
  }

  var jsobj = Module.hiwire_get_value(idobj);
  if (typeof jsobj.next === 'function') {
    return Module.hiwire_new_value(jsobj);
  } else if (typeof jsobj[Symbol.iterator] === 'function') {
    return Module.hiwire_new_value(jsobj[Symbol.iterator]());
  } else {
    return Module.hiwire_new_value(
      Object.entries(jsobj)[Symbol.iterator]()
    );
  }
  return -1;
  // clang-format on
})

EM_JS(int, hiwire_nonzero, (int idobj), {
  var jsobj = Module.hiwire_get_value(idobj);
  return (jsobj != 0) ? 1 : 0;
});

EM_JS(int, hiwire_is_typedarray, (int idobj), {
  var jsobj = Module.hiwire_get_value(idobj);
  // clang-format off
  return (jsobj['byteLength'] !== undefined) ? 1 : 0;
  // clang-format on
});

EM_JS(int, hiwire_is_on_wasm_heap, (int idobj), {
  var jsobj = Module.hiwire_get_value(idobj);
  // clang-format off
  return (jsobj.buffer === Module.HEAPU8.buffer) ? 1 : 0;
  // clang-format on
});

EM_JS(int, hiwire_get_byteOffset, (int idobj), {
  var jsobj = Module.hiwire_get_value(idobj);
  return jsobj['byteOffset'];
});

EM_JS(int, hiwire_get_byteLength, (int idobj), {
  var jsobj = Module.hiwire_get_value(idobj);
  return jsobj['byteLength'];
});

EM_JS(int, hiwire_copy_to_ptr, (int idobj, int ptr), {
  var jsobj = Module.hiwire_get_value(idobj);
  // clang-format off
  var buffer = (jsobj['buffer'] !== undefined) ? jsobj.buffer : jsobj;
  // clang-format on
  Module.HEAPU8.set(new Uint8Array(buffer), ptr);
});

EM_JS(int, hiwire_get_dtype, (int idobj), {
  var jsobj = Module.hiwire_get_value(idobj);
  switch (jsobj.constructor.name) {
    case 'Int8Array':
      dtype = 1; // INT8_TYPE;
      break;
    case 'Uint8Array':
      dtype = 2; // UINT8_TYPE;
      break;
    case 'Uint8ClampedArray':
      dtype = 3; // UINT8CLAMPED_TYPE;
      break;
    case 'Int16Array':
      dtype = 4; // INT16_TYPE;
      break;
    case 'Uint16Array':
      dtype = 5; // UINT16_TYPE;
      break;
    case 'Int32Array':
      dtype = 6; // INT32_TYPE;
      break;
    case 'Uint32Array':
      dtype = 7; // UINT32_TYPE;
      break;
    case 'Float32Array':
      dtype = 8; // FLOAT32_TYPE;
      break;
    case 'Float64Array':
      dtype = 9; // FLOAT64_TYPE;
      break;
    case 'ArrayBuffer':
      dtype = 3;
      break;
    default:
      dtype = 3; // UINT8CLAMPED_TYPE;
      break;
  }
  return dtype;
});

EM_JS(int, hiwire_subarray, (int idarr, int start, int end), {
  var jsarr = Module.hiwire_get_value(idarr);
  var jssub = jsarr.subarray(start, end);
  return Module.hiwire_new_value(jssub);
});
