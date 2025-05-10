#include "hiwire/hiwire.h"
#include "error_handling.h"
#include <emscripten.h>

// clang-format off
EM_JS_MACROS(void, hiwire_invalid_ref_js, (int type, JsRef ref), {
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

// Called by libhiwire if an invalid ID is dereferenced.
void
hiwire_invalid_ref(int type, JsRef ref)
{
  hiwire_invalid_ref_js(type, ref);
}
