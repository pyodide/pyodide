#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"
#include "jsmemops.h"

#define ERROR_REF (0)
#define ERROR_NUM (-1)

const JsRef Js_undefined = ((JsRef)(2));
const JsRef Js_true = ((JsRef)(4));
const JsRef Js_false = ((JsRef)(6));
const JsRef Js_null = ((JsRef)(8));

// For when the return value would be Option<JsRef>
const JsRef Js_novalue = ((JsRef)(10));

JsRef
hiwire_from_bool(bool boolean)
{
  return boolean ? Js_true : Js_false;
}

// clang-format off
EM_JS(bool, hiwire_to_bool, (JsRef val), {
  return !!Hiwire.get_value(val);
});
// clang-format on

#ifdef DEBUG_F
bool tracerefs;
#endif

#define HIWIRE_INIT_CONST(js_const, hiwire_attr, js_value)                     \
  Hiwire.hiwire_attr = DEREF_U8(js_const, 0);                                  \
  _hiwire.objects.set(Hiwire.hiwire_attr, [ js_value, -1 ]);                   \
  _hiwire.obj_to_key.set(js_value, Hiwire.hiwire_attr);

EM_JS_NUM(int, hiwire_init, (), {
  let _hiwire = {
    objects : new Map(),
    // The reverse of the object maps, needed to deduplicate keys so that key
    // equality is object identity.
    obj_to_key : new Map(),
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
  HIWIRE_INIT_CONST(_Js_undefined, UNDEFINED, undefined);
  HIWIRE_INIT_CONST(_Js_null, JSNULL, null);
  HIWIRE_INIT_CONST(_Js_true, TRUE, true);
  HIWIRE_INIT_CONST(_Js_false, FALSE, false);
  let hiwire_next_permanent = HEAPU8[_Js_novalue] + 2;

#ifdef DEBUG_F
  Hiwire._hiwire = _hiwire;
  let many_objects_warning_threshold = 200;
#endif

  Hiwire.new_value = function(jsval)
  {
    // If jsval already has a hiwire key, then use existing key. We need this to
    // ensure that obj1 === obj2 implies key1 == key2.
    let idval = _hiwire.obj_to_key.get(jsval);
    // clang-format off
    if (idval !== undefined) {
      _hiwire.objects.get(idval)[1]++;
      return idval;
    }
    // clang-format on
    while (_hiwire.objects.has(_hiwire.counter[0])) {
      // Increment by two here (and below) because even integers are reserved
      // for singleton constants
      _hiwire.counter[0] += 2;
    }
    idval = _hiwire.counter[0];
    _hiwire.objects.set(idval, [ jsval, 1 ]);
    _hiwire.obj_to_key.set(jsval, idval);
    _hiwire.counter[0] += 2;
#ifdef DEBUG_F
    if (_hiwire.objects.size > many_objects_warning_threshold) {
      console.warn(
        "A fairly large number of hiwire objects are present, this could " +
        "be a sign of a memory leak.");
      many_objects_warning_threshold += 100;
    }
#endif
#ifdef DEBUG_F
    if (DEREF_U8(_tracerefs, 0)) {
      console.warn("hw.new_value", idval, jsval);
    }
#endif
    return idval;
  };

  Hiwire.intern_object = function(obj)
  {
    let id = hiwire_next_permanent;
    hiwire_next_permanent += 2;
    _hiwire.objects.set(id, [ obj, -1 ]);
    return id;
  };

  // for testing purposes.
  Hiwire.num_keys = function(){
    // clang-format off
    return Array.from(_hiwire.objects.keys()).filter((x) => x % 2).length
    // clang-format on
  };

  Hiwire.get_value = function(idval)
  {
    if (!idval) {
      API.fail_test = true;
      // clang-format off
      // This might have happened because the error indicator is set. Let's
      // check.
      if (_PyErr_Occurred()) {
        // This will lead to a more helpful error message.
        let exc = _wrap_exception();
        let e = Hiwire.pop_value(exc);
        console.error(
          `Internal error: Argument '${idval}' to hiwire.get_value is falsy. ` +
          "This was probably because the Python error indicator was set when get_value was called. " +
          "The Python error that caused this was:",
          e
        );
        throw e;
      } else {
        console.error(
          `Internal error: Argument '${idval}' to hiwire.get_value is falsy`
          + ' (but error indicator is not set).'
        );
        throw new Error(
          `Internal error: Argument '${idval}' to hiwire.get_value is falsy`
          + ' (but error indicator is not set).'
        );
      }
      // clang-format on
    }
    if (!_hiwire.objects.has(idval)) {
      // clang-format off
      console.error(`Undefined id ${ idval }`);
      throw new Error(`Undefined id ${ idval }`);
      // clang-format on
    }
    return _hiwire.objects.get(idval)[0];
  };

  Hiwire.decref = function(idval)
  {
    // clang-format off
    if ((idval & 1) === 0) {
      // least significant bit unset ==> idval is a singleton / interned value.
      // We don't reference count interned values.
      return;
    }
#ifdef DEBUG_F
    if(DEREF_U8(_tracerefs, 0)){
      console.warn("hw.decref", idval, _hiwire.objects.get(idval));
    }
#endif
    let pair = _hiwire.objects.get(idval);
    let new_refcnt = --pair[1];
    if (new_refcnt === 0) {
      _hiwire.objects.delete(idval);
      _hiwire.obj_to_key.delete(pair[0]);
    }
    // clang-format on
  };

  Hiwire.incref = function(idval)
  {
    _hiwire.objects.get(idval)[1]++;
#ifdef DEBUG_F
    if (DEREF_U8(_tracerefs, 0)) {
      console.warn("hw.incref", idval, _hiwire.objects.get(idval));
    }
#endif
  };

  Hiwire.pop_value = function(idval)
  {
    let result = Hiwire.get_value(idval);
    Hiwire.decref(idval);
    return result;
  };

  // This is factored out primarily for testing purposes.
  Hiwire.isPromise = function(obj)
  {
    try {
      // clang-format off
      return (!!obj) && typeof obj.then === 'function';
      // clang-format on
    } catch (e) {
      return false;
    }
  };

  /**
   * Turn any ArrayBuffer view or ArrayBuffer into a Uint8Array.
   *
   * This respects slices: if the ArrayBuffer view is restricted to a slice of
   * the backing ArrayBuffer, we return a Uint8Array that shows the same slice.
   */
  Module.typedArrayAsUint8Array = function(arg)
  {
    // clang-format off
    if(arg.buffer !== undefined){
      // clang-format on
      return new Uint8Array(arg.buffer, arg.byteOffset, arg.byteLength);
    } else {
      return new Uint8Array(arg);
    }
  };

  {
    let dtypes_str =
      [ "b", "B", "h", "H", "i", "I", "f", "d" ].join(String.fromCharCode(0));
    let dtypes_ptr = stringToNewUTF8(dtypes_str);
    let dtypes_map = {};
    for (let[idx, val] of Object.entries(dtypes_str)) {
      dtypes_map[val] = dtypes_ptr + Number(idx);
    }

    let buffer_datatype_map = new Map([
      [ 'Int8Array', [ dtypes_map['b'], 1, true ] ],
      [ 'Uint8Array', [ dtypes_map['B'], 1, true ] ],
      [ 'Uint8ClampedArray', [ dtypes_map['B'], 1, true ] ],
      [ 'Int16Array', [ dtypes_map['h'], 2, true ] ],
      [ 'Uint16Array', [ dtypes_map['H'], 2, true ] ],
      [ 'Int32Array', [ dtypes_map['i'], 4, true ] ],
      [ 'Uint32Array', [ dtypes_map['I'], 4, true ] ],
      [ 'Float32Array', [ dtypes_map['f'], 4, true ] ],
      [ 'Float64Array', [ dtypes_map['d'], 8, true ] ],
      // These last two default to Uint8. They have checked : false to allow use
      // with other types.
      [ 'DataView', [ dtypes_map['B'], 1, false ] ],
      [ 'ArrayBuffer', [ dtypes_map['B'], 1, false ] ],
    ]);

    /**
     * This gets the dtype of a ArrayBuffer or ArrayBuffer view. We return a
     * triple: [char* format_ptr, int itemsize, bool checked] If argument is
     * untyped (a DataView or ArrayBuffer) then we say it's a Uint8, but we set
     * the flag checked to false in that case so we allow assignment to/from
     * anything.
     *
     * This is the API for use from JavaScript, there's also an EM_JS
     * hiwire_get_buffer_datatype wrapper for use from C. Used in js2python and
     * in jsproxy.c for buffers.
     */
    Module.get_buffer_datatype = function(jsobj)
    {
      return buffer_datatype_map.get(jsobj.constructor.name) || [ 0, 0, false ];
    }
  }

  if (globalThis.BigInt) {
    Module.BigInt = BigInt;
  } else {
    Module.BigInt = Number;
  }
  return 0;
});

EM_JS_REF(JsRef, JsString_InternFromCString, (const char* str), {
  let jsstring = UTF8ToString(str);
  return Hiwire.intern_object(jsstring);
})

JsRef
JsString_FromId(Js_Identifier* id)
{
  if (!id->object) {
    id->object = JsString_InternFromCString(id->string);
  }
  return id->object;
}

EM_JS(JsRef, hiwire_incref, (JsRef idval), {
  if (idval & 1) {
    // least significant bit unset ==> idval is a singleton.
    // We don't reference count singletons.
    Hiwire.incref(idval);
  }
  return idval;
});

// clang-format off
EM_JS(void, hiwire_decref, (JsRef idval), {
  Hiwire.decref(idval);
});
// clang-format on

// clang-format off
EM_JS_REF(JsRef, hiwire_int, (int val), {
  return Hiwire.new_value(val);
});
// clang-format on

// clang-format off
EM_JS_REF(JsRef,
hiwire_int_from_digits, (const unsigned int* digits, size_t ndigits), {
  let result = BigInt(0);
  for (let i = 0; i < ndigits; i++) {
    result += BigInt(DEREF_U32(digits, i)) << BigInt(32 * i);
  }
  result += BigInt(DEREF_U32(digits, ndigits - 1) & 0x80000000)
            << BigInt(1 + 32 * (ndigits - 1));
  if (-Number.MAX_SAFE_INTEGER < result && result < Number.MAX_SAFE_INTEGER) {
    result = Number(result);
  }
  return Hiwire.new_value(result);
})
// clang-format on

EM_JS_REF(JsRef, hiwire_double, (double val), {
  return Hiwire.new_value(val);
});

EM_JS_REF(JsRef, hiwire_string_ucs4, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCodePoint(DEREF_U32(ptr, i));
  }
  return Hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_ucs2, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(DEREF_U16(ptr, i));
  }
  return Hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_ucs1, (const char* ptr, int len), {
  let jsstr = "";
  for (let i = 0; i < len; ++i) {
    jsstr += String.fromCharCode(DEREF_U8(ptr, i));
  }
  return Hiwire.new_value(jsstr);
});

