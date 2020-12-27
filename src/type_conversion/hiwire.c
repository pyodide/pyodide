#include <emscripten.h>

#include "hiwire.h"

int
hiwire_error()
{
  return HW_ERROR;
}

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

int
hiwire_bool(int boolean)
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

EM_JS(int, hiwire_incref, (int idval), {
  if (idval < 0) {
    return;
  }
  return Module.hiwire.new_value(Module.hiwire.get_value(idval));
});

EM_JS(void, hiwire_decref, (int idval), { Module.hiwire.decref(idval); });

EM_JS(int, hiwire_int, (int val), { return Module.hiwire.new_value(val); });

EM_JS(int, hiwire_double, (double val), {
  return Module.hiwire.new_value(val);
});

EM_JS(int, hiwire_string_ucs4, (int ptr, int len), {
  var jsstr = "";
  var idx = ptr / 4;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(Module.HEAPU32[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(int, hiwire_string_ucs2, (int ptr, int len), {
  var jsstr = "";
  var idx = ptr / 2;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU16[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(int, hiwire_string_ucs1, (int ptr, int len), {
  var jsstr = "";
  var idx = ptr;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU8[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(int, hiwire_string_utf8, (int ptr), {
  return Module.hiwire.new_value(UTF8ToString(ptr));
});

EM_JS(int, hiwire_string_ascii, (int ptr), {
  return Module.hiwire.new_value(AsciiToString(ptr));
});

EM_JS(int, hiwire_bytes, (int ptr, int len), {
  var bytes = new Uint8ClampedArray(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(bytes);
});

EM_JS(int, hiwire_int8array, (int ptr, int len), {
  var array = new Int8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(int, hiwire_uint8array, (int ptr, int len), {
  var array = new Uint8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(int, hiwire_int16array, (int ptr, int len), {
  var array = new Int16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(int, hiwire_uint16array, (int ptr, int len), {
  var array = new Uint16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(int, hiwire_int32array, (int ptr, int len), {
  var array = new Int32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(int, hiwire_uint32array, (int ptr, int len), {
  var array = new Uint32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(int, hiwire_float32array, (int ptr, int len), {
  var array = new Float32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(int, hiwire_float64array, (int ptr, int len), {
  var array = new Float64Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(void, hiwire_throw_error, (int idmsg), {
  var jsmsg = Module.hiwire.get_value(idmsg);
  Module.hiwire.decref(idmsg);
  throw new Error(jsmsg);
});

EM_JS(int, hiwire_array, (), { return Module.hiwire.new_value([]); });

EM_JS(void, hiwire_push_array, (int idarr, int idval), {
  Module.hiwire.get_value(idarr).push(Module.hiwire.get_value(idval));
});

EM_JS(int, hiwire_object, (), { return Module.hiwire.new_value({}); });

EM_JS(void, hiwire_push_object_pair, (int idobj, int idkey, int idval), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jskey = Module.hiwire.get_value(idkey);
  var jsval = Module.hiwire.get_value(idval);
  jsobj[jskey] = jsval;
});

EM_JS(int, hiwire_get_global, (int idname), {
  var jsname = UTF8ToString(idname);
  if (jsname in self) {
    return Module.hiwire.new_value(self[jsname]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS(int, hiwire_get_member_string, (int idobj, int idkey), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jskey = UTF8ToString(idkey);
  if (jskey in jsobj) {
    return Module.hiwire.new_value(jsobj[jskey]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS(void, hiwire_set_member_string, (int idobj, int ptrkey, int idval), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jskey = UTF8ToString(ptrkey);
  var jsval = Module.hiwire.get_value(idval);
  jsobj[jskey] = jsval;
});

EM_JS(void, hiwire_delete_member_string, (int idobj, int ptrkey), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jskey = UTF8ToString(ptrkey);
  delete jsobj[jskey];
});

EM_JS(int, hiwire_get_member_int, (int idobj, int idx), {
  var jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(jsobj[idx]);
});

EM_JS(void, hiwire_set_member_int, (int idobj, int idx, int idval), {
  Module.hiwire.get_value(idobj)[idx] = Module.hiwire.get_value(idval);
});

EM_JS(int, hiwire_get_member_obj, (int idobj, int ididx), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsidx = Module.hiwire.get_value(ididx);
  if (jsidx in jsobj) {
    return Module.hiwire.new_value(jsobj[jsidx]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS(void, hiwire_set_member_obj, (int idobj, int ididx, int idval), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsidx = Module.hiwire.get_value(ididx);
  var jsval = Module.hiwire.get_value(idval);
  jsobj[jsidx] = jsval;
});

EM_JS(void, hiwire_delete_member_obj, (int idobj, int ididx), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsidx = Module.hiwire.get_value(ididx);
  delete jsobj[jsidx];
});

EM_JS(int, hiwire_dir, (int idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  var result = [];
  do {
    result.push.apply(result, Object.getOwnPropertyNames(jsobj));
  } while ((jsobj = Object.getPrototypeOf(jsobj)));
  return Module.hiwire.new_value(result);
});

EM_JS(int, hiwire_call, (int idfunc, int idargs), {
  var jsfunc = Module.hiwire.get_value(idfunc);
  var jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(jsfunc.apply(jsfunc, jsargs));
});

EM_JS(int, hiwire_call_member, (int idobj, int ptrname, int idargs), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsname = UTF8ToString(ptrname);
  var jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(jsobj[jsname].apply(jsobj, jsargs));
});

EM_JS(int, hiwire_new, (int idobj, int idargs), {
  function newCall(Cls)
  {
    return new (Function.prototype.bind.apply(Cls, arguments));
  }
  var jsobj = Module.hiwire.get_value(idobj);
  var jsargs = Module.hiwire.get_value(idargs);
  jsargs.unshift(jsobj);
  return Module.hiwire.new_value(newCall.apply(newCall, jsargs));
});

EM_JS(int, hiwire_get_length, (int idobj), {
  return Module.hiwire.get_value(idobj).length;
});

EM_JS(int, hiwire_get_bool, (int idobj), {
  var val = Module.hiwire.get_value(idobj);
  // clang-format off
  return (val && (val.length === undefined || val.length)) ? 1 : 0;
  // clang-format on
});

EM_JS(int, hiwire_is_function, (int idobj), {
  // clang-format off
  return typeof Module.hiwire.get_value(idobj) === 'function';
  // clang-format on
});

EM_JS(int, hiwire_to_string, (int idobj), {
  return Module.hiwire.new_value(Module.hiwire.get_value(idobj).toString());
});

EM_JS(int, hiwire_typeof, (int idobj), {
  return Module.hiwire.new_value(typeof Module.hiwire.get_value(idobj));
});

EM_JS(int, hiwire_constructor_name, (int idobj), {
  return Module.hiwire.new_value(
    Module.hiwire.get_value(idobj).constructor.name);
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS(int, hiwire_##name, (int ida, int idb), {                              \
    return (Module.hiwire.get_value(ida) op Module.hiwire.get_value(idb)) ? 1  \
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
  if (idobj === Module.hiwire.UNDEFINED) {
    return Module.hiwire.ERROR;
  }

  var jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(jsobj.next());
  // clang-format on
});

EM_JS(int, hiwire_get_iterator, (int idobj), {
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

EM_JS(int, hiwire_nonzero, (int idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // TODO: should this be !== 0?
  return (jsobj != 0) ? 1 : 0;
});

EM_JS(int, hiwire_is_typedarray, (int idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return (jsobj['byteLength'] !== undefined) ? 1 : 0;
  // clang-format on
});

EM_JS(int, hiwire_is_on_wasm_heap, (int idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return (jsobj.buffer === Module.HEAPU8.buffer) ? 1 : 0;
  // clang-format on
});

EM_JS(int, hiwire_get_byteOffset, (int idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteOffset'];
});

EM_JS(int, hiwire_get_byteLength, (int idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteLength'];
});

EM_JS(int, hiwire_copy_to_ptr, (int idobj, int ptr), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  var buffer = (jsobj['buffer'] !== undefined) ? jsobj.buffer : jsobj;
  // clang-format on
  Module.HEAPU8.set(new Uint8Array(buffer), ptr);
});

EM_JS(void, hiwire_get_dtype, (int idobj, int format_ptr, int size_ptr), {
  if (!Module.hiwire.dtype_map) {
    let entries = Object.entries({
      'Int8Array' : [ 'b', 1 ],
      'Uint8Array' : [ 'B', 1 ],
      'Uint8ClampedArray' : [ 'B', 1 ],
      'Int16Array' : [ "h", 2 ],
      'Uint16Array' : [ "H", 2 ],
      'Int32Array' : [ "i", 4 ],
      'Uint32Array' : [ "I", 4 ],
      'Float32Array' : [ "f", 4 ],
      'Float64Array' : [ "d", 8 ],
      'ArrayBuffer' : [ 'B', 1 ], // Default to Uint8;
    });
    Module.hiwire.dtype_map = new Map();
    for (let[key, [ format, size ]] of entries) {
      let format_utf8 =
        allocate(intArrayFromString(format), "i8", ALLOC_NORMAL);
      Module.hiwire.dtype_map.set(key, [ format, size ]);
    }
  }
  let jsobj = Module.hiwire.get_value(idobj);
  let[format, size] =
    Module.hiwire.dtype_map.get(jsobj.constructor.name) || [ 0, 0 ];
  // Store results into arguments
  setValue(format_ptr, format, "i8*");
  setValue(size_ptr, size, "i32");
});

EM_JS(int, hiwire_subarray, (int idarr, int start, int end), {
  var jsarr = Module.hiwire.get_value(idarr);
  var jssub = jsarr.subarray(start, end);
  return Module.hiwire.new_value(jssub);
});
