#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"
#include "jsmemops.h"
#undef hiwire_incref

#define ERROR_REF (0)
#define ERROR_NUM (-1)

#ifdef DEBUG_F
int tracerefs = 0;
#endif

// For when the return value would be Option<JsRef>
// we use the largest possible immortal reference so that `get_value` on it will
// always raise an error.
const JsRef Js_novalue = ((JsRef)(2147483644));

#define HIWIRE_INIT_CONSTS()                                                   \
  HIWIRE_INIT_CONST(undefined)                                                 \
  HIWIRE_INIT_CONST(null)                                                      \
  HIWIRE_INIT_CONST(true)                                                      \
  HIWIRE_INIT_CONST(false)

// we use HIWIRE_INIT_CONSTS once in C and once inside JS with different
// definitions of HIWIRE_INIT_CONST to ensure everything lines up properly
// C definition:
#define HIWIRE_INIT_CONST(js_value)                                            \
  EMSCRIPTEN_KEEPALIVE const JsRef Js_##js_value;
HIWIRE_INIT_CONSTS();

#undef HIWIRE_INIT_CONST

#define HIWIRE_INIT_CONST(js_value)                                            \
  HEAP32[_Js_##js_value / 4] = _hiwire_intern(js_value);

EM_JS_NUM(int, hiwire_init_js, (void), {
  HIWIRE_INIT_CONSTS();
  // clang-format off
  Hiwire.new_value = _hiwire_new;
  Hiwire.new_stack = _hiwire_new;
  Hiwire.intern_object = _hiwire_intern;
  Hiwire.num_keys = _hiwire_num_refs;
  Hiwire.stack_length = () => 0;
  Hiwire.get_value = _hiwire_get;
  Hiwire.incref = (x) =>
  {
    _hiwire_incref(x);
    return x;
  };
  Hiwire.decref = _hiwire_decref;
  Hiwire.pop_value = _hiwire_pop;
  // clang-format on

  Module.iterObject = function * (object)
  {
    for (let k in object) {
      if (Object.prototype.hasOwnProperty.call(object, k)) {
        yield k;
      }
    }
  };
  return 0;
});

int
hiwire_init()
{
  return hiwire_init_js();
}

HwRef
wrapped_hiwire_incref(HwRef ref)
{
  hiwire_incref(ref);
  return ref;
}

// Called by libhiwire if an invalid ID is dereferenced.
// clang-format off
EM_JS_MACROS(void, hiwire_invalid_ref, (int type, JsRef ref), {
  API.fail_test = true;
  if (type === HIWIRE_FAIL_GET && !ref) {
    // hiwire_get on NULL.
    // This might have happened because the error indicator is set. Let's
    // check.
    if (_PyErr_Occurred()) {
      // This will lead to a more helpful error message.
      const e = _wrap_exception();
      console.error(
        "Pyodide internal error: Argument to hiwire_get is falsy. This was " +
        "probably because the Python error indicator was set when get_value was " +
        "called. The Python error that caused this was:",
        e
      );
      throw e;
    } else {
      const msg = (
          "Pyodide internal error: Argument to hiwire_get is falsy (but error " +
          "indicator is not set)."
      );
      console.error(msg);
      throw new Error(msg);
    }
  }
  const typestr = {
    [HIWIRE_FAIL_GET]: "get",
    [HIWIRE_FAIL_INCREF]: "incref",
    [HIWIRE_FAIL_DECREF]: "decref",
  }[type];
  const msg = (
    `hiwire_${typestr} on invalid reference ${ref}. This is most likely due ` +
    "to use after free. It may also be due to memory corruption."
  );
  console.error(msg);
  throw new Error(msg);
});
// clang-format on