EM_JS_REF(JsRef, hiwire_string_utf8, (const char* ptr), {
  return Hiwire.new_value(UTF8ToString(ptr));
});

EM_JS_REF(JsRef, hiwire_string_ascii, (const char* ptr), {
  return Hiwire.new_value(AsciiToString(ptr));
});

EM_JS(void _Py_NO_RETURN, hiwire_throw_error, (JsRef iderr), {
  throw Hiwire.pop_value(iderr);
});

EM_JS(bool, JsArray_Check, (JsRef idobj), {
  let obj = Hiwire.get_value(idobj);
  if (Array.isArray(obj)) {
    return true;
  }
  let typeTag = Object.prototype.toString.call(obj);
  // We want to treat some standard array-like objects as Array.
  // clang-format off
  if(typeTag === "[object HTMLCollection]" || typeTag === "[object NodeList]"){
    // clang-format on
    return true;
  }
  // What if it's a TypedArray?
  // clang-format off
  if (ArrayBuffer.isView(obj) && obj.constructor.name !== "DataView") {
    // clang-format on
    return true;
  }
  return false;
});

// clang-format off
EM_JS_REF(JsRef, JsArray_New, (), {
  return Hiwire.new_value([]);
});
// clang-format on

EM_JS_NUM(errcode, JsArray_Push, (JsRef idarr, JsRef idval), {
  Hiwire.get_value(idarr).push(Hiwire.get_value(idval));
});

