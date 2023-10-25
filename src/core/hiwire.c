#define PY_SSIZE_T_CLEAN
#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"

#ifdef DEBUG_F
int tracerefs = 0;
#endif

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
  Hiwire.num_keys = _hiwire_num_refs;
  return 0;
});

int
hiwire_init()
{
  return hiwire_init_js();
}

HwRef
hiwire_new_deduplicate(__externref_t v)
{
  HwRef id = hiwire_new(v);
  HwRef result = hiwire_incref_deduplicate(id);
  hiwire_decref(id);
  return result;
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
