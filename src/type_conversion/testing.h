#ifndef TEST_H
#define TEST_H
#ifdef TEST

#include "Python.h"
#include <stdio.h>

int
testing_init();

// For use in tests.
// If the assertion is false, malloc an explanation and return it.
#define ASSERT(assertion...)                                                   \
  do {                                                                         \
    printf("asserted: %s\n", #assertion);                                      \
    if (!(assertion)) {                                                        \
      printf("Assertion failed!");                                             \
      char* failure_msg;                                                       \
      asprintf(&failure_msg,                                                   \
               "Assertion failed on line %d:\nASSERT(%s);",                    \
               __LINE__,                                                       \
               #assertion);                                                    \
      printf("%s\n", failure_msg);                                             \
      return failure_msg;                                                      \
    }                                                                          \
    printf("Assertion passed!");                                               \
  } while (0)

// Define a C function called inner_test_<name-of-test>
// and a javascript wrapper called test_<name-of-test>
#define DEFINE_TEST(name, body...)                                             \
  _DEFINE_TEST_INNER(name, body)                                               \
  _DEFINE_TEST_HELPER(_expect_success, name, #body, __LINE__, __FILE__)

#define DEFINE_TEST_EXPECT_FAIL(name, match, body...)                          \
  _DEFINE_TEST_INNER(name, body)                                               \
  _DEFINE_TEST_HELPER(_expect_fail, name, match, #body, __LINE__, __FILE__)

#define _DEFINE_TEST_INNER(name, ...)                                          \
  char* inner_test_##name()                                                    \
  {                                                                            \
    __VA_ARGS__                                                                \
    return NULL;                                                               \
  }

// We need this helper function because EM_JS blocks expansion of macros
// inside its body, so we need to expand out the inner macros first
// Remember: C macros expand their arguments exactly once.
#define _DEFINE_TEST_HELPER(fn, name, args...)                                 \
  EM_JS(void, test_##name, (), {                                               \
    return Module.Tests.fn(_inner_test_##name(), #name, args);                 \
  })

// clang-format on

#endif // TEST
#endif // TEST_H
