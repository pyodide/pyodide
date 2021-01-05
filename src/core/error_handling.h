/**  Wrap EM_JS so that it produces functions that follow the Python return
 *  conventions. We catch javascript errors and proxy them and use
 *  `PyErr_SetObject` to hand them off to python. We need two variants, one
 *  for functions that return pointers / references (return 0)
 *  the other for functions that return numbers (return -1).
 */

typedef int errcode;

void
PyodideErr_SetJsError(JsRef err);

#define EM_JS_REF(ret, func_name, args, body...)                               \
  EM_JS(ret, func_name, args, {                                                \
    /* "use strict";  TODO: enable this. */                                    \
    try {                                                                      \
      body                                                                     \
    } catch (e) {                                                              \
      /* Dummied out until calling code is ready to catch these errors */      \
      throw e;                                                                 \
      let err = Module.hiwire.new_value(e);                                    \
      PyodideErr_SetJsError(err);                                              \
      Module.hiwire.decref(err);                                               \
      return 0;                                                                \
    }                                                                          \
  })

#define EM_JS_NUM(ret, func_name, args, body...)                               \
  EM_JS(ret, func_name, args, {                                                \
    /* "use strict";  TODO: enable this. */                                    \
    try {                                                                      \
      body                                                                     \
    } catch (e) {                                                              \
      throw e;                                                                 \
      /* Dummied out until calling code is ready to catch these errors */      \
      let err = Module.hiwire.new_value(e);                                    \
      PyodideErr_SetJsError(err);                                              \
      Module.hiwire.decref(err);                                               \
      return -1;                                                               \
    }                                                                          \
  })
