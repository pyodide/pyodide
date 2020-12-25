#include "Python.h"
#include <stdio.h>

#define ASSERT(...)                                                   \
  do {\
    int result = __VA_ARGS__;                                                                       \
    printf("result : %d\n", result);\
    if(!result) {                                                        \
      asprintf(&failure_msg,                                                   \
               "Assertion failed on line %d in %s (function %s):\n%s",         \
               __LINE__,                                                       \
               __FILE__,                                                       \
               __func__,                                                       \
               #__VA_ARGS__);                                                    \
      return failure_msg;                                                      \
    }                                                                          \
  } while (0)

#define DEFINE_TEST(name, ...)\
  char* \
  inner_test_ ## name(){\
    char* failure_msg = NULL;\
    __VA_ARGS__\
    return failure_msg;\
  }\
  EM_JS(void, test_ ## name, (), {\
    Module.Tests.raise_on_fail(_inner_test_ ## name());\
  })
