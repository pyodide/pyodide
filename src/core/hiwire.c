#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"

JsRef
hiwire_undefined()
{
  return Js_UNDEFINED;
}

JsRef
hiwire_null()
{
  return Js_NULL;
}

JsRef
hiwire_true()
{
  return Js_TRUE;
}

JsRef
hiwire_false()
{
  return Js_FALSE;
}

JsRef
hiwire_bool(bool boolean)
{
  return boolean ? hiwire_true() : hiwire_false();
}

EM_JS(int, hiwire_init, (), {
  let _hiwire = {
    objects : new Map(),
    // counter is used to allocate keys for the objects map.
    // We use even integers to represent singleton constants which we won't
    // reference count. We only want to allocate odd keys so we start at 1 and
    // step by 2. We use a native uint32 for our counter, so counter
    // automatically overflows back to 1 if it ever gets up to the max u32 =
    // 2^{31} - 1. This ensures we can keep recycling keys even for very long
    // sessions. (Also the native u32 is faster since javascript won't convert
    // it to a float.)
    // 0 == C NULL is an error code for compatibility with Python calling
    // conventions.
    counter : new Uint32Array([1])
  };
  Module.hiwire = {};
  Module.hiwire.UNDEFINED = _hiwire_undefined();
  Module.hiwire.JSNULL = _hiwire_null();
  Module.hiwire.TRUE = _hiwire_true();
  Module.hiwire.FALSE = _hiwire_false();

  _hiwire.objects.set(Module.hiwire.UNDEFINED, undefined);
  _hiwire.objects.set(Module.hiwire.JSNULL, null);
  _hiwire.objects.set(Module.hiwire.TRUE, true);
  _hiwire.objects.set(Module.hiwire.FALSE, false);

  Module.hiwire.new_value = function(jsval)
  {
    // Should we guard against duplicating standard values?
    // Probably not worth it for performance: it's harmless to ocassionally
    // duplicate. Maybe in test builds we could raise if jsval is a standard
    // value?
    while (_hiwire.objects.has(_hiwire.counter[0])) {
      // Increment by two here (and below) because even integers are reserved
      // for singleton constants
      _hiwire.counter[0] += 2;
    }
    let idval = _hiwire.counter[0];
    _hiwire.objects.set(idval, jsval);
    _hiwire.counter[0] += 2;
    return idval;
  };

  Module.hiwire.get_value = function(idval)
  {
    if (!idval) {
      // This might have happened because the error indicator is set. Let's
      // check.
      if (_PyErr_Occurred()) {
        // This will lead to a more helpful error message.
        _pythonexc2js();
      }
      throw new Error("Argument to hiwire.get_value is undefined");
    }
    if (!_hiwire.objects.has(idval)) {
      // clang-format off
      throw new Error(`Undefined id ${ idval }`);
      // clang-format on
    }
    return _hiwire.objects.get(idval);
  };

  Module.hiwire.decref = function(idval)
  {
    // clang-format off
    if ((idval & 1) === 0) {
      // clang-format on
      // least significant bit unset ==> idval is a singleton.
      // We don't reference count singletons.
      return;
    }
    _hiwire.objects.delete(idval);
  };

  Module.hiwire.pop_value = function(idval)
  {
    let result = Module.hiwire.get_value(idval);
    Module.hiwire.decref(idval);
    return result;
  };

  Module.hiwire.isPromise = function(obj)
  {
    // clang-format off
    return (!!obj) && typeof obj.then === 'function';
    // clang-format on
  };
  return 0;
});

EM_JS_REF(JsRef, hiwire_incref, (JsRef idval), {
  // clang-format off
  if ((idval & 1) === 0) {
    // least significant bit unset ==> idval is a singleton.
    // We don't reference count singletons.
    // clang-format on
    return;
  }
  return Module.hiwire.new_value(Module.hiwire.get_value(idval));
});

EM_JS_NUM(errcode, hiwire_decref, (JsRef idval), {
  Module.hiwire.decref(idval);
});

EM_JS_REF(JsRef, hiwire_int, (int val), {
  return Module.hiwire.new_value(val);
});

EM_JS_REF(JsRef, hiwire_double, (double val), {
  return Module.hiwire.new_value(val);
});

