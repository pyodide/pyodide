#include <exception>
using namespace std;
#include <Python.h>
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