EM_JS(void, JsArray_Push_unchecked, (JsRef idarr, JsRef idval), {
  Hiwire.get_value(idarr).push(Hiwire.get_value(idval));
});

// clang-format off
EM_JS_REF(JsRef, JsObject_New, (), {
  return Hiwire.new_value({});
});
// clang-format on

EM_JS_REF(JsRef, JsObject_GetString, (JsRef idobj, const char* ptrkey), {
  let jsobj = Hiwire.get_value(idobj);
  let jskey = UTF8ToString(ptrkey);
  let result = jsobj[jskey];
  // clang-format off
  if (result === undefined && !(jskey in jsobj)) {
    // clang-format on
    return ERROR_REF;
  }
  return Hiwire.new_value(result);
});

// clang-format off
EM_JS_NUM(errcode,
          JsObject_SetString,
          (JsRef idobj, const char* ptrkey, JsRef idval),
{
  let jsobj = Hiwire.get_value(idobj);
  let jskey = UTF8ToString(ptrkey);
  let jsval = Hiwire.get_value(idval);
  jsobj[jskey] = jsval;
});
// clang-format on

EM_JS_NUM(errcode, JsObject_DeleteString, (JsRef idobj, const char* ptrkey), {
  let jsobj = Hiwire.get_value(idobj);
  let jskey = UTF8ToString(ptrkey);
  delete jsobj[jskey];
});

