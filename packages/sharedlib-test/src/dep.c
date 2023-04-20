#include "include/sharedlibtest.h"

int
dep_do_the_thing(int a, int b)
{
  return dep_dep_do_the_thing(a);
}
