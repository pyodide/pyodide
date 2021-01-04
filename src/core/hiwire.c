#include <emscripten.h>

#include "hiwire.h"

JsRef
hiwire_error()
{
  return Js_ERROR;
}

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

  // Put this here so we can test it.
  Module.hiwire.function_supports_kwargs = function(funcstr)
  {
    // This is basically a finite state machine (except for paren counting)
    // Start at beginning of argspec
    let idx = funcstr.indexOf("(") + 1;
    // States:
    // START_ARG -- Start of an argument. We leave this state when we see a non
    // whitespace character.
    //    If the first nonwhitespace character we see is `{` this is an object
    //    destructuring argument. Else it's not. When we see non whitespace goto
    //    state ARG and set `arg_is_obj_dest` true if it's "{", else false.
    // ARG -- we're in the middle of an argument. Count parens. On comma, if
    // parens_depth === 0 goto state START_ARG, on quote set
    //      set quote_start and goto state QUOTE.
    // QUOTE -- We're in a quote. Record quote_start in quote_start and look for
    // a matching end quote.
    //    On end quote, goto state ARGS. If we see "\\" goto state QUOTE_ESCAPE.
    // QUOTE_ESCAPE -- unconditionally goto state QUOTE.
    // If we see a ) when parens_depth === 0, return arg_is_obj_dest.
    let START_ARG = 1;
    let ARG = 2;
    let QUOTE = 3;
    let QUOTE_ESCAPE = 4;
    let paren_depth = 0;
    let arg_start = 0;
    let arg_is_obj_dest = false;
    let quote_start = undefined;
    let state = START_ARG;
    // clang-format off
    for (i = idx; i < funcstr.length; i++) {
      let x = funcstr[i];
      if(state === QUOTE){
        switch(x){
          case quote_start:
            // found match, go back to ARG
            state = ARG;
            continue;
          case "\\":
            state = QUOTE_ESCAPE;
            continue;
          default:
            continue;
        }
      }
      if(state === QUOTE_ESCAPE){
        state = QUOTE;
        continue;
      }
      // Skip whitespace.
      if(x === " " || x === "\n" || x === "\t"){
        continue;
      }
      if(paren_depth === 0 && x === ")" && STATE !== QUOTE && STATE !== QUOTE_ESCAPE)
      {
        // We hit closing brace which ends argspec.
        // We have to handle this up here in case argspec ends in a trailing comma
        // (if we're in state START_ARG, the next check would clobber arg_is_obj_dest).
        return arg_is_obj_dest;
      }
      if(state === START_ARG){
        // Nonwhitespace character in START_ARG so now we're in state arg.
        state = ARG;
        arg_is_obj_dest = x === "{";
        // don't continue.
      }
      switch(x){
        case ",":
          if(paren_depth === 0){
            state = START_ARG;
          }
          continue;
        case "[": case "{": case "(":
          paren_depth ++;
          continue;
        case "]": case "}": case ")":
          paren_depth--;
          continue;
        case "'": case '"': case '`':
          state = QUOTE;
          quote_start = x;
          continue;
      }
    }
    // clang-format on
    // Correct exit is paren_depth === 0 && x === ")" test above.
    throw new Error("Assertion failure: this is a logic error in "
                    "hiwire_function_supports_kwargs");
  }

  return 0;
});

EM_JS(JsRef, hiwire_incref, (JsRef idval), {
  if (idval < 0) {
    return;
  }
  return Module.hiwire.new_value(Module.hiwire.get_value(idval));
});

EM_JS(void, hiwire_decref, (JsRef idval), { Module.hiwire.decref(idval); });

EM_JS(JsRef, hiwire_int, (int val), { return Module.hiwire.new_value(val); });

EM_JS(JsRef, hiwire_double, (double val), {
  return Module.hiwire.new_value(val);
});

