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

extern "C" void
set_suspender(__externref_t suspender);

extern "C" char*
promising_catch_call_pyobj(__externref_t suspender, PyObject* x)
{
  set_suspender(suspender);
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