EM_JS_REF(JsRef, JsArray_Get, (JsRef idobj, int idx), {
  let obj = Hiwire.get_value(idobj);
  let result = obj[idx];
  // clang-format off
  if (result === undefined && !(idx in obj)) {
    // clang-format on
    return ERROR_REF;
  }
  return Hiwire.new_value(result);
});

EM_JS_NUM(errcode, JsArray_Set, (JsRef idobj, int idx, JsRef idval), {
  Hiwire.get_value(idobj)[idx] = Hiwire.get_value(idval);
});

EM_JS_NUM(errcode, JsArray_Delete, (JsRef idobj, int idx), {
  let obj = Hiwire.get_value(idobj);
  // Weird edge case: allow deleting an empty entry, but we raise a key error if
  // access is attempted.
  if (idx < 0 || idx >= obj.length) {
    return ERROR_NUM;
  }
  obj.splice(idx, 1);
});

EM_JS_REF(JsRef, JsObject_Dir, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  let result = [];
  do {
    // clang-format off
    result.push(... Object.getOwnPropertyNames(jsobj).filter(
      s => {
        let c = s.charCodeAt(0);
        return c < 48 || c > 57; /* Filter out integer array indices */
      }
    ));
    // clang-format on
  } while (jsobj = Object.getPrototypeOf(jsobj));
  return Hiwire.new_value(result);
});

static JsRef
convert_va_args(va_list args)
{
  JsRef idargs = JsArray_New();
  while (true) {
    JsRef idarg = va_arg(args, JsRef);
    if (idarg == NULL) {
      break;
    }
    JsArray_Push_unchecked(idargs, idarg);
  }
  va_end(args);
  return idargs;
}

EM_JS_REF(JsRef, hiwire_call, (JsRef idfunc, JsRef idargs), {
  let jsfunc = Hiwire.get_value(idfunc);
  let jsargs = Hiwire.get_value(idargs);
  return Hiwire.new_value(jsfunc(... jsargs));
});

JsRef
hiwire_call_va(JsRef idobj, ...)
{
  va_list args;
  va_start(args, idobj);
  JsRef idargs = convert_va_args(args);
  JsRef idresult = hiwire_call(idobj, idargs);
  hiwire_decref(idargs);
  return idresult;
}

