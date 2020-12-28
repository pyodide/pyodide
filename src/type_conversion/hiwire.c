#include <emscripten.h>

#include "hiwire.h"

HwObject
hiwire_error()
{
  return HW_ERROR;
}

HwObject
hiwire_undefined()
{
  return HW_UNDEFINED;
}

HwObject
hiwire_null()
{
  return HW_NULL;
}

HwObject
hiwire_true()
{
  return HW_TRUE;
}

HwObject
hiwire_false()
{
  return HW_FALSE;
}

HwObject
hiwire_bool(bool boolean)
{
  return boolean ? hiwire_true() : hiwire_false();
}

EM_JS(void, hiwire_setup, (), {
  let _hiwire = { objects : new Map(), counter : 1 };
  Module.hiwire = {};
  Module.hiwire.ERROR = _hiwire_error();
  Module.hiwire.UNDEFINED = _hiwire_undefined();
  Module.hiwire.NULL = _hiwire_null();
  Module.hiwire.TRUE = _hiwire_true();
  Module.hiwire.FALSE = _hiwire_false();

  _hiwire.objects.set(Module.hiwire.UNDEFINED, undefined);
  _hiwire.objects.set(Module.hiwire.NULL, null);
  _hiwire.objects.set(Module.hiwire.TRUE, true);
  _hiwire.objects.set(Module.hiwire.FALSE, false);

  Module.hiwire.new_value = function(jsval)
  {
    // Should we guard against duplicating standard values?
    // Probably not worth it for performance: it's harmless to ocassionally
    // duplicate. Maybe in test builds we could raise if jsval is a standard
    // value?
    while (_hiwire.objects.has(_hiwire.counter)) {
      _hiwire.counter = (_hiwire.counter + 1) & 0x7fffffff;
    }
    let idval = _hiwire.counter;
    _hiwire.objects.set(idval, jsval);
    _hiwire.counter = (_hiwire.counter + 1) & 0x7fffffff;
    return idval;
  };

  Module.hiwire.get_value = function(idval)
  {
    if (!idval) {
      throw new Error("Argument to hiwire.get_value is undefined");
    }
    if (!_hiwire.objects.has(idval)) {
      throw new Error(`Undefined id $ { idval }`);
    }
    return _hiwire.objects.get(idval);
  };

  Module.hiwire.decref = function(idval)
  {
    if (idval < 0) {
      return;
    }
    _hiwire.objects.delete(idval);
  };
});

EM_JS(HwObject, hiwire_incref, (HwObject idval), {
  if (idval < 0) {
    return;
  }
  return Module.hiwire.new_value(Module.hiwire.get_value(idval));
});

EM_JS(void, hiwire_decref, (HwObject idval), { Module.hiwire.decref(idval); });

EM_JS(HwObject, hiwire_int, (int val), {
  return Module.hiwire.new_value(val);
});

EM_JS(HwObject, hiwire_double, (double val), {
  return Module.hiwire.new_value(val);
});

