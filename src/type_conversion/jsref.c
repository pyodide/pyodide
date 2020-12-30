#include <emscripten.h>

#include "jsref.h"

JsRef
Js_error()
{
  return Js_ERROR;
}

JsRef
Js_undefined()
{
  return Js_UNDEFINED;
}

JsRef
Js_null()
{
  return Js_NULL;
}

JsRef
Js_true()
{
  return Js_TRUE;
}

JsRef
Js_false()
{
  return Js_FALSE;
}

JsRef
Js_bool(bool boolean)
{
  return boolean ? Js_true() : Js_false();
}

EM_JS(int, Js_init, (), {
  let _jsref = { objects : new Map(), counter : 1 };
  Module.jsref = {};
  Module.jsref.ERROR = _Js_error();
  Module.jsref.UNDEFINED = _Js_undefined();
  Module.jsref.NULL = _Js_null();
  Module.jsref.TRUE = _Js_true();
  Module.jsref.FALSE = _Js_false();

  _jsref.objects.set(Module.jsref.UNDEFINED, undefined);
  _jsref.objects.set(Module.jsref.NULL, null);
  _jsref.objects.set(Module.jsref.TRUE, true);
  _jsref.objects.set(Module.jsref.FALSE, false);

  Module.jsref.new_value = function(jsval)
  {
    // Should we guard against duplicating standard values?
    // Probably not worth it for performance: it's harmless to ocassionally
    // duplicate. Maybe in test builds we could raise if jsval is a standard
    // value?
    while (_jsref.objects.has(_jsref.counter)) {
      _jsref.counter = (_jsref.counter + 1) & 0x7fffffff;
    }
    let idval = _jsref.counter;
    _jsref.objects.set(idval, jsval);
    _jsref.counter = (_jsref.counter + 1) & 0x7fffffff;
    return idval;
  };

  Module.jsref.get_value = function(idval)
  {
    if (!idval) {
      throw new Error("Argument to hiwire.get_value is undefined");
    }
    if (!_jsref.objects.has(idval)) {
      throw new Error(`Undefined id $ { idval }`);
    }
    return _jsref.objects.get(idval);
  };

  Module.jsref.decref = function(idval)
  {
    if (idval < 0) {
      return;
    }
    _jsref.objects.delete(idval);
  };
  return 0;
});

EM_JS(JsRef, Js_incref, (JsRef idval), {
  if (idval < 0) {
    return;
  }
  return Module.jsref.new_value(Module.jsref.get_value(idval));
});

EM_JS(void, Js_decref, (JsRef idval), { Module.jsref.decref(idval); });

EM_JS(JsRef, Js_int, (int val), { return Module.jsref.new_value(val); });

EM_JS(JsRef, Js_double, (double val), { return Module.jsref.new_value(val); });

EM_JS(JsRef, Js_string_ucs4, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr / 4;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(Module.HEAPU32[idx + i]);
  }
  return Module.jsref.new_value(jsstr);
});

EM_JS(JsRef, Js_string_ucs2, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr / 2;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU16[idx + i]);
  }
  return Module.jsref.new_value(jsstr);
});

EM_JS(JsRef, Js_string_ucs1, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU8[idx + i]);
  }
  return Module.jsref.new_value(jsstr);
});

EM_JS(JsRef, Js_string_utf8, (const char* ptr), {
  return Module.jsref.new_value(UTF8ToString(ptr));
});

EM_JS(JsRef, Js_string_ascii, (const char* ptr), {
  return Module.jsref.new_value(AsciiToString(ptr));
});

