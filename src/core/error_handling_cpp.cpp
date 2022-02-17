#include <exception>
using namespace std;

extern "C" const char*
exc_what(exception& e)
{
  return e.what();
}
