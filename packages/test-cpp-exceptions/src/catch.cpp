#include <exception>
using namespace std;
#include <Python.h>
#include <setjmp.h>
#include <stdexcept>
#include <stdio.h>

extern "C" char*
throw_exc(int x);

extern "C" int
call_pyobj(PyObject* x);

extern "C" char*
catch_exc(int x)
{
  char* msg;
  try {
    char* res = throw_exc(x);
    asprintf(&msg, "result was: %s", res);
  } catch (int param) {
    asprintf(&msg, "caught int %d", param);
  } catch (char param) {
    asprintf(&msg, "caught char %d", param);
  } catch (runtime_error& e) {
    asprintf(&msg, "caught runtime_error %s", e.what());
  } catch (...) {
    asprintf(&msg, "caught ????");
  }
  return msg;
}

extern "C" char*
catch_call_pyobj(PyObject* x)
{
  char* msg;
  try {
    int res = call_pyobj(x);
    asprintf(&msg, "result was: %d", res);
  } catch (int param) {
    asprintf(&msg, "caught int %d", param);
  } catch (char param) {
    asprintf(&msg, "caught char %d", param);
  } catch (runtime_error& e) {
    asprintf(&msg, "caught runtime_error %s", e.what());
  } catch (...) {
    asprintf(&msg, "caught ????");
  }
  return msg;
}

extern "C" char*
promising_catch_call_pyobj(PyObject* x)
{
  return catch_call_pyobj(x);
}

jmp_buf my_jump_buffer;
void
longjmp_func(int status);

extern "C" int
set_jmp_func()
{
  int status = setjmp(my_jump_buffer);
  if (status == 0) {
    longjmp_func(4);
  }
  return status;
}

// Test invoke functions
//
// With JSPI we replace the invoke functions see
// src/core/stack_switching/create_invokes.mjs and
// emsdk/patches/0001-Changes-for-JSPI.patch.
//
// This requires a slightly different mechanism if the signature of the function
// call in the try block matches the signature of a function call that occurs in
// a try block in the main module or not. If it does, the invoke function is
// setup at startup, otherwise it's setup when needed (or something). We used to
// have a bug for the second type of function. `custom_invoke` with its weird
// sequence of argument types is intended to provide coverage for this case.
//
// See PR #4455

int
throw_builtin_invoke(int a1, int a2);

int
throw_custom_invoke(int a1,
                    double a2,
                    int a3,
                    float a4,
                    int a5,
                    double a6,
                    long long a7);

extern "C" char*
catch_invoke_func(int x)
{
  char* msg = "";
  try {
    if (x == 0) {
      throw_builtin_invoke(1, 2);
    } else {
      throw_custom_invoke(1, 2, 3, 4, 5, 6, 7);
    }
  } catch (runtime_error& e) {
    asprintf(&msg, "caught runtime_error %s", e.what());
  }
  return msg;
}

// Python bindings. The C functions above stay exported so the tests that need
// to call them directly from JavaScript can still do so.

static PyObject*
take_string(char* msg)
{
  PyObject* result = PyUnicode_FromString(msg);
  free(msg);
  return result;
}

static PyObject*
py_catch_exc(PyObject* self, PyObject* arg)
{
  int x = PyLong_AsInt(arg);
  if (x == -1 && PyErr_Occurred()) {
    return NULL;
  }
  return take_string(catch_exc(x));
}

static PyObject*
py_catch_invoke_func(PyObject* self, PyObject* arg)
{
  int x = PyLong_AsInt(arg);
  if (x == -1 && PyErr_Occurred()) {
    return NULL;
  }
  return take_string(catch_invoke_func(x));
}

static PyObject*
py_set_jmp_func(PyObject* self, PyObject* Py_UNUSED(ignored))
{
  return PyLong_FromLong(set_jmp_func());
}

static PyMethodDef methods[] = {
  { "catch_exc",
    py_catch_exc,
    METH_O,
    "Call a function in libthrow.so that throws and catch the C++ exception." },
  { "catch_invoke_func",
    py_catch_invoke_func,
    METH_O,
    "Catch a C++ exception thrown through an invoke function." },
  { "set_jmp_func",
    py_set_jmp_func,
    METH_NOARGS,
    "setjmp here and longjmp back from libthrow.so." },
  { NULL, NULL, 0, NULL },
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT, "_catch", NULL, -1, methods,
};

extern "C" PyMODINIT_FUNC
PyInit__catch(void)
{
  return PyModule_Create(&module);
}