EM_JS(JsRef, hiwire_string_ucs4, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr / 4;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(Module.HEAPU32[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(JsRef, hiwire_string_ucs2, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr / 2;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU16[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(JsRef, hiwire_string_ucs1, (const char* ptr, int len), {
  var jsstr = "";
  var idx = ptr;
  for (var i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(Module.HEAPU8[idx + i]);
  }
  return Module.hiwire.new_value(jsstr);
});

EM_JS(JsRef, hiwire_string_utf8, (const char* ptr), {
  return Module.hiwire.new_value(UTF8ToString(ptr));
});

EM_JS(JsRef, hiwire_string_ascii, (const char* ptr), {
  return Module.hiwire.new_value(AsciiToString(ptr));
});

EM_JS(JsRef, hiwire_bytes, (char* ptr, int len), {
  var bytes = new Uint8ClampedArray(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(bytes);
});

EM_JS(JsRef, hiwire_int8array, (i8 * ptr, int len), {
  var array = new Int8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(JsRef, hiwire_uint8array, (u8 * ptr, int len), {
  var array = new Uint8Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(JsRef, hiwire_int16array, (i16 * ptr, int len), {
  var array = new Int16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(JsRef, hiwire_uint16array, (u16 * ptr, int len), {
  var array = new Uint16Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(JsRef, hiwire_int32array, (i32 * ptr, int len), {
  var array = new Int32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(JsRef, hiwire_uint32array, (u32 * ptr, int len), {
  var array = new Uint32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(JsRef, hiwire_float32array, (f32 * ptr, int len), {
  var array = new Float32Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(JsRef, hiwire_float64array, (f64 * ptr, int len), {
  var array = new Float64Array(Module.HEAPU8.buffer, ptr, len);
  return Module.hiwire.new_value(array);
})

EM_JS(void, hiwire_throw_error, (JsRef idmsg), {
  var jsmsg = Module.hiwire.get_value(idmsg);
  Module.hiwire.decref(idmsg);
  throw new Error(jsmsg);
});

EM_JS(JsRef, hiwire_array, (), { return Module.hiwire.new_value([]); });

EM_JS(void, hiwire_push_array, (JsRef idarr, JsRef idval), {
  Module.hiwire.get_value(idarr).push(Module.hiwire.get_value(idval));
});

EM_JS(JsRef, hiwire_object, (), { return Module.hiwire.new_value({}); });

EM_JS(void, hiwire_push_object_pair, (JsRef idobj, JsRef idkey, JsRef idval), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jskey = Module.hiwire.get_value(idkey);
  var jsval = Module.hiwire.get_value(idval);
  jsobj[jskey] = jsval;
});

EM_JS(JsRef, hiwire_get_global, (const char* ptrname), {
  var jsname = UTF8ToString(ptrname);
  if (jsname in self) {
    return Module.hiwire.new_value(self[jsname]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS(JsRef, hiwire_get_member_string, (JsRef idobj, const char* ptrkey), {
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
      (JsRef idobj, const char* ptrkey, JsRef idval),
      {
        var jsobj = Module.hiwire.get_value(idobj);
        var jskey = UTF8ToString(ptrkey);
        var jsval = Module.hiwire.get_value(idval);
        jsobj[jskey] = jsval;
      });

EM_JS(void, hiwire_delete_member_string, (JsRef idobj, const char* ptrkey), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jskey = UTF8ToString(ptrkey);
  delete jsobj[jskey];
});

EM_JS(JsRef, hiwire_get_member_int, (JsRef idobj, int idx), {
  var jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(jsobj[idx]);
});

EM_JS(void, hiwire_set_member_int, (JsRef idobj, int idx, JsRef idval), {
  Module.hiwire.get_value(idobj)[idx] = Module.hiwire.get_value(idval);
});

EM_JS(JsRef, hiwire_get_member_obj, (JsRef idobj, JsRef ididx), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsidx = Module.hiwire.get_value(ididx);
  if (jsidx in jsobj) {
    return Module.hiwire.new_value(jsobj[jsidx]);
  } else {
    return Module.hiwire.ERROR;
  }
});

EM_JS(void, hiwire_set_member_obj, (JsRef idobj, JsRef ididx, JsRef idval), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsidx = Module.hiwire.get_value(ididx);
  var jsval = Module.hiwire.get_value(idval);
  jsobj[jsidx] = jsval;
});

EM_JS(void, hiwire_delete_member_obj, (JsRef idobj, JsRef ididx), {
  var jsobj = Module.hiwire.get_value(idobj);
  var jsidx = Module.hiwire.get_value(ididx);
  delete jsobj[jsidx];
});

EM_JS(JsRef, hiwire_dir, (JsRef idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  var result = [];
  do {
    result.push.apply(result, Object.getOwnPropertyNames(jsobj));
  } while ((jsobj = Object.getPrototypeOf(jsobj)));
  return Module.hiwire.new_value(result);
});

EM_JS(JsRef, hiwire_call, (JsRef idfunc, JsRef idargs), {
  var jsfunc = Module.hiwire.get_value(idfunc);
  var jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(jsfunc.apply(jsfunc, jsargs));
});

EM_JS(JsRef,
      hiwire_call_member,
      (JsRef idobj, const char* ptrname, JsRef idargs),
      {
        var jsobj = Module.hiwire.get_value(idobj);
        var jsname = UTF8ToString(ptrname);
        var jsargs = Module.hiwire.get_value(idargs);
        return Module.hiwire.new_value(jsobj[jsname].apply(jsobj, jsargs));
      });

EM_JS(JsRef, hiwire_new, (JsRef idobj, JsRef idargs), {
  function newCall(Cls)
  {
    return new (Function.prototype.bind.apply(Cls, arguments));
  }
  var jsobj = Module.hiwire.get_value(idobj);
  var jsargs = Module.hiwire.get_value(idargs);
  jsargs.unshift(jsobj);
  return Module.hiwire.new_value(newCall.apply(newCall, jsargs));
});

EM_JS(int, hiwire_get_length, (JsRef idobj), {
  return Module.hiwire.get_value(idobj).length;
});

EM_JS(bool, hiwire_get_bool, (JsRef idobj), {
  var val = Module.hiwire.get_value(idobj);
  // clang-format off
  return (val && (val.length === undefined || val.length)) ? 1 : 0;
  // clang-format on
});

EM_JS(bool, hiwire_is_function, (JsRef idobj), {
  // clang-format off
  return typeof Module.hiwire.get_value(idobj) === 'function';
  // clang-format on
});

EM_JS(bool, hiwire_function_supports_kwargs, (JsRef idfunc), {
  let funcstr = Module.hiwire.get_value(idfunc).toString();
  return Module.hiwire.function_supports_kwargs(funcstr);
});

EM_JS(JsRef, hiwire_to_string, (JsRef idobj), {
  return Module.hiwire.new_value(Module.hiwire.get_value(idobj).toString());
});

EM_JS(JsRef, hiwire_typeof, (JsRef idobj), {
  return Module.hiwire.new_value(typeof Module.hiwire.get_value(idobj));
});

EM_JS(char*, hiwire_constructor_name, (JsRef idobj), {
  return stringToNewUTF8(Module.hiwire.get_value(idobj).constructor.name);
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS(bool, hiwire_##name, (JsRef ida, JsRef idb), {                         \
    return (Module.hiwire.get_value(ida) op Module.hiwire.get_value(idb)) ? 1  \
                                                                          : 0; \
  })

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
MAKE_OPERATOR(equal, ==);
MAKE_OPERATOR(not_equal, !=);
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

EM_JS(JsRef, hiwire_next, (JsRef idobj), {
  // clang-format off
  if (idobj === Module.hiwire.UNDEFINED) {
    return Module.hiwire.ERROR;
  }

  var jsobj = Module.hiwire.get_value(idobj);
  return Module.hiwire.new_value(jsobj.next());
  // clang-format on
});

EM_JS(JsRef, hiwire_get_iterator, (JsRef idobj), {
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

EM_JS(bool, hiwire_nonzero, (JsRef idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // TODO: should this be !== 0?
  return (jsobj != 0) ? 1 : 0;
});

EM_JS(bool, hiwire_is_typedarray, (JsRef idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return (jsobj['byteLength'] !== undefined) ? 1 : 0;
  // clang-format on
});

EM_JS(bool, hiwire_is_on_wasm_heap, (JsRef idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  return (jsobj.buffer === Module.HEAPU8.buffer) ? 1 : 0;
  // clang-format on
});

EM_JS(int, hiwire_get_byteOffset, (JsRef idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteOffset'];
});

EM_JS(int, hiwire_get_byteLength, (JsRef idobj), {
  var jsobj = Module.hiwire.get_value(idobj);
  return jsobj['byteLength'];
});

EM_JS(void, hiwire_copy_to_ptr, (JsRef idobj, void* ptr), {
  var jsobj = Module.hiwire.get_value(idobj);
  // clang-format off
  var buffer = (jsobj['buffer'] !== undefined) ? jsobj.buffer : jsobj;
  // clang-format on
  Module.HEAPU8.set(new Uint8Array(buffer), ptr);
});

EM_JS(void,
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

EM_JS(JsRef, hiwire_subarray, (JsRef idarr, int start, int end), {
  var jsarr = Module.hiwire.get_value(idarr);
  var jssub = jsarr.subarray(start, end);
  return Module.hiwire.new_value(jssub);
});
