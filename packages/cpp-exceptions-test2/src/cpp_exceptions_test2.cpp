#include "Python.h"
#include <stdexcept>

extern "C" __attribute__((visibility("default"))) PyObject*
PyInit_cpp_exceptions_test2()
{
  try {
    throw std::runtime_error("something bad?");
  } catch (const std::exception& e) {
    PyErr_SetString(PyExc_ImportError, "oops");
  }
  return nullptr;
}
