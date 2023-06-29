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
