#include <emscripten/emscripten.h>
#include <emscripten/promise.h>

// Note: Another approach for passing the callback function to the dlopen in JS
// side
//       is using Module.addFunction to register the JS function, then passing
//       it to the C function. However, there is an issue with
//       Module.addFunction with Pyodide snapshot, so we ended up using a
//       predefined C callback functions and passing the promise indirectly
//       through the Module object.

em_promise_result_t
on_fullfilled(void** result, void* data, void* handle)
{
  EM_ASM({ Module.pyodidePromiseLibraryLoading ?.resolve(); });
  return EM_PROMISE_FULFILL;
}

em_promise_result_t
on_rejected(void** result, void* data, void* value)
{
  EM_ASM({
    Module.pyodidePromiseLibraryLoading
      ?.reject(new Error("Failed to load dynamic library"));
  });
  return EM_PROMISE_FULFILL;
}

// Caller must set Module.pyodidePromiseLibraryLoading with a Promise before
// invoking this function.
EMSCRIPTEN_KEEPALIVE void
emscripten_dlopen_wrapper(const char* filename, int flags)
{
  em_promise_t inner = emscripten_dlopen_promise(filename, flags);
  em_promise_t outer =
    emscripten_promise_then(inner, on_fullfilled, on_rejected, NULL);
  emscripten_promise_destroy(outer);
  emscripten_promise_destroy(inner);
}
