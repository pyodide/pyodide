#include "Python.h"

// Some Python methods that got removed from the public headers in Python 3.13,
// but don't have immediately obvious replacements. For now, I copied them from
// the private headers to this file.

static inline PyObject*
_PyObject_VectorcallMethodId(_Py_Identifier* name,
                             PyObject* const* args,
                             size_t nargsf,
                             PyObject* kwnames)
{
  PyObject* oname = _PyUnicode_FromId(name); /* borrowed */
  if (!oname) {
    return _Py_NULL;
  }
  return PyObject_VectorcallMethod(oname, args, nargsf, kwnames);
}

static inline PyObject*
_PyObject_CallMethodIdNoArgs(PyObject* self, _Py_Identifier* name)
{
  size_t nargsf = 1 | PY_VECTORCALL_ARGUMENTS_OFFSET;
  return _PyObject_VectorcallMethodId(name, &self, nargsf, _Py_NULL);
}

static inline PyObject*
_PyObject_CallMethodIdOneArg(PyObject* self,
                             _Py_Identifier* name,
                             PyObject* arg)
{
  PyObject* args[2] = { self, arg };
  size_t nargsf = 2 | PY_VECTORCALL_ARGUMENTS_OFFSET;
  assert(arg != NULL);
  return _PyObject_VectorcallMethodId(name, args, nargsf, _Py_NULL);
}

PyObject*
_PyErr_FormatFromCause(PyObject* exception, const char* format, ...);

Py_hash_t
_Py_HashBytes(const void*, Py_ssize_t);

extern PyObject*
_PyObject_CallMethodIdObjArgs(PyObject* obj, _Py_Identifier* name, ...);

int
_PyGen_SetStopIterationValue(PyObject*);

PyAPI_FUNC(int) _PyArg_ParseStack(PyObject* const* args,
                                  Py_ssize_t nargs,
                                  const char* format,
                                  ...);

PyAPI_FUNC(int)
  _PyArg_CheckPositional(const char*, Py_ssize_t, Py_ssize_t, Py_ssize_t);

extern PyObject*
_PyObject_CallMethodIdObjArgs(PyObject* obj, _Py_Identifier* name, ...);

PyAPI_FUNC(int) _PyArg_ParseStackAndKeywords(PyObject* const* args,
                                             Py_ssize_t nargs,
                                             PyObject* kwnames,
                                             struct _PyArg_Parser*,
                                             ...);

PyAPI_FUNC(int) _PySet_Update(PyObject* set, PyObject* iterable);

extern int
_PyObject_SetAttrId(PyObject*, _Py_Identifier*, PyObject*);

extern int
_PyUnicode_EQ(PyObject*, PyObject*);

extern PyObject*
_PyObject_NextNotImplemented(PyObject*);
PyAPI_FUNC(int) _PyGen_FetchStopIterationValue(PyObject**);
