#include <Python.h>
#include <emscripten.h>
#include <stdbool.h>

static bool type_reflection_available;

int
pytrampoline_init()
{
  type_reflection_available = EM_ASM_INT({ return "Function" in WebAssembly; });
  return 0;
}

// clang-format off
EM_JS(
PyObject*,
py_emjs_trampoline_js,
(PyCFunctionWithKeywords func, PyObject* self, PyObject* args, PyObject* kw),
{
    return wasmTableMirror[func](self, args, kw);
});
// clang-format on

static PyObject*
py_emjs_trampoline(PyCFunctionWithKeywords func,
                   PyObject* self,
                   PyObject* args,
                   PyObject* kw)
{
  return py_emjs_trampoline_js(func, self, args, kw);
}

// clang-format off
EM_JS(int, count_params, (PyCFunctionWithKeywords func), {
  if (count_params.cache.has(func)) {
    return count_params.cache.get(func);
  }
  const n = WebAssembly.Function.type(wasmTableMirror[func]).parameters.length;
  if (n > 3) {
    throw new Error("handler takes too many arguments");
  }
  count_params.cache.set(func, n);
  return n;
}
count_params.cache = new Map();
)
// clang-format on

typedef PyObject* (*zero_arg)(void);
typedef PyObject* (*one_arg)(PyObject*);
typedef PyObject* (*two_arg)(PyObject*, PyObject*);
typedef PyObject* (*three_arg)(PyObject*, PyObject*, PyObject*);

// These are the Emscripten call trampolines that we patched out of CPython.
static PyObject*
py_trampoline(PyCFunctionWithKeywords func,
              PyObject* self,
              PyObject* args,
              PyObject* kw)
{
  if (!type_reflection_available) {
    return py_emjs_trampoline(func, self, args, kw);
  } else {
    switch (count_params(func)) {
      case 0:
        return ((zero_arg)func)();
      case 1:
        return ((one_arg)func)(self);
      case 2:
        return ((two_arg)func)(self, args);
      case 3:
        return ((three_arg)func)(self, args, kw);
      default:
        __builtin_unreachable();
    }
  }
}

PyObject*
_PyCFunctionWithKeywords_TrampolineCall(PyCFunctionWithKeywords func,
                                        PyObject* self,
                                        PyObject* args,
                                        PyObject* kw)
{
  return py_trampoline(func, self, args, kw);
}

int
descr_set_trampoline_call(setter set,
                          PyObject* obj,
                          PyObject* value,
                          void* closure)
{
  return (int)py_trampoline(
    (PyCFunctionWithKeywords)set, obj, value, (PyObject*)closure);
}

PyObject*
descr_get_trampoline_call(getter get, PyObject* obj, void* closure)
{
  return py_trampoline(
    (PyCFunctionWithKeywords)get, obj, (PyObject*)closure, NULL);
}
