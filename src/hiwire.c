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

EM_JS(int, hiwire_string_utf8_length, (int ptr, int len), {
  var bytes = new Uint8Array(Module.HEAPU8.buffer, ptr, len);
  var jsval = new TextDecoder('utf-8').decode(bytes);
  return Module.hiwire_new_value(jsval);
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

EM_JS(int, hiwire_throw_error, (int idmsg), {
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

EM_JS(int, hiwire_get_member_int, (int idobj, int idx), {
  var jsobj = Module.hiwire_get_value(idobj);
  return Module.hiwire_new_value(jsobj[idx]);
});

EM_JS(void, hiwire_set_member_int, (int idobj, int idx, int idval), {
  Module.hiwire_get_value(idobj)[idx] = Module.hiwire_get_value(idval);
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

EM_JS(void, hiwire_get_length, (int idobj), {
  return Module.hiwire_get_value(idobj).length;
});

EM_JS(void, hiwire_is_function, (int idobj), {
  // clang-format off
  return typeof Module.hiwire_get_value(idobj) === 'function';
  // clang-format on
});

EM_JS(void, hiwire_to_string, (int idobj), {
  return Module.hiwire_new_value(Module.hiwire_get_value(idobj).toString());
});
