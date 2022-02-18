#include <exception>
using namespace std;
#include <stdexcept>
#include <stdio.h>

char*
g(int x);

extern "C" char*
f(int x)
{
  char* msg;
  try {
    char* res = g(x);
    asprintf(&msg, "result was: %s\n", res);
  } catch (int param) {
    asprintf(&msg, "caught int %d\n", param);
  } catch (char param) {
    asprintf(&msg, "caught char %d\n", param);
  } catch (runtime_error& e) {
    asprintf(&msg, "caught runtime_error %s\n", e.what());
  } catch (...) {
    asprintf(&msg, "caught ????");
  }
  return msg;
}
