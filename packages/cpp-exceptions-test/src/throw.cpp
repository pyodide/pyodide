#include <exception>
#include <stdexcept>
using namespace std;

class myexception : public exception
{
  virtual const char* what() const throw() { return "My exception happened"; }
} myex;

extern "C" char*
throw_exc(int x)
{
  if (x == 1) {
    throw 1000;
  } else if (x == 2) {
    throw 'c';
  } else if (x == 3) {
    throw runtime_error("abc");
  } else if (x == 4) {
    throw myex;
  } else {
    throw "abc";
  }
}
