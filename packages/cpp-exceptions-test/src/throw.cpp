#include <exception>
#include <stdexcept>
using namespace std;

char*
g(int x)
{
  if (x == 1) {
    throw 1000;
  } else if (x == 2) {
    throw 'c';
  } else if (x == 3) {
    throw runtime_error("abc");
  } else {
    throw "abc";
  }
  return "no exception here...";
}

class myexception : public exception
{
  virtual const char* what() const throw() { return "My exception happened"; }
} myex;

extern "C"
{

  void throw_20() { throw 20; }

  int throw_my_exc() { throw myex; }

  int throw_runtime_exc() { throw runtime_error("Hello there!"); }
}