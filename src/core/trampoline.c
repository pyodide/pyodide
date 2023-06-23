#include <emscripten.h>
#include <Python.h>

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

// These are the Emscripten call trampolines that we patched out of CPython.
static PyObject*
py_trampoline(PyCFunctionWithKeywords func,
              PyObject* self,
              PyObject* args,
              PyObject* kw)
{
    return py_emjs_trampoline(func, self, args, kw);
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