EM_JS(HwObject, hiwire_string_ucs4, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr / 4;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(Module.HEAPU32[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(HwObject, hiwire_string_ucs2, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr / 2;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU16[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(HwObject, hiwire_string_ucs1, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU8[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(HwObject, hiwire_string_utf8, (const char* ptr), {
  return Module.hiwire.new_value(UTF8ToString(ptr));
});

EM_JS(HwObject, hiwire_string_ascii, (const char* ptr), {
  return Module.hiwire.new_value(AsciiToString(ptr));
});

EM_JS(HwObject, hiwire_bytes, (char* ptr, int len), {
  var bytes = new Uint8ClampedArray(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(bytes);
});

EM_JS(HwObject, hiwire_int8array, (i8 * ptr, int len), {
  var array = new Int8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(HwObject, hiwire_uint8array, (u8 * ptr, int len), {
  var array = new Uint8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(HwObject, hiwire_int16array, (i16 * ptr, int len), {
  var array = new Int16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(HwObject, hiwire_uint16array, (u16 * ptr, int len), {
  var array = new Uint16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(HwObject, hiwire_int32array, (i32 * ptr, int len), {
  var array = new Int32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(HwObject, hiwire_uint32array, (u32 * ptr, int len), {
  var array = new Uint32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(HwObject, hiwire_float32array, (f32 * ptr, int len), {
  var array = new Float32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(HwObject, hiwire_float64array, (f64 * ptr, int len), {
  var array = new Float64Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(void, hiwire_throw_error, (HwObject idmsg), {
  var jsmsg = Module.hiwire.get_value(idmsg);
  Module.hiwire.decref(idmsg);
  throw new Error(jsmsg);
});

EM_JS(HwObject, hiwire_array, (), { return Module.hiwire.new_value([]); });

EM_JS(void, hiwire_push_array, (HwObject idarr, HwObject idval), {
  Module.hiwire.get_value(idarr).push(Module.hiwire.get_value(idval));
});

EM_JS(HwObject, hiwire_object, (), { return Module.hiwire.new_value({}); });

EM_JS(void,
      hiwire_push_object_pair,
      (HwObject idobj, HwObject idkey, HwObject idval),
      {
        var jsobj = Module.hiwire.get_value(idobj);
        var jskey = Module.hiwire.get_value(idkey);
        var jsval = Module.hiwire.get_value(idval);
        jsobj[jskey] = jsval;
      });

EM_JS(HwObject, hiwire_get_global, (const char* ptrname), {
  var jsname = UTF8ToString(ptrname);
  if (jsname in self) {
    return Module.hiwire.new_value(self[jsname]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS(HwObject,
      hiwire_get_member_string,
      (HwObject idobj, const char* ptrkey),
      {
        var jsobj = Module.hiwire.get_value(idobj);
        var jskey = UTF8ToString(ptrkey);
        if (jskey in jsobj) {
          return Module.hiwire.new_value(jsobj[jskey]);
        } else {
          return Module.hiwire.ERROR;
        }
      });

EM_JS(void,
      hiwire_set_member_string,
      (HwObject idobj, const char* ptrkey, HwObject idval),
      {
        var jsobj = Module.hiwire.get_value(idobj);
        var jskey = UTF8ToString(ptrkey);
        var jsval = Module.hiwire.get_value(idval);
        jsobj[jskey] = jsval;
      });

EM_JS(void, hiwire_delete_member_string, (HwObject idobj, const char* ptrkey), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jskey = UTF8ToString(ptrkey);
  delete jsobj[jskey];
});

EM_JS(HwObject, hiwire_get_member_int, (HwObject idobj, int idx), {
  var jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(jsobj[idx]);
});

EM_JS(void, hiwire_set_member_int, (HwObject idobj, int idx, HwObject idval), {
  Module.hiwire.get_value(idobj)[idx] = Module.hiwire.get_value(idval);
});

EM_JS(HwObject, hiwire_get_member_obj, (HwObject idobj, HwObject ididx), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsidx = Module.hiwire.get_value(ididx);
  if (jsidx in jsobj) {
    return Module.hiwire.new_value(jsobj[jsidx]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS(void,
      hiwire_set_member_obj,
      (HwObject idobj, HwObject ididx, HwObject idval),
      {
        var jsobj = Module.hiwire.get_value(idobj);
        var jsidx = Module.hiwire.get_value(ididx);
        var jsval = Module.hiwire.get_value(idval);
        jsobj[jsidx] = jsval;
      });

EM_JS(void, hiwire_delete_member_obj, (HwObject idobj, HwObject ididx), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsidx = Module.hiwire.get_value(ididx);
  delete jsobj[jsidx];
});

EM_JS(HwObject, hiwire_dir, (HwObject idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  var result = [];
  do {
    result.push.apply(result, Object.getOwnPropertyNames(jsobj));
  } while ((jsobj = Object.getPrototypeOf(jsobj)));
  return Module.hiwire.new_value(result);
});

EM_JS(HwObject, hiwire_call, (HwObject idfunc, HwObject idargs), {
  var jsfunc = Module.hiwire.get_value(idfunc);
  var jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(jsfunc.apply(jsfunc, jsargs));
});

EM_JS(HwObject,
      hiwire_call_member,
      (HwObject idobj, const char* ptrname, HwObject idargs),
      {
        var jsobj = Module.hiwire.get_value(idobj);
        var jsname = UTF8ToString(ptrname);
        var jsargs = Module.hiwire.get_value(idargs);
        return Module.hiwire.new_value(jsobj[jsname].apply(jsobj, jsargs));
      });

EM_JS(HwObject, hiwire_new, (HwObject idobj, HwObject idargs), {
  function newCall(Cls)
  {
    return new (Function.prototype.bind.apply(Cls, arguments));
  }
  var jsobj = Module.hiwire.get_value(idobj);
  var jsargs = Module.hiwire.get_value(idargs);
  jsargs.unshift(jsobj);
  return Module.hiwire.new_value(newCall.apply(newCall, jsargs));
});

EM_JS(int, hiwire_get_length, (HwObject idobj), {
  return Module.hiwire.get_value(idobj).length;
});

EM_JS(bool, hiwire_get_bool, (HwObject idobj), {
  var val = Module.hiwire.get_value(idobj);
  // clang-format off
  return (val && (val.length === undefined || val.length)) ? 1 : 0;
  // clang-format on
});

EM_JS(bool, hiwire_is_function, (HwObject idobj), {
  // clang-format off
  return typeof Module.hiwire.get_value(idobj) === 'function';
  // clang-format on
});

EM_JS(HwObject, hiwire_to_string, (HwObject idobj), {
  return Module.hiwire.new_value(Module.hiwire.get_value(idobj).toString());
});

EM_JS(HwObject, hiwire_typeof, (HwObject idobj), {
  return Module.hiwire.new_value(typeof Module.hiwire.get_value(idobj));
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS(bool, hiwire_##name, (HwObject ida, HwObject idb), {                   \
    return (Module.hiwire.get_value(ida) op Module.hiwire.get_value(idb)) ? 1  \
                                                                          : 0; \
  })

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
MAKE_OPERATOR(equal, ==);
MAKE_OPERATOR(not_equal, !=);
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

EM_JS(HwObject, hiwire_next, (HwObject idobj), {
  // clang-format off
  if (idobj === Module.hiwire.UNDEFINED) {
    return Module.hiwire.ERROR;
  }

  var jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(jsobj.next());
  // clang-format on
});

EM_JS(HwObject, hiwire_get_iterator, (HwObject idobj), {
  // clang-format off
  if (idobj === Module.hiwire.UNDEFINED) {
    return Module.hiwire.ERROR;
  }

  var jsobj = Module.hiwire.get_value(idobj);
  if (typeof jsobj.next === 'function') {
    return Module.hiwire.new_value(jsobj);
  } else if (typeof jsobj[Symbol.iterator] === 'function') {
    return Module.hiwire.new_value(jsobj[Symbol.iterator]());
  } else {
    return Module.hiwire.new_value(Object.entries(jsobj)[Symbol.iterator]());
  }
  return Module.hiwire.ERROR;
  // clang-format on
})

EM_JS(bool, hiwire_nonzero, (HwObject idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // TODO: should this be !== 0?
  return (jsobj != 0) ? 1 : 0;
});

EM_JS(bool, hiwire_is_typedarray, (HwObject idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return (jsobj['byteLength'] !== undefined) ? 1 : 0;
  // clang-format on
});

EM_JS(bool, hiwire_is_on_wasm_heap, (HwObject idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return (jsobj.buffer === Module.HEAPU8.buffer) ? 1 : 0;
  // clang-format on
});

EM_JS(int, hiwire_get_byteOffset, (HwObject idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteOffset'];
});

EM_JS(int, hiwire_get_byteLength, (HwObject idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteLength'];
});

EM_JS(void, hiwire_copy_to_ptr, (HwObject idobj, int ptr), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  var buffer = (jsobj['buffer'] !== undefined) ? jsobj.buffer : jsobj;
  // clang-format on
  Module.HEAPU8.set(new Uint8Array(buffer), ptr);
});

EM_JS(int, hiwire_get_dtype, (HwObject idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
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

EM_JS(HwObject, hiwire_subarray, (HwObject idarr, int start, int end), {
  var jsarr = Module.hiwire.get_value(idarr);
  var jssub = jsarr.subarray(start, end);
  return Module.hiwire.new_value(jssub);
});