EM_JS_REF(JsRef, hiwire_call_OneArg, (JsRef idfunc, JsRef idarg), {
  let jsfunc = Hiwire.get_value(idfunc);
  let jsarg = Hiwire.get_value(idarg);
  return Hiwire.new_value(jsfunc(jsarg));
});

// clang-format off
EM_JS_REF(JsRef,
          hiwire_call_bound,
          (JsRef idfunc, JsRef idthis, JsRef idargs),
{
  let func = Hiwire.get_value(idfunc);
  let this_;
  if (idthis === 0) {
    this_ = null;
  } else {
    this_ = Hiwire.get_value(idthis);
  }
  let args = Hiwire.get_value(idargs);
  return Hiwire.new_value(func.apply(this_, args));
});
// clang-format on

EM_JS(bool, hiwire_HasMethod, (JsRef obj_id, JsRef name), {
  // clang-format off
  let obj = Hiwire.get_value(obj_id);
  return obj && typeof obj[Hiwire.get_value(name)] === "function";
  // clang-format on
})

bool
hiwire_HasMethodId(JsRef obj, Js_Identifier* name)
{
  return hiwire_HasMethod(obj, JsString_FromId(name));
}

// clang-format off
EM_JS_REF(JsRef,
          hiwire_CallMethodString,
          (JsRef idobj, const char* name, JsRef idargs),
{
  let jsobj = Hiwire.get_value(idobj);
  let jsname = UTF8ToString(name);
  let jsargs = Hiwire.get_value(idargs);
  return Hiwire.new_value(jsobj[jsname](...jsargs));
});
// clang-format on

EM_JS_REF(JsRef, hiwire_CallMethod, (JsRef idobj, JsRef name, JsRef idargs), {
  let jsobj = Hiwire.get_value(idobj);
  let jsname = Hiwire.get_value(name);
  let jsargs = Hiwire.get_value(idargs);
  return Hiwire.new_value(jsobj[jsname](... jsargs));
});

// clang-format off
EM_JS_REF(JsRef,
          hiwire_CallMethod_OneArg,
          (JsRef idobj, JsRef name, JsRef idarg),
{
  let jsobj = Hiwire.get_value(idobj);
  let jsname = Hiwire.get_value(name);
  let jsarg = Hiwire.get_value(idarg);
  return Hiwire.new_value(jsobj[jsname](jsarg));
});
// clang-format on

JsRef
hiwire_CallMethodId(JsRef idobj, Js_Identifier* name_id, JsRef idargs)
{
  JsRef name_ref = JsString_FromId(name_id);
  if (name_ref == NULL) {
    return NULL;
  }
  return hiwire_CallMethod(idobj, name_ref, idargs);
}

JsRef
hiwire_CallMethodString_va(JsRef idobj, const char* ptrname, ...)
{
  va_list args;
  va_start(args, ptrname);
  JsRef idargs = convert_va_args(args);
  JsRef idresult = hiwire_CallMethodString(idobj, ptrname, idargs);
  hiwire_decref(idargs);
  return idresult;
}

JsRef
hiwire_CallMethodId_va(JsRef idobj, Js_Identifier* name, ...)
{
  va_list args;
  va_start(args, name);
  JsRef idargs = convert_va_args(args);
  JsRef idresult = hiwire_CallMethodId(idobj, name, idargs);
  hiwire_decref(idargs);
  return idresult;
}

JsRef
hiwire_CallMethodId_OneArg(JsRef obj, Js_Identifier* name, JsRef arg)
{
  JsRef name_ref = JsString_FromId(name);
  if (name_ref == NULL) {
    return NULL;
  }
  return hiwire_CallMethod_OneArg(obj, name_ref, arg);
}

EM_JS_REF(JsRef, hiwire_construct, (JsRef idobj, JsRef idargs), {
  let jsobj = Hiwire.get_value(idobj);
  let jsargs = Hiwire.get_value(idargs);
  return Hiwire.new_value(Reflect.construct(jsobj, jsargs));
});

