#include "include/sharedlibtest.h"

int
do_the_thing(int a, int b)
{
  return dep_do_the_thing(a, b) + b + a * b;
}