EM_JS_REF(JsRef, hiwire_string_ucs4, (const char* ptr, int len), {
  let jsstr = "";
  let idx = ptr / 4;
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(Module.HEAPU32[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_ucs2, (const char* ptr, int len), {
  let jsstr = "";
  let idx = ptr / 2;
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU16[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_ucs1, (const char* ptr, int len), {
  let jsstr = "";
  let idx = ptr;
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU8[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_utf8, (const char* ptr), {
  return Module.hiwire.new_value(UTF8ToString(ptr));
});

EM_JS_REF(JsRef, hiwire_string_ascii, (const char* ptr), {
  return Module.hiwire.new_value(AsciiToString(ptr));
});

EM_JS_REF(JsRef, hiwire_bytes, (char* ptr, int len), {
  let bytes = new Uint8ClampedArray(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(bytes);
});

EM_JS_REF(JsRef, hiwire_int8array, (i8 * ptr, int len), {
  let array = new Int8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS_REF(JsRef, hiwire_uint8array, (u8 * ptr, int len), {
  let array = new Uint8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS_REF(JsRef, hiwire_int16array, (i16 * ptr, int len), {
  let array = new Int16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS_REF(JsRef, hiwire_uint16array, (u16 * ptr, int len), {
  let array = new Uint16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS_REF(JsRef, hiwire_int32array, (i32 * ptr, int len), {
  let array = new Int32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS_REF(JsRef, hiwire_uint32array, (u32 * ptr, int len), {
  let array = new Uint32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS_REF(JsRef, hiwire_float32array, (f32 * ptr, int len), {
  let array = new Float32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS_REF(JsRef, hiwire_float64array, (f64 * ptr, int len), {
  let array = new Float64Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(void _Py_NO_RETURN, hiwire_throw_error, (JsRef idmsg), {
  let jsmsg = Module.hiwire.get_value(idmsg);
  Module.hiwire.decref(idmsg);
  throw new Error(jsmsg);
});

EM_JS_REF(JsRef, hiwire_array, (), { return Module.hiwire.new_value([]); });

EM_JS_NUM(errcode, hiwire_push_array, (JsRef idarr, JsRef idval), {
  Module.hiwire.get_value(idarr).push(Module.hiwire.get_value(idval));
});

EM_JS_REF(JsRef, hiwire_object, (), { return Module.hiwire.new_value({}); });

EM_JS_NUM(errcode,
          hiwire_push_object_pair,
          (JsRef idobj, JsRef idkey, JsRef idval),
          {
            let jsobj = Module.hiwire.get_value(idobj);
            let jskey = Module.hiwire.get_value(idkey);
            let jsval = Module.hiwire.get_value(idval);
            jsobj[jskey] = jsval;
          });

EM_JS_REF(JsRef, hiwire_get_global, (const char* ptrname), {
  let jsname = UTF8ToString(ptrname);
  if (jsname in self) {
    return Module.hiwire.new_value(self[jsname]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS_REF(JsRef, hiwire_get_member_string, (JsRef idobj, const char* ptrkey), {
  let jsobj = Module.hiwire.get_value(idobj);
  let jskey = UTF8ToString(ptrkey);
  if (jskey in jsobj) {
    return Module.hiwire.new_value(jsobj[jskey]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS_NUM(errcode,
          hiwire_set_member_string,
          (JsRef idobj, const char* ptrkey, JsRef idval),
          {
            let jsobj = Module.hiwire.get_value(idobj);
            let jskey = UTF8ToString(ptrkey);
            let jsval = Module.hiwire.get_value(idval);
            jsobj[jskey] = jsval;
          });

EM_JS_NUM(errcode,
          hiwire_delete_member_string,
          (JsRef idobj, const char* ptrkey),
          {
            let jsobj = Module.hiwire.get_value(idobj);
            let jskey = UTF8ToString(ptrkey);
            delete jsobj[jskey];
          });

EM_JS_REF(JsRef, hiwire_get_member_int, (JsRef idobj, int idx), {
  let jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(jsobj[idx]);
});

EM_JS_NUM(errcode, hiwire_set_member_int, (JsRef idobj, int idx, JsRef idval), {
  Module.hiwire.get_value(idobj)[idx] = Module.hiwire.get_value(idval);
});

EM_JS_REF(JsRef, hiwire_get_member_obj, (JsRef idobj, JsRef ididx), {
  let jsobj = Module.hiwire.get_value(idobj);
  let jsidx = Module.hiwire.get_value(ididx);
  if (jsidx in jsobj) {
    return Module.hiwire.new_value(jsobj[jsidx]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS_NUM(errcode,
          hiwire_set_member_obj,
          (JsRef idobj, JsRef ididx, JsRef idval),
          {
            let jsobj = Module.hiwire.get_value(idobj);
            let jsidx = Module.hiwire.get_value(ididx);
            let jsval = Module.hiwire.get_value(idval);
            jsobj[jsidx] = jsval;
          });

EM_JS_NUM(errcode, hiwire_delete_member_obj, (JsRef idobj, JsRef ididx), {
  let jsobj = Module.hiwire.get_value(idobj);
  let jsidx = Module.hiwire.get_value(ididx);
  delete jsobj[jsidx];
});

EM_JS_REF(JsRef, hiwire_dir, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  let result = [];
  do {
    result.push(... Object.getOwnPropertyNames(jsobj));
  } while (jsobj = Object.getPrototypeOf(jsobj));
  return Module.hiwire.new_value(result);
});

EM_JS_REF(JsRef, hiwire_call, (JsRef idfunc, JsRef idargs), {
  let jsfunc = Module.hiwire.get_value(idfunc);
  let jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(jsfunc(... jsargs));
});

EM_JS_REF(JsRef,
          hiwire_call_bound,
          (JsRef idfunc, JsRef idthis, JsRef idargs),
          {
            let func = Module.hiwire.get_value(idfunc);
            let this_;
            // clang-format off
            if (idthis === 0) {
              // clang-format on
              this_ = null;
            } else {
              this_ = Module.hiwire.get_value(idthis);
            }
            let args = Module.hiwire.get_value(idargs);
            return Module.hiwire.new_value(func.apply(this_, args));
          });

EM_JS_REF(JsRef,
          hiwire_call_member,
          (JsRef idobj, const char* ptrname, JsRef idargs),
          {
            let jsobj = Module.hiwire.get_value(idobj);
            let jsname = UTF8ToString(ptrname);
            let jsargs = Module.hiwire.get_value(idargs);
            return Module.hiwire.new_value(jsobj[jsname](... jsargs));
          });

EM_JS_REF(JsRef, hiwire_new, (JsRef idobj, JsRef idargs), {
  let jsobj = Module.hiwire.get_value(idobj);
  let jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(Reflect.construct(jsobj, jsargs));
});

EM_JS_NUM(int, hiwire_get_length, (JsRef idobj), {
  return Module.hiwire.get_value(idobj).length;
});

EM_JS_NUM(bool, hiwire_get_bool, (JsRef idobj), {
  let val = Module.hiwire.get_value(idobj);
  // clang-format off
  if (!val) {
    return false;
  }
  if (val.size === 0) {
    // I think things with a size are all container types.
    return false;
  }
  if (Array.isArray(val) && val.length === 0) {
    return false;
  }
  return true;
  // clang-format on
});

EM_JS_NUM(bool, hiwire_is_pyproxy, (JsRef idobj), {
  // clang-format off
  return Module.PyProxy.isPyProxy(Module.hiwire.get_value(idobj));
  // clang-format on
});

EM_JS_NUM(bool, hiwire_is_function, (JsRef idobj), {
  // clang-format off
  return typeof Module.hiwire.get_value(idobj) === 'function';
  // clang-format on
});

EM_JS_NUM(bool, hiwire_is_error, (JsRef idobj), {
  // From https://stackoverflow.com/a/45496068
  let value = Module.hiwire.get_value(idobj);
  return !!(value && value.stack && value.message);
});

EM_JS_NUM(bool, hiwire_function_supports_kwargs, (JsRef idfunc), {
  let funcstr = Module.hiwire.get_value(idfunc).toString();
  return Module.function_supports_kwargs(funcstr);
});

EM_JS_NUM(bool, hiwire_is_promise, (JsRef idobj), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  return Module.hiwire.isPromise(obj);
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_resolve_promise, (JsRef idobj), {
  // clang-format off
  let obj = Module.hiwire.get_value(idobj);
  let result = Promise.resolve(obj);
  return Module.hiwire.new_value(result);
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_to_string, (JsRef idobj), {
  return Module.hiwire.new_value(Module.hiwire.get_value(idobj).toString());
});

EM_JS_REF(JsRef, hiwire_typeof, (JsRef idobj), {
  return Module.hiwire.new_value(typeof Module.hiwire.get_value(idobj));
});

EM_JS_REF(char*, hiwire_constructor_name, (JsRef idobj), {
  return stringToNewUTF8(Module.hiwire.get_value(idobj).constructor.name);
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS_NUM(bool, hiwire_##name, (JsRef ida, JsRef idb), {                     \
    return (Module.hiwire.get_value(ida) op Module.hiwire.get_value(idb)) ? 1  \
                                                                          : 0; \
  })

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
// clang-format off
MAKE_OPERATOR(equal, ===);
MAKE_OPERATOR(not_equal, !==);
// clang-format on
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

EM_JS_REF(int, hiwire_next, (JsRef idobj, JsRef* result_ptr), {
  // clang-format off
  let jsobj = Module.hiwire.get_value(idobj);
  let { done, value } = jsobj.next();
  let result_id = Module.hiwire.new_value(value);
  setValue(result_ptr, result_id, "i32");
  return done;
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_get_iterator, (JsRef idobj), {
  // clang-format off
  if (idobj === Module.hiwire.UNDEFINED) {
    return Module.hiwire.ERROR;
  }

  let jsobj = Module.hiwire.get_value(idobj);
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

EM_JS_NUM(bool, hiwire_is_typedarray, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return (jsobj['byteLength'] !== undefined) ? 1 : 0;
  // clang-format on
});

EM_JS_NUM(bool, hiwire_is_on_wasm_heap, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return (jsobj.buffer === Module.HEAPU8.buffer) ? 1 : 0;
  // clang-format on
});

EM_JS_NUM(int, hiwire_get_byteOffset, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteOffset'];
});

EM_JS_NUM(int, hiwire_get_byteLength, (JsRef idobj), {
  let jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteLength'];
});

EM_JS_NUM(errcode, hiwire_copy_to_ptr, (JsRef idobj, void* ptr), {
  let jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  let buffer = (jsobj['buffer'] !== undefined) ? jsobj.buffer : jsobj;
  // clang-format on
  Module.HEAPU8.set(new Uint8Array(buffer), ptr);
});

EM_JS_NUM(errcode,
          hiwire_get_dtype,
          (JsRef idobj, char** format_ptr, Py_ssize_t* size_ptr),
          {
            if (!Module.hiwire.dtype_map) {
              let alloc = stringToNewUTF8;
              Module.hiwire.dtype_map = new Map([
                [ 'Int8Array', [ alloc('b'), 1 ] ],
                [ 'Uint8Array', [ alloc('B'), 1 ] ],
                [ 'Uint8ClampedArray', [ alloc('B'), 1 ] ],
                [ 'Int16Array', [ alloc('h'), 2 ] ],
                [ 'Uint16Array', [ alloc('H'), 2 ] ],
                [ 'Int32Array', [ alloc('i'), 4 ] ],
                [ 'Uint32Array', [ alloc('I'), 4 ] ],
                [ 'Float32Array', [ alloc('f'), 4 ] ],
                [ 'Float64Array', [ alloc('d'), 8 ] ],
                [ 'ArrayBuffer', [ alloc('B'), 1 ] ], // Default to Uint8;
              ]);
            }
            let jsobj = Module.hiwire.get_value(idobj);
            let[format_utf8, size] =
              Module.hiwire.dtype_map.get(jsobj.constructor.name) || [ 0, 0 ];
            // Store results into arguments
            setValue(format_ptr, format_utf8, "i8*");
            setValue(size_ptr, size, "i32");
          });

EM_JS_REF(JsRef, hiwire_subarray, (JsRef idarr, int start, int end), {
  let jsarr = Module.hiwire.get_value(idarr);
  let jssub = jsarr.subarray(start, end);
  return Module.hiwire.new_value(jssub);
});