EM_JS(bool, hiwire_has_length, (JsRef idobj), {
  let val = Hiwire.get_value(idobj);
  // clang-format off
  return (typeof val.size === "number") ||
         (typeof val.length === "number" && typeof val !== "function");
  // clang-format on
});

EM_JS_NUM(int, hiwire_get_length, (JsRef idobj), {
  let val = Hiwire.get_value(idobj);
  // clang-format off
  if (typeof val.size === "number") {
    return val.size;
  }
  if (typeof val.length === "number") {
    return val.length;
  }
  // clang-format on
  return ERROR_NUM;
});

EM_JS(bool, hiwire_get_bool, (JsRef idobj), {
  let val = Hiwire.get_value(idobj);
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

EM_JS(bool, hiwire_is_pyproxy, (JsRef idobj), {
  return API.isPyProxy(Hiwire.get_value(idobj));
});

EM_JS(bool, hiwire_is_function, (JsRef idobj), {
  // clang-format off
  return typeof Hiwire.get_value(idobj) === 'function';
  // clang-format on
});

EM_JS(bool, hiwire_is_comlink_proxy, (JsRef idobj), {
  let value = Hiwire.get_value(idobj);
  return !!(API.Comlink && value[API.Comlink.createEndpoint]);
});

EM_JS(bool, hiwire_is_error, (JsRef idobj), {
  // From https://stackoverflow.com/a/45496068
  let value = Hiwire.get_value(idobj);
  // clang-format off
  return !!(value && typeof value.stack === "string" &&
            typeof value.message === "string");
  // clang-format on
});

EM_JS(bool, hiwire_is_promise, (JsRef idobj), {
  // clang-format off
  let obj = Hiwire.get_value(idobj);
  return Hiwire.isPromise(obj);
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_resolve_promise, (JsRef idobj), {
  // clang-format off
  let obj = Hiwire.get_value(idobj);
  let result = Promise.resolve(obj);
  return Hiwire.new_value(result);
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_to_string, (JsRef idobj), {
  return Hiwire.new_value(Hiwire.get_value(idobj).toString());
});

EM_JS_REF(JsRef, hiwire_typeof, (JsRef idobj), {
  return Hiwire.new_value(typeof Hiwire.get_value(idobj));
});

EM_JS_REF(char*, hiwire_constructor_name, (JsRef idobj), {
  return stringToNewUTF8(Hiwire.get_value(idobj).constructor.name);
});

#define MAKE_OPERATOR(name, op)                                                \
  EM_JS(bool, hiwire_##name, (JsRef ida, JsRef idb), {                         \
    return !!(Hiwire.get_value(ida) op Hiwire.get_value(idb));                 \
  })

MAKE_OPERATOR(less_than, <);
MAKE_OPERATOR(less_than_equal, <=);
// clang-format off
MAKE_OPERATOR(equal, ===);
MAKE_OPERATOR(not_equal, !==);
// clang-format on
MAKE_OPERATOR(greater_than, >);
MAKE_OPERATOR(greater_than_equal, >=);

EM_JS(bool, hiwire_is_iterator, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  // clang-format off
  return typeof jsobj.next === 'function';
  // clang-format on
});

EM_JS_NUM(int, hiwire_next, (JsRef idobj, JsRef* result_ptr), {
  let jsobj = Hiwire.get_value(idobj);
  // clang-format off
  let { done, value } = jsobj.next();
  // clang-format on
  let result_id = Hiwire.new_value(value);
  DEREF_U32(result_ptr, 0) = result_id;
  return done;
});

EM_JS(bool, hiwire_is_iterable, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  // clang-format off
  return typeof jsobj[Symbol.iterator] === 'function';
  // clang-format on
});

EM_JS_REF(JsRef, hiwire_get_iterator, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  return Hiwire.new_value(jsobj[Symbol.iterator]());
})

EM_JS_REF(JsRef, JsObject_Entries, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  return Hiwire.new_value(Object.entries(jsobj));
});

EM_JS_REF(JsRef, JsObject_Keys, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  return Hiwire.new_value(Object.keys(jsobj));
});

