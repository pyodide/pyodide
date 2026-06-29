#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "error_handling.h"
#include "python_unexposed.h"

_Py_IDENTIFIER(get_cmeth_docstring);
PyObject* py_docstring_mod;

int
set_method_docstring(PyMethodDef* method, PyObject* parent)
{
  FAIL_RETURN_VALUE(-1);
  DECLARE_PY_OBJECT(py_method);

  py_method = PyObject_GetAttrString(parent, method->ml_name);
  if (py_method == NULL) {
    PyErr_Format(PyExc_AttributeError,
                 "set_method_docstring failed for method %s, documentation "
                 "stub '%.50s' has no such attribute.",
                 method->ml_name,
                 Py_TYPE(parent)->tp_name);
    FAIL();
  }

  DECLARE_PY_OBJECT(py_result);
  py_result = _PyObject_CallMethodIdOneArg(
    py_docstring_mod, &PyId_get_cmeth_docstring, py_method);
  FAIL_IF_NULL(py_result);

  Py_ssize_t size;
  const char* py_result_utf8 = PyUnicode_AsUTF8AndSize(py_result, &size);
  // size is the number of characters in the string, not including the null
  // byte at the end.
  // We are never going to free this memory.
  char* result = (char*)malloc(size + 1);
  FAIL_IF_NULL(result);

  memcpy(result, py_result_utf8, size + 1);
  method->ml_doc = result;

  return 0;
}

int
add_methods_and_set_docstrings(PyObject* module,
                               PyMethodDef* methods,
                               PyObject* docstring_source)
{
  FAIL_RETURN_VALUE(-1);

  int i = 0;
  while (methods[i].ml_name != NULL) {
    FAIL_IF_MINUS_ONE(set_method_docstring(&methods[i], docstring_source));
    i++;
  }
  FAIL_IF_MINUS_ONE(PyModule_AddFunctions(module, methods));

  return 0;
}

int
docstring_init()
{
  FAIL_RETURN_VALUE(-1);

  py_docstring_mod = PyImport_ImportModule("_pyodide.docstring");
  FAIL_IF_NULL(py_docstring_mod);

  return 0;
}