EM_JS(JsRef, Js_bytes, (char* ptr, int len), {
  var bytes = new Uint8ClampedArray(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(bytes);
});

EM_JS(JsRef, Js_int8array, (i8 * ptr, int len), {
  var array = new Int8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(array);
})

EM_JS(JsRef, Js_uint8array, (u8 * ptr, int len), {
  var array = new Uint8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(array);
})

EM_JS(JsRef, Js_int16array, (i16 * ptr, int len), {
  var array = new Int16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(array);
})

EM_JS(JsRef, Js_uint16array, (u16 * ptr, int len), {
  var array = new Uint16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(array);
})

EM_JS(JsRef, Js_int32array, (i32 * ptr, int len), {
  var array = new Int32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(array);
})

EM_JS(JsRef, Js_uint32array, (u32 * ptr, int len), {
  var array = new Uint32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(array);
})

EM_JS(JsRef, Js_float32array, (f32 * ptr, int len), {
  var array = new Float32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(array);
})

EM_JS(JsRef, Js_float64array, (f64 * ptr, int len), {
  var array = new Float64Array(Module.HEAPU8.buffer, ptr, len);
  return Module.jsref.new_value(array);
})

EM_JS(void, Js_throw_error, (JsRef idmsg), {
  var jsmsg = Module.jsref.get_value(idmsg);
  Module.jsref.decref(idmsg);
  throw new Error(jsmsg);
});

EM_JS(JsRef, Js_array, (), { return Module.jsref.new_value([]); });

EM_JS(void, Js_push_array, (JsRef idarr, JsRef idval), {
  Module.jsref.get_value(idarr).push(Module.jsref.get_value(idval));
});

EM_JS(JsRef, Js_object, (), { return Module.jsref.new_value({}); });

EM_JS(void, Js_push_object_pair, (JsRef idobj, JsRef idkey, JsRef idval), {
  var jsobj = Module.jsref.get_value(idobj);
  var jskey = Module.jsref.get_value(idkey);
  var jsval = Module.jsref.get_value(idval);
  jsobj[jskey] = jsval;
});

EM_JS(JsRef, Js_get_global, (const char* ptrname), {
  var jsname = UTF8ToString(ptrname);
  if (jsname in self) {
    return Module.jsref.new_value(self[jsname]);
  } else {
    return Module.jsref.ERROR;
  }
});

EM_JS(JsRef, Js_get_member_string, (JsRef idobj, const char* ptrkey), {
  var jsobj = Module.jsref.get_value(idobj);
  var jskey = UTF8ToString(ptrkey);
  if (jskey in jsobj) {
    return Module.jsref.new_value(jsobj[jskey]);
  } else {
    return Module.jsref.ERROR;
  }
});

EM_JS(void,
      Js_set_member_string,
      (JsRef idobj, const char* ptrkey, JsRef idval),
      {
        var jsobj = Module.jsref.get_value(idobj);
        var jskey = UTF8ToString(ptrkey);
        var jsval = Module.jsref.get_value(idval);
        jsobj[jskey] = jsval;
      });

EM_JS(void, Js_delete_member_string, (JsRef idobj, const char* ptrkey), {
  var jsobj = Module.jsref.get_value(idobj);
  var jskey = UTF8ToString(ptrkey);
  delete jsobj[jskey];
});

EM_JS(JsRef, Js_get_member_int, (JsRef idobj, int idx), {
  var jsobj = Module.jsref.get_value(idobj);
  return Module.jsref.new_value(jsobj[idx]);
});

EM_JS(void, Js_set_member_int, (JsRef idobj, int idx, JsRef idval), {
  Module.jsref.get_value(idobj)[idx] = Module.jsref.get_value(idval);
});

EM_JS(JsRef, Js_get_member_obj, (JsRef idobj, JsRef ididx), {
  var jsobj = Module.jsref.get_value(idobj);
  var jsidx = Module.jsref.get_value(ididx);
  if (jsidx in jsobj) {
    return Module.jsref.new_value(jsobj[jsidx]);
  } else {
    return Module.jsref.ERROR;
  }
});

EM_JS(void, Js_set_member_obj, (JsRef idobj, JsRef ididx, JsRef idval), {
  var jsobj = Module.jsref.get_value(idobj);
  var jsidx = Module.jsref.get_value(ididx);
  var jsval = Module.jsref.get_value(idval);
  jsobj[jsidx] = jsval;
});

EM_JS(void, Js_delete_member_obj, (JsRef idobj, JsRef ididx), {
  var jsobj = Module.jsref.get_value(idobj);
  var jsidx = Module.jsref.get_value(ididx);
  delete jsobj[jsidx];
});

EM_JS(JsRef, Js_dir, (JsRef idobj), {
  var jsobj = Module.jsref.get_value(idobj);
  var result = [];
  do {
    result.push.apply(result, Object.getOwnPropertyNames(jsobj));
  } while ((jsobj = Object.getPrototypeOf(jsobj)));
  return Module.jsref.new_value(result);
});

EM_JS(JsRef, Js_call, (JsRef idfunc, JsRef idargs), {
  var jsfunc = Module.jsref.get_value(idfunc);
  var jsargs = Module.jsref.get_value(idargs);
  return Module.jsref.new_value(jsfunc.apply(jsfunc, jsargs));
});

EM_JS(JsRef, Js_call_member, (JsRef idobj, const char* ptrname, JsRef idargs), {
  var jsobj = Module.jsref.get_value(idobj);
  var jsname = UTF8ToString(ptrname);
  var jsargs = Module.jsref.get_value(idargs);
  return Module.jsref.new_value(jsobj[jsname].apply(jsobj, jsargs));
});

EM_JS(JsRef, Js_new, (JsRef idobj, JsRef idargs), {
  function newCall(Cls)
  {
    return new (Function.prototype.bind.apply(Cls, arguments));
  }
  var jsobj = Module.jsref.get_value(idobj);
  var jsargs = Module.jsref.get_value(idargs);
  jsargs.unshift(jsobj);
  return Module.jsref.new_value(newCall.apply(newCall, jsargs));
});

EM_JS(int, Js_get_length, (JsRef idobj), {
  return Module.jsref.get_value(idobj).length;
});

EM_JS(bool, Js_get_bool, (JsRef idobj), {
  var val = Module.jsref.get_value(idobj);
  // clang-format off
  return (val && (val.length === undefined || val.length)) ? 1 : 0;
  // clang-format on
});

EM_JS(bool, Js_is_function, (JsRef idobj), {
  // clang-format off
  return typeof Module.jsref.get_value(idobj) === 'function';
  // clang-format on
});

EM_JS(JsRef, Js_to_string, (JsRef idobj), {
  return Module.jsref.new_value(Module.jsref.get_value(idobj).toString());
});

EM_JS(JsRef, Js_typeof, (JsRef idobj), {
  return Module.jsref.new_value(typeof Module.jsref.get_value(idobj));
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS(bool, Js_##name, (JsRef ida, JsRef idb), {                             \
    return (Module.jsref.get_value(ida) op Module.jsref.get_value(idb)) ? 1    \
                                                                        : 0;   \
  })

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
MAKE_OPERATOR(equal, ==);
MAKE_OPERATOR(not_equal, !=);
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

EM_JS(JsRef, Js_next, (JsRef idobj), {
  // clang-format off
  if (idobj === Module.jsref.UNDEFINED) {
    return Module.jsref.ERROR;
  }

  var jsobj = Module.jsref.get_value(idobj);
  return Module.jsref.new_value(jsobj.next());
  // clang-format on
});

EM_JS(JsRef, Js_get_iterator, (JsRef idobj), {
  // clang-format off
  if (idobj === Module.jsref.UNDEFINED) {
    return Module.jsref.ERROR;
  }

  var jsobj = Module.jsref.get_value(idobj);
  if (typeof jsobj.next === 'function') {
    return Module.jsref.new_value(jsobj);
  } else if (typeof jsobj[Symbol.iterator] === 'function') {
    return Module.jsref.new_value(jsobj[Symbol.iterator]());
  } else {
    return Module.jsref.new_value(Object.entries(jsobj)[Symbol.iterator]());
  }
  return Module.jsref.ERROR;
  // clang-format on
})

EM_JS(bool, Js_nonzero, (JsRef idobj), {
  var jsobj = Module.jsref.get_value(idobj);
  // TODO: should this be !== 0?
  return (jsobj != 0) ? 1 : 0;
});

EM_JS(bool, Js_is_typedarray, (JsRef idobj), {
  var jsobj = Module.jsref.get_value(idobj);
  // clang-format off
  return (jsobj['byteLength'] !== undefined) ? 1 : 0;
  // clang-format on
});

EM_JS(bool, Js_is_on_wasm_heap, (JsRef idobj), {
  var jsobj = Module.jsref.get_value(idobj);
  // clang-format off
  return (jsobj.buffer === Module.HEAPU8.buffer) ? 1 : 0;
  // clang-format on
});

EM_JS(int, Js_get_byteOffset, (JsRef idobj), {
  var jsobj = Module.jsref.get_value(idobj);
  return jsobj['byteOffset'];
});

EM_JS(int, Js_get_byteLength, (JsRef idobj), {
  var jsobj = Module.jsref.get_value(idobj);
  return jsobj['byteLength'];
});

EM_JS(void, Js_copy_to_ptr, (JsRef idobj, int ptr), {
  var jsobj = Module.jsref.get_value(idobj);
  // clang-format off
  var buffer = (jsobj['buffer'] !== undefined) ? jsobj.buffer : jsobj;
  // clang-format on
  Module.HEAPU8.set(new Uint8Array(buffer), ptr);
});

EM_JS(int, Js_get_dtype, (JsRef idobj), {
  var jsobj = Module.jsref.get_value(idobj);
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

EM_JS(JsRef, Js_subarray, (JsRef idarr, int start, int end), {
  var jsarr = Module.jsref.get_value(idarr);
  var jssub = jsarr.subarray(start, end);
  return Module.jsref.new_value(jssub);
});
