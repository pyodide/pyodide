#include <emscripten.h>

// TODO: Use consistent naming so it's clear what's an id and what's a concrete value

EM_JS(void, hiwire_setup, (), {
  var hiwire = {
    objects: {},
    id_src: 1
  };

  Module.hiwire_new_value = function(val) {
    var objects = hiwire.objects;
    while (hiwire.id_src in objects) {
      hiwire.id_src = (hiwire.id_src + 1) % 0x8fffffff;
    }
    var id = hiwire.id_src;
    objects[id] = val;
    hiwire.id_src = (hiwire.id_src + 1) % 0x8fffffff;
    return id;
  };

  Module.hiwire_get_value = function(id) {
    return hiwire.objects[id];
  };

  Module.hiwire_decref = function(id) {
    var objects = hiwire.objects;
    delete objects[id];
  };
});

EM_JS(int, hiwire_incref, (int id), {
  return Module.hiwire_new_value(Module.hiwire_get_value(id));
});

EM_JS(void, hiwire_decref, (int id), {
  Module.hiwire_decref(id);
});

EM_JS(int, hiwire_int, (int value), {
  return Module.hiwire_new_value(value);
});

EM_JS(int, hiwire_double, (double value), {
  return Module.hiwire_new_value(value);
});

EM_JS(int, hiwire_string_utf8_length, (int pointer, int length), {
  var bytes = new Uint8Array(Module.HEAPU8.buffer, pointer, length);
  var value = new TextDecoder('utf-8').decode(bytes);
  return Module.hiwire_new_value(value);
});

EM_JS(int, hiwire_string_utf8, (int pointer), {
  return Module.hiwire_new_value(UTF8ToString(pointer));
});

EM_JS(int, hiwire_bytes, (int pointer, int length), {
  var bytes = new Uint8Array(Module.HEAPU8.buffer, pointer, length);
  return Module.hiwire_new_value(bytes);
});

EM_JS(int, hiwire_undefined, (), {
  return Module.hiwire_new_value(undefined);
});

EM_JS(int, hiwire_null, (), {
  return Module.hiwire_new_value(null);
});

EM_JS(int, hiwire_true, (), {
  return Module.hiwire_new_value(true);
});

EM_JS(int, hiwire_false, (), {
  return Module.hiwire_new_value(false);
});

EM_JS(int, hiwire_throw_error, (int id), {
  var msg = Module.hiwire_get_value(id);
  Module.hiwire_decref(id);
  throw new Error(msg);
});

EM_JS(int, hiwire_array, (), {
  return Module.hiwire_new_value([]);
});

EM_JS(void, hiwire_push_array, (int id, int val), {
  Module.hiwire_get_value(id).push(Module.hiwire_get_value(val));
});

EM_JS(int, hiwire_object, (), {
  return Module.hiwire_new_value({});
});

EM_JS(void, hiwire_push_object_pair, (int id, int key, int val), {
  var jsobj = Module.hiwire_get_value(id);
  var jskey = Module.hiwire_get_value(key);
  var jsval = Module.hiwire_get_value(val);
  jsobj[jskey] = jsval;
});

EM_JS(int, hiwire_get_global, (int ptr), {
  var idx = UTF8ToString(ptr);
  return Module.hiwire_new_value(window[idx]);
});

EM_JS(int, hiwire_get_member_string, (int ptr, int key), {
  var jskey = UTF8ToString(key);
  var jsobj = Module.hiwire_get_value(ptr);
  return Module.hiwire_new_value(jsobj[jskey]);
});

EM_JS(void, hiwire_set_member_string, (int ptr, int key, int val), {
  var jskey = UTF8ToString(key);
  Module.hiwire_get_value(ptr)[jskey] = Module.hiwire_get_value(val);
});

EM_JS(int, hiwire_get_member_int, (int ptr, int idx), {
  var jsobj = Module.hiwire_get_value(ptr);
  return Module.hiwire_new_value(jsobj[idx]);
});

EM_JS(void, hiwire_set_member_int, (int ptr, int idx, int val), {
  Module.hiwire_get_value(ptr)[idx] = Module.hiwire_get_value(val);
});

EM_JS(void, hiwire_call, (int ptr, int args), {
  var jsargs = Module.hiwire_get_value(args);
  var callable = Module.hiwire_get_value(ptr);
  return Module.hiwire_new_value(callable.apply(callable, jsargs));
});

EM_JS(void, hiwire_call_member, (int ptr, int name, int args), {
  var jsname = UTF8ToString(name);
  var jsargs = Module.hiwire_get_value(args);
  var callable = Module.hiwire_get_value(ptr);
  return Module.hiwire_new_value(callable[jsname].apply(callable, jsargs));
});

EM_JS(void, hiwire_new, (int ptr, int args), {
  var jsargs = Module.hiwire_get_value(args);
  var callable = Module.hiwire_get_value(ptr);
  return Module.hiwire_new_value(new (Function.prototype.bind.apply(callable, jsargs)));
});

EM_JS(void, hiwire_length, (int ptr), {
  return Module.hiwire_get_value(ptr).length;
});

EM_JS(void, hiwire_is_function, (int ptr), {
  return typeof Module.hiwire_get_value(ptr) === 'function';
});

EM_JS(void, hiwire_to_string, (int ptr), {
  return Module.hiwire_new_value(Module.hiwire_get_value(ptr).toString());
});