EM_JS_REF(JsRef, JsObject_Values, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  return Hiwire.new_value(Object.values(jsobj));
});

EM_JS(bool, hiwire_is_typedarray, (JsRef idobj), {
  let jsobj = Hiwire.get_value(idobj);
  // clang-format off
  return ArrayBuffer.isView(jsobj) || jsobj.constructor.name === "ArrayBuffer";
  // clang-format on
});

EM_JS_NUM(errcode, hiwire_assign_to_ptr, (JsRef idobj, void* ptr), {
  let jsobj = Hiwire.get_value(idobj);
  Module.HEAPU8.set(Module.typedArrayAsUint8Array(jsobj), ptr);
});

EM_JS_NUM(errcode, hiwire_assign_from_ptr, (JsRef idobj, void* ptr), {
  let jsobj = Hiwire.get_value(idobj);
  Module.typedArrayAsUint8Array(jsobj).set(
    Module.HEAPU8.subarray(ptr, ptr + jsobj.byteLength));
});

EM_JS_NUM(errcode, hiwire_read_from_file, (JsRef idobj, int fd), {
  let jsobj = Hiwire.get_value(idobj);
  let uint8_buffer = Module.typedArrayAsUint8Array(jsobj);
  let stream = Module.FS.streams[fd];
  Module.FS.read(stream, uint8_buffer, 0, uint8_buffer.byteLength);
});

EM_JS_NUM(errcode, hiwire_write_to_file, (JsRef idobj, int fd), {
  let jsobj = Hiwire.get_value(idobj);
  let uint8_buffer = Module.typedArrayAsUint8Array(jsobj);
  let stream = Module.FS.streams[fd];
  Module.FS.write(stream, uint8_buffer, 0, uint8_buffer.byteLength);
});

EM_JS_NUM(errcode, hiwire_into_file, (JsRef idobj, int fd), {
  let jsobj = Hiwire.get_value(idobj);
  let uint8_buffer = Module.typedArrayAsUint8Array(jsobj);
  let stream = Module.FS.streams[fd];
  // set canOwn param to true, leave position undefined.
  Module.FS.write(
    stream, uint8_buffer, 0, uint8_buffer.byteLength, undefined, true);
});

// clang-format off
EM_JS_UNCHECKED(
void,
hiwire_get_buffer_info, (JsRef idobj,
                         Py_ssize_t* byteLength_ptr,
                         char** format_ptr,
                         Py_ssize_t* size_ptr,
                         bool* checked_ptr),
{
  let jsobj = Hiwire.get_value(idobj);
  let byteLength = jsobj.byteLength;
  let [format_utf8, size, checked] = Module.get_buffer_datatype(jsobj);
  // Store results into arguments
  DEREF_U32(byteLength_ptr, 0) = byteLength;
  DEREF_U32(format_ptr, 0) = format_utf8;
  DEREF_U32(size_ptr, 0) = size;
  DEREF_U8(checked_ptr, 0) = checked;
});
// clang-format on

EM_JS_REF(JsRef, hiwire_subarray, (JsRef idarr, int start, int end), {
  let jsarr = Hiwire.get_value(idarr);
  let jssub = jsarr.subarray(start, end);
  return Hiwire.new_value(jssub);
});

// clang-format off
EM_JS_REF(JsRef, JsMap_New, (), {
  return Hiwire.new_value(new Map());
})
// clang-format on

EM_JS_NUM(errcode, JsMap_Set, (JsRef mapid, JsRef keyid, JsRef valueid), {
  let map = Hiwire.get_value(mapid);
  let key = Hiwire.get_value(keyid);
  let value = Hiwire.get_value(valueid);
  map.set(key, value);
})

// clang-format off
EM_JS_REF(JsRef, JsSet_New, (), {
  return Hiwire.new_value(new Set());
})
// clang-format on

EM_JS_NUM(errcode, JsSet_Add, (JsRef mapid, JsRef keyid), {
  let set = Hiwire.get_value(mapid);
  let key = Hiwire.get_value(keyid);
  set.add(key);
})
