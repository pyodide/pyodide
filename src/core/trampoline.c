// This file provides the following trampolines:
//
//    * _PyCFunctionWithKeywords_TrampolineCall
//    * descr_set_trampoline_call
//    * descr_get_trampoline_call
//
// These are all imported from libpython because we deleted them with the
// Remove-trampoline-definitions patch. We need this for JSPI because it
// does not get along with JS trampolines.

#include <Python.h>
#include <emscripten.h>

// clang-format off
EM_JS(
PyObject*,
py_emjs_trampoline_js,
(PyCFunctionWithKeywords func, PyObject* self, PyObject* args, PyObject* kw),
{
    return getWasmTableEntry(func)(self, args, kw);
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
