#include <emscripten.h>
#include <exception>
#include <typeinfo>
using namespace std;

extern "C"
{

  EMSCRIPTEN_KEEPALIVE
  const char* exc_what(exception& e)
  {
    return e.what();
  }

  EMSCRIPTEN_KEEPALIVE
  const std::type_info* exc_type()
  {
    return &typeid(exception);
  }

  EMSCRIPTEN_KEEPALIVE
  const char* exc_typename(std::type_info* type)
  {
    return type->name();
  }
}
