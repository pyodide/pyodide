#include <exception>
#include <stdexcept>
using namespace std;

extern "C"
{

  void throw_20() { throw 20; }

  class myexception : public exception
  {
    virtual const char* what() const throw() { return "My exception happened"; }
  } myex;

  int throw_my_exc() { throw myex; }

  int throw_runtime_exc() { throw runtime_error("Hello there!"); }
}