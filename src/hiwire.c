#include <emscripten.h>

EM_JS(void, hiwire_setup, (), {
  var hiwire = { objects : {}, counter : 1 };

  Module.hiwire_new_value = function(jsval)
  {
    var objects = hiwire.objects;
    while (hiwire.counter in objects) {
      hiwire.counter = (hiwire.counter + 1) % 0x8fffffff;
    }
    var idval = hiwire.counter;
    objects[idval] = jsval;
    hiwire.counter = (hiwire.counter + 1) % 0x8fffffff;
    return idval;
  };

  Module.hiwire_get_value = function(idval) { return hiwire.objects[idval]; };

  Module.hiwire_decref = function(idval)
  {
    var objects = hiwire.objects;
    delete objects[idval];
  };
});

EM_JS(int, hiwire_incref, (int idval), {
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
    jsstr += String.fromCharCode(Module.HEAPU32[idx + i]);
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

EM_JS(int, hiwire_bytes, (int ptr, int len), {
  var bytes = new Uint8ClampedArray(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire_new_value(bytes);
});

EM_JS(int, hiwire_undefined, (), {
  return Module.hiwire_new_value(undefined);
});

EM_JS(int, hiwire_null, (), { return Module.hiwire_new_value(null); });

EM_JS(int, hiwire_true, (), { return Module.hiwire_new_value(true); });

EM_JS(int, hiwire_false, (), { return Module.hiwire_new_value(false); });

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
  return Module.hiwire_new_value(window[jsname]);
});

EM_JS(int, hiwire_get_member_string, (int idobj, int idkey), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jskey = UTF8ToString(idkey);
  return Module.hiwire_new_value(jsobj[jskey]);
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
  return Module.hiwire_new_value(jsobj[jsidx]);
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

EM_JS(void, hiwire_call, (int idfunc, int idargs), {
  var jsfunc = Module.hiwire_get_value(idfunc);
  var jsargs = Module.hiwire_get_value(idargs);
  return Module.hiwire_new_value(jsfunc.apply(jsfunc, jsargs));
});

EM_JS(void, hiwire_call_member, (int idobj, int ptrname, int idargs), {
  var jsobj = Module.hiwire_get_value(idobj);
  var jsname = UTF8ToString(ptrname);
  var jsargs = Module.hiwire_get_value(idargs);
  return Module.hiwire_new_value(jsobj[jsname].apply(jsobj, jsargs));
});

EM_JS(void, hiwire_new, (int idobj, int idargs), {
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
  var jsobj = Module.hiwire_get_value(idobj);
  // clang-format off
  if (jsobj.next === undefined) {
    // clang-format on
    return -1;
  }

  return Module.hiwire_new_value(jsobj.next());
});

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
  Module.HEAPU8.set(new Uint8Array(jsobj.buffer), ptr);
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
    default:
      dtype = 3; // UINT8CLAMPED_TYPE;
      break;
  }
  return dtype;
});
