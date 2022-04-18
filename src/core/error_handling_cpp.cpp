#include <exception>
#include <typeinfo>
using namespace std;

extern "C"
{

  const char* exc_what(exception& e) { return e.what(); }

  const std::type_info* exc_type() { return &typeid(exception); }

  const char* exc_typename(std::type_info* type) { return type->name(); }
}
