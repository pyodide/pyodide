#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"

_Py_IDENTIFIER(get_cmeth_docstring);
PyObject* py_docstring_mod;

int
set_method_docstring(PyMethodDef* method, PyObject* parent)
{
  bool success = false;
  PyObject* py_method = NULL;
  PyObject* py_result = NULL;

  py_method = PyObject_GetAttrString(parent, method->ml_name);
  FAIL_IF_NULL(py_method);

  py_result = _PyObject_CallMethodIdObjArgs(
    py_docstring_mod, &PyId_get_cmeth_docstring, py_method, NULL);
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

  success = true;
finally:
  Py_CLEAR(py_method);
  Py_CLEAR(py_result);
  return success ? 0 : -1;
}

int
add_methods_and_set_docstrings(PyObject* module,
                               PyMethodDef* methods,
                               PyObject* docstring_source)
{
  bool success = false;

  int i = 0;
  while (methods[i].ml_name != NULL) {
    FAIL_IF_MINUS_ONE(set_method_docstring(&methods[i], docstring_source));
    i++;
  }
  FAIL_IF_MINUS_ONE(PyModule_AddFunctions(module, methods));

  success = true;
finally:
  return success ? 0 : -1;
}

int
docstring_init()
{
  bool success = false;

  py_docstring_mod = PyImport_ImportModule("_pyodide.docstring");
  FAIL_IF_NULL(py_docstring_mod);

  success = true;
finally:
  return success ? 0 : -1;
}
